"""
Intraday backtesting engine (candle-by-candle) that:
  • loads suggestions (daily list) from JSON
  • on every 5‑minute close of the chosen date, calls the *production* screener to get ranked picks with plans
  • evaluates whether plan criteria are met (entries) and records trades using a TradeRecorder‑style interface
  • checks exits after every candle (stop/targets) and closes trades, logging diagnostics
  • supports multiple entries per symbol (separate trades)

Design goals:
  • Minimal changes to production code — the only non‑breaking change we assume is that
    `screen_and_rank_intraday_candidates(...)` accepts optional `override_to_date` / `override_from_date`.
    If not present yet, add them as optional kwargs (defaults keep current behavior).
  • MockBroker continues to read Feather files and slice by the provided from/to dates.

Author: trading-assistant
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time as dt_time
from typing import Any, Dict, List, Optional, Tuple
import sys
from pathlib import Path
import re as _re_local
# Ensure the root directory is in sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.intraday_screener import screen_and_rank_intraday_candidates
from brokers.mock.mock_broker import MockBroker
from trade_recorder import TradeRecorder
from config.filters_setup import load_filters
from config.logging_config import get_loggers
from util.diagnostic_report_generator import diagnostics_tracker
from util.util import is_trading_day

logger, trade_logger = get_loggers()
config = load_filters()

SUGGESTIONS_BASE = ROOT / "cache" / "suggestions" / "mock"
TOP_N = 40
INTERVAL_MIN = 5
START_TIME = (9, 20)
END_TIME = (15, 15)
LOOKBACK_MIN = 90

# --- Entry trigger tuning ---
PROX_ENTRY_BPCT = 0.15   # allow entries when close is within 0.15% of zone
LUNCH_PROX_BPCT = 0.10   # tighter during lunch window (12:15–14:30 IST)
ENABLE_BREAKOUT = True
BREAKOUT_MIN_VR = 1.6    # breakout needs some volume expansion

@dataclass
class EngineConfig:
    test_date: datetime
    end_date: Optional[datetime] = None


@dataclass
class OpenTrade:
    trade_id: str
    symbol: str
    side: str  # "long" or "short"
    qty: int
    entry_price: float
    entry_time: datetime
    stop: float
    t1: float
    meta: Dict[str, Any] = field(default_factory=dict)
    # --- Partial/runner fields ---
    qty_open: int = 0
    qty_closed: int = 0
    t2: float | None = None
    t1_done: bool = False
    trail_mode: str | None = None
    t1_book_pct: float = 0.30


def _parse_book_pct(action: str | None, default: float = 0.30) -> float:
    if not action:
        return default
    m = _re_local.search(r"book[_\s]?(\d+)\s*%", str(action), flags=_re_local.I)
    if not m:
        return default
    pct = max(5, min(95, int(m.group(1)))) / 100.0
    return float(pct)


def _round_to_lot(qty: int, lot: int) -> int:
    lot = max(1, int(lot or 1))
    return max(lot, (qty // lot) * lot or lot)


def _size_position(entry: float, stop: float, cfg: dict) -> int:
    """Risk-based sizing: qty = floor(risk_amount / risk_per_share)."""
    try:
        risk_cfg = (cfg or {}).get("risk", {})
        capital = float(risk_cfg.get("risk_capital", 100000.0))
        risk_pct = float(risk_cfg.get("risk_pct_per_trade", 0.005))
        min_qty  = int(risk_cfg.get("min_qty", 1))
        lot      = int(risk_cfg.get("round_lot", 1))
        rps = abs(float(entry) - float(stop))
        if not (rps and rps > 0):
            return 1
        risk_amt = capital * risk_pct
        qty = int(risk_amt // rps)
        qty = max(qty, min_qty)
        qty = _round_to_lot(qty, lot)
        return max(1, qty)
    except Exception:
        return 1


def _should_hold_runner(trade, last, df, cfg) -> bool:
    """Hold remainder for T2 if EV>0 → p2 > L/(G+L) with simple feature-based p2."""
    if trade.t2 is None:
        return False
    G = abs(float(trade.t2) - float(trade.t1))
    L = max(float(trade.t1) - float(trade.stop), 0.0) if trade.side == "long" else max(float(trade.stop) - float(trade.t1), 0.0)
    if G <= 0:
        return False
    threshold = L / (G + L)

    def _f(name, default=float("nan")):
        try:
            return float(last.get(name, default))
        except Exception:
            return default

    adx = _f("ADX_ACTIVE"); adx_slope = _f("adx_slope", 0.0)
    rsi = _f("RSI");        rsi_slope = _f("rsi_slope", 0.0)
    vr  = _f("volume_ratio", 0.0)
    sqp = _f("squeeze_pctile", float("nan"))

    p2 = float((cfg or {}).get("t2_decision", {}).get("p2_baseline", 0.40))
    if adx >= 25 and adx_slope > 0: p2 += 0.08
    if (55 <= rsi <= 68) and rsi_slope > 0: p2 += 0.06
    if vr >= 2.0: p2 += 0.06
    if isinstance(sqp, float) and sqp == sqp and sqp <= 60: p2 += 0.05
    try:
        t = last.name.time() if hasattr(last, "name") else None
        if t and (t.hour > 14 or (t.hour == 14 and t.minute >= 30)):
            p2 -= 0.10
    except Exception:
        pass

    p2 = max(0.0, min(1.0, p2))
    return p2 > threshold


class IntradayBacktestEngine:
    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.run_id = self.cfg.test_date.strftime("%Y-%m-%d")
        self.recorder = TradeRecorder(run_id=self.run_id)
        self.config_blob = config
        self.broker = MockBroker()

        self.open_trades: List[OpenTrade] = []

    def _resolve_suggestion_file(self, date_obj: datetime.date) -> Path:
        return SUGGESTIONS_BASE / f"suggestions_all_{date_obj.strftime('%Y-%m-%d')}.json"

    def _run_intraday_for_date(self, date_ist: datetime.date):
        ticks = self._gen_ticks(
            day=date_ist,
            interval_min=INTERVAL_MIN,
            start_time=START_TIME,
            end_time=END_TIME,
        )
        for tick in ticks:
            from_dt = tick - timedelta(minutes=LOOKBACK_MIN)
            logger.info(f" Running screener at tick: {tick.strftime('%H:%M')}")
            ranked = screen_and_rank_intraday_candidates(
                self.suggestions, self.broker, self.config_blob, TOP_N,
                override_from_date=from_dt, override_to_date=tick,
            )
            self._evaluate_entries(ranked, tick)
            self._evaluate_exits(tick)

        self._force_flatten(date_ist)
    def run(self) -> Dict[str, Any]:
        logger.info(f"🚀 Starting backtest: {self.cfg.test_date.date()} to {self.cfg.end_date.date() if self.cfg.end_date else self.cfg.test_date.date()}")
        diagnostics_tracker.reset_intraday()
        current_date = self.cfg.test_date.date()
        final_date = self.cfg.end_date.date() if self.cfg.end_date else current_date

        while current_date <= final_date:
            if not is_trading_day(current_date):
                logger.info(f"⏩ Skipping {current_date} — market not active")
                current_date += timedelta(days=1)
                continue
            
            logger.info(f"📅 Running for {current_date}")
            suggestion_file = self._resolve_suggestion_file(current_date)
            
            if not suggestion_file.exists():
                logger.warning(f"⚠️ Skipping {current_date} — suggestions file not found: {suggestion_file.name}")
                current_date += timedelta(days=1)
                continue
            self.suggestions = self._load_suggestions(str(suggestion_file))
            self._run_intraday_for_date(current_date)
            current_date += timedelta(days=1)

        diag_entries = dict(getattr(diagnostics_tracker, "intraday_entries", {}) or {})
        diag_events  = list(getattr(diagnostics_tracker, "intraday_exit_events", []) or [])
        log_folder   = str(self.recorder.log_folder_path)
        diagnostics_tracker.reset_intraday()
        return {
            "open": len(self.open_trades),
            "diag_entries": diag_entries,
            "diag_events": diag_events,
            "log_folder": log_folder,
        }

    # --------------------------- Internal logic ---------------------------
    @staticmethod
    def _load_suggestions(path: str) -> List[Dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = []
        if isinstance(data, dict) and "suggestions" in data:
            data = data["suggestions"]
        for row in data:
            if isinstance(row, dict) and row.get("symbol"):
                out.append({"symbol": row["symbol"], "score": row.get("score", 0.0)})
            elif isinstance(row, (list, tuple)) and row:
                out.append({"symbol": row[0], "score": 0.0})
        return out

    @staticmethod
    def _gen_ticks(day: datetime.date, interval_min: int, start_time: Tuple[int, int], end_time: Tuple[int, int]) -> List[datetime]:
        start = datetime.combine(day, dt_time(start_time[0], start_time[1]))
        end = datetime.combine(day, dt_time(end_time[0], end_time[1]))
        cur = start
        ticks: List[datetime] = []
        while cur <= end:
            ticks.append(cur)
            cur += timedelta(minutes=interval_min)
        return ticks

    @staticmethod
    def _infer_side(entry_zone: List[float], targets: List[Dict[str, Any]]) -> str:
        if not entry_zone or not targets:
            return "long"
        mid = (entry_zone[0] + entry_zone[1]) / 2.0
        t1 = float(targets[0].get("level", mid))
        return "long" if t1 >= mid else "short"

    def _evaluate_entries(self, ranked: List[Dict[str, Any]], tick: datetime) -> List[Dict[str, Any]]:
        if tick.time() >= dt_time(15, 0):
            return []
        events: List[Dict[str, Any]] = []
        for row in ranked:
            sym = row.get("symbol")
            plan = row.get("plan", {}) or {}
            zone: List[float] = list(plan.get("entry", {}).get("zone") or [])
            targets: List[Dict[str, Any]] = list(plan.get("targets") or [])
            stop = plan.get("stop")
            stop_hard = float(stop.get("hard")) if isinstance(stop, dict) and stop.get("hard") is not None else None
            if not sym or len(zone) != 2 or stop_hard is None or not targets:
                continue

            side = self._infer_side(zone, targets)
            df = self.broker.fetch_candles(sym, interval="5m", from_date=tick - timedelta(minutes=30), to_date=tick)
            if df is None or df.empty:
                continue
            last = df.iloc[-1]
            high = float(last.get("high", last.get("High", float("nan"))))
            low = float(last.get("low", last.get("Low", float("nan"))))
            close = float(last.get("close", last.get("Close", float("nan"))))

            z_lo, z_hi = float(min(zone)), float(max(zone))

            # --- Entry trigger logic: zone touch / proximity / breakout ---
            lunch = dt_time(12, 15) <= tick.time() < dt_time(14, 30)
            prox_bpct = LUNCH_PROX_BPCT if lunch else PROX_ENTRY_BPCT

            def _dist_bpct(px: float, lo: float, hi: float) -> float:
                return min(abs(px - lo), abs(px - hi)) / max(1e-9, px) * 100.0

            dist_to_zone_bpct = _dist_bpct(close, z_lo, z_hi)
            zone_touched = (low <= z_hi) and (high >= z_lo)

            trigger_type: Optional[str] = None
            entry_px: Optional[float] = None
            if zone_touched:
                trigger_type, entry_px = "ZONE_TOUCH", (z_lo + z_hi) / 2.0
            elif dist_to_zone_bpct <= prox_bpct:
                trigger_type, entry_px = "ZONE_PROX", close
            elif ENABLE_BREAKOUT:
                lvl_px = float((row.get("level") or {}).get("px") or (targets[0].get("level") if targets else close) or close)
                ma20_slope = float((row.get("intraday") or {}).get("ma20_slope") or 0.0)
                vr = float((row.get("intraday") or {}).get("volume_ratio") or 1.0)
                if side == "long" and close > lvl_px and ma20_slope >= 0 and vr >= BREAKOUT_MIN_VR:
                    trigger_type, entry_px = "BREAKOUT", close
                elif side == "short" and close < lvl_px and ma20_slope <= 0 and vr >= BREAKOUT_MIN_VR:
                    trigger_type, entry_px = "BREAKOUT", close

            if not entry_px:
                logger.debug(f"[{sym}] No trigger at {tick}: dist_to_zone={dist_to_zone_bpct:.3f}% (prox≤{prox_bpct}%)")
                continue

            intr_ok = bool(row.get("intraday", {}).get("acceptance_ok", True))
            plan_ok = bool((plan.get("quality", {}) or {}).get("acceptance_ok", True))
            if not (intr_ok and plan_ok):
                logger.debug(f"[{sym}] acceptance gate blocked entry at {tick}")
                continue

            qty = _size_position(entry_px, stop_hard, self.config_blob)
            investment = round(entry_px * qty)

            trade_id = f"{sym}-{tick.strftime('%Y%m%d%H%M')}-{len(self.open_trades)+1}"
            t1_level = float(targets[0].get("level"))

            trade = OpenTrade(
                trade_id=trade_id,
                symbol=sym,
                side=side,
                qty=qty,
                entry_price=entry_px,
                entry_time=tick,
                stop=float(stop_hard),
                t1=float(t1_level),
                meta={
                    "zone": zone,
                    "targets": targets,
                    "plan": plan,
                    "investment": investment,
                    "fixed_qty_mode": False,
                },
                qty_open=qty,
                qty_closed=0,
                t2=float(targets[1].get("level")) if len(targets) > 1 and targets[1].get("level") is not None else None,
                t1_done=False,
                trail_mode=str(plan.get("trail") or "vwap_or_ema20"),
                t1_book_pct=_parse_book_pct(targets[0].get("action") if targets else ""),
            )
            self.open_trades.append(trade)

            logger.info(f"✅ ENTRY: {sym} at {entry_px:.2f} (qty={qty}, tick: {tick.strftime('%H:%M')}, trigger={trigger_type})")
            trade_logger.info(json.dumps({
                "event": "ENTRY", "symbol": sym, "trade_id": trade_id,
                "time": tick.strftime("%Y-%m-%d %H:%M"), "price": entry_px,
                "side": side, "qty": qty, "zone": zone, "stop": stop_hard, "t1": t1_level
            }))

            # BACKWARD‑COMPAT call to recorder
            self.recorder.record_entry(symbol=sym, date=tick.isoformat(), price=entry_px, investment=investment)

            diagnostics_tracker.record_intraday_entry_diagnostics(
                trade_id=trade_id,
                diagnostics={
                    "symbol": sym,
                    "entry_time": tick,
                    "entry_price": entry_px,
                    "stop": plan.get("stop", {}).get("hard"),
                    "t1": plan.get("targets", [{}])[0].get("level"),
                    "rr_first": plan.get("targets", [{}])[0].get("rr"),
                    "entry_zone": plan.get("entry", {}).get("zone"),
                    "confidence": plan.get("strategy"),
                    "atr": row.get("atr5"),
                    "vwap": row.get("vwap"),
                    "close": entry_px,
                    "volatility": round((df["high"].max() - df["low"].min()) / close, 4) if close else None,

                    # Indicators at entry
                    "RSI": last.get("RSI"),
                    "rsi_slope": row.get("intraday", {}).get("rsi_slope"),
                    "ADX": last.get("ADX_ACTIVE"),
                    "adx_slope": row.get("intraday", {}).get("adx_slope"),
                    "macd": last.get("macd"),
                    "macd_signal": last.get("macd_signal"),
                    "stochastic_k": last.get("stochastic_k"),
                    "obv": last.get("obv"),
                    "atr5": last.get("atr5"),
                    "ma20_slope": row.get("intraday", {}).get("ma20_slope"),
                    "supertrend_signal": last.get("supertrend_signal"),

                    # VWAP and price structure
                    "above_vwap": row.get("intraday", {}).get("above_vwap"),
                    "distance_from_vwap_bpct": (((entry_px - row.get("vwap")) / row.get("vwap")) * 100) if entry_px and row.get("vwap") else None,
                    "dist_from_level_bpct": ((close - row.get("level", {}).get("px", 0)) / row.get("level", {}).get("px", 1)) * 100 if close else None,

                    # Structural & quality metrics
                    "structural_rr": plan.get("quality", {}).get("structural_rr"),
                    "acceptance_ok": plan.get("quality", {}).get("acceptance_ok"),

                    # Confirmation checks
                    "retest_ok": row.get("intraday", {}).get("confirmation", {}).get("retest_ok"),
                    "vwap_hold": row.get("intraday", {}).get("confirmation", {}).get("vwap_hold"),

                    # Squeeze and ranking
                    "squeeze_pctile": row.get("intraday", {}).get("squeeze_pctile"),
                    "squeeze_ok": row.get("intraday", {}).get("squeeze_ok"),
                    "score": row.get("score"),
                    "rank_score": row.get("rank_score"),

                    # Level info
                    "level_type": row.get("level", {}).get("name"),
                    "level_px": row.get("level", {}).get("px"),

                    # Extra trigger diagnostics
                    "trigger_type": trigger_type,
                    "dist_to_zone_bpct": round(dist_to_zone_bpct, 4),

                    # Exit info (set to None at entry time)
                    "exit_reason": None,
                    "holding_minutes": None,
                }
            )

            events.append({"symbol": sym, "trade_id": trade_id, "reason": "ENTRY"})
        return events

    def _evaluate_exits(self, tick: datetime) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for trade in list(self.open_trades):
            df = self.broker.fetch_candles(trade.symbol, interval="5m", from_date=tick - timedelta(minutes=30), to_date=tick)
            if df is None or df.empty:
                continue
            last = df.iloc[-1]
            high = float(last.get("high", last.get("High", float("nan"))))
            low = float(last.get("low", last.get("Low", float("nan"))))
            close = float(last.get("close", last.get("Close", float("nan"))))

            if trade.side == "long":
                stop_hit = low <= trade.stop
                t1_hit = high >= trade.t1
                t2_hit = (trade.t2 is not None) and (high >= float(trade.t2))
            else:
                stop_hit = high >= trade.stop
                t1_hit = low <= trade.t1
                t2_hit = (trade.t2 is not None) and (low <= float(trade.t2))

            # STOP
            if stop_hit:
                exit_price = trade.stop
                if trade.qty_open > 0:
                    self.recorder.record_exit(symbol=trade.symbol, date=tick.isoformat(), exit_price=exit_price)
                    trade_logger.info(json.dumps({
                        "event": "EXIT", "symbol": trade.symbol, "trade_id": trade.trade_id,
                        "time": tick.strftime("%Y-%m-%d %H:%M"), "price": exit_price,
                        "reason": "STOP", "qty": trade.qty_open
                    }))
                pnl = (exit_price - trade.entry_price) * (1 if trade.side == "long" else -1)
                diagnostics_tracker.record_intraday_exit_diagnostics(
                   trade_id=trade.trade_id, exit_price=exit_price, pnl=pnl,
                   exit_time=tick.strftime("%Y-%m-%d %H:%M"), reason="STOP"
                )
                self.open_trades.remove(trade)
                events.append({"symbol": trade.symbol, "trade_id": trade.trade_id, "reason": "STOP"})
                continue

            # T2 (only after T1 partial done)
            if t2_hit and trade.t1_done and trade.qty_open > 0:
                exit_price = float(trade.t2)
                self.recorder.record_exit(symbol=trade.symbol, date=tick.isoformat(), exit_price=exit_price)
                trade_logger.info(json.dumps({
                    "event": "EXIT", "symbol": trade.symbol, "trade_id": trade.trade_id,
                    "time": tick.strftime("%Y-%m-%d %H:%M"), "price": exit_price,
                    "reason": "T2", "qty": trade.qty_open
                }))
                pnl = (exit_price - trade.entry_price) * (1 if trade.side == "long" else -1)
                diagnostics_tracker.record_intraday_exit_diagnostics(
                   trade_id=trade.trade_id, exit_price=exit_price, pnl=pnl,
                   exit_time=tick.strftime("%Y-%m-%d %H:%M"), reason="T2"
                )
                trade.qty_closed += trade.qty_open
                trade.qty_open = 0
                self.open_trades.remove(trade)
                events.append({"symbol": trade.symbol, "trade_id": trade.trade_id, "reason": "T2"})
                continue

            # T1 partial + EV decision
            if t1_hit and (not trade.t1_done) and trade.qty_open > 0:
                part_qty = max(int(round(trade.qty_open * trade.t1_book_pct)), 1)
                part_qty = min(part_qty, trade.qty_open)
                self.recorder.record_exit(symbol=trade.symbol, date=tick.isoformat(), exit_price=trade.t1)
                trade_logger.info(json.dumps({
                    "event": "EXIT", "symbol": trade.symbol, "trade_id": trade.trade_id,
                    "time": tick.strftime("%Y-%m-%d %H:%M"), "price": trade.t1,
                    "reason": "T1_PARTIAL", "qty": part_qty
                }))
                pnl = (trade.t1 - trade.entry_price) * (1 if trade.side == "long" else -1)
                diagnostics_tracker.record_intraday_exit_diagnostics(
                   trade_id=trade.trade_id, exit_price=trade.t1, pnl=pnl,
                   exit_time=tick.strftime("%Y-%m-%d %H:%M"), reason="T1_PARTIAL"
                )

                trade.qty_open -= part_qty
                trade.qty_closed += part_qty
                trade.t1_done = True

                # raise stop to BE/VWAP/EMA20
                be = trade.entry_price
                try:
                    vwap = float(last.get("vwap", float("nan")))
                except Exception:
                    vwap = float("nan")
                try:
                    ema20 = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
                except Exception:
                    ema20 = float("nan")
                anchors = [x for x in [be, vwap, ema20] if x == x]
                if anchors:
                    if trade.side == "long":
                        trade.stop = max(anchors) * 0.999
                    else:
                        trade.stop = min(anchors) * 1.001

                hold_runner = _should_hold_runner(trade, last, df, self.config_blob)
                if not hold_runner and trade.qty_open > 0:
                    self.recorder.record_exit(symbol=trade.symbol, date=tick.isoformat(), exit_price=trade.t1)
                    trade_logger.info(json.dumps({
                        "event": "EXIT", "symbol": trade.symbol, "trade_id": trade.trade_id,
                        "time": tick.strftime("%Y-%m-%d %H:%M"), "price": trade.t1,
                        "reason": "T1_FULL", "qty": trade.qty_open
                    }))
                    pnl = (trade.t1 - trade.entry_price) * (1 if trade.side == "long" else -1)
                    diagnostics_tracker.record_intraday_exit_diagnostics(
                       trade_id=trade.trade_id, exit_price=trade.t1, pnl=pnl,
                       exit_time=tick.strftime("%Y-%m-%d %H:%M"), reason="T1_FULL"
                    )

                    trade.qty_closed += trade.qty_open
                    trade.qty_open = 0
                    self.open_trades.remove(trade)
                    events.append({"symbol": trade.symbol, "trade_id": trade.trade_id, "reason": "T1_FULL"})
                continue

        return events

    def _force_flatten(self, day: Optional[datetime.date] = None):
        if not self.open_trades:
            return
        day = day or self.cfg.test_date.date()
        eod_tick = datetime.combine(day, dt_time(*END_TIME))
        for trade in list(self.open_trades):
            df = self.broker.fetch_candles(trade.symbol, interval="5m", from_date=eod_tick - timedelta(minutes=30), to_date=eod_tick)
            if df is None or df.empty:
                exit_price = trade.meta.get("last_close", trade.entry_price)
            else:
                last = df.iloc[-1]
                exit_price = float(last.get("close", last.get("Close", trade.entry_price)))
            self.recorder.record_exit(symbol=trade.symbol, date=eod_tick.isoformat(), exit_price=exit_price)
            trade_logger.info(json.dumps({
                "event": "EXIT", "symbol": trade.symbol, "trade_id": trade.trade_id, "time": eod_tick.strftime("%Y-%m-%d %H:%M"), "price": exit_price, "reason": "EOD", "qty": getattr(trade, 'qty_open', 0) or trade.qty
            }))
            pnl = (exit_price - trade.entry_price) * (1 if trade.side == "long" else -1)
            diagnostics_tracker.record_intraday_exit_diagnostics(
               trade_id=trade.trade_id, exit_price=exit_price, pnl=pnl,
               exit_time=eod_tick.strftime("%Y-%m-%d %H:%M"), reason="EOD"
            )

            self.open_trades.remove(trade)


# ----------------------------- Convenience CLI -----------------------------
if __name__ == "__main__":
    TEST_DAY = datetime.strptime("2023-01-01", "%Y-%m-%d")
    END_DAY = datetime.strptime("2023-01-15", "%Y-%m-%d")
    ENGINE = IntradayBacktestEngine(EngineConfig(test_date=TEST_DAY, end_date=END_DAY))
    ENGINE.run()
