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

logger, trade_logger = get_loggers()
config = load_filters()

SUGGESTIONS_BASE = ROOT / "cache" / "suggestions" / "mock"
CACHE_BASE = ROOT / "backtesting" / "ohlcv_archive"
TOP_N = 12
INTERVAL_MIN = 5
START_TIME = (9, 20)
END_TIME = (15, 15)
LOOKBACK_MIN = 90

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


class IntradayBacktestEngine:
    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.recorder = TradeRecorder()
        self.config_blob = config
        self.broker = MockBroker()

        self.open_trades: List[OpenTrade] = []

    # ----------------------------- Public API -----------------------------
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
            try:
                ranked = screen_and_rank_intraday_candidates(
                    self.suggestions,
                    self.broker,
                    self.config_blob,
                    TOP_N,
                    override_from_date=from_dt,
                    override_to_date=tick,
                )
            except TypeError:
                raise TypeError(
                    "screen_and_rank_intraday_candidates is missing `override_from_date`/`override_to_date`."
                    "Please add them as optional kwargs and pass through to the broker fetch window."
                )
            self._evaluate_entries(ranked, tick)
            self._evaluate_exits(tick)

        self._force_flatten(date_ist)
    def run(self) -> Dict[str, Any]:
        logger.info(f"🚀 Starting backtest: {self.cfg.test_date.date()} to {self.cfg.end_date.date() if self.cfg.end_date else self.cfg.test_date.date()}")
        current_date = self.cfg.test_date.date()
        final_date = self.cfg.end_date.date() if self.cfg.end_date else current_date

        while current_date <= final_date:
            logger.info(f"📅 Running for {current_date}")
            suggestion_file = self._resolve_suggestion_file(current_date)

            if not suggestion_file.exists():
                logger.warning(f"⚠️ Skipping {current_date} — suggestions file not found: {suggestion_file.name}")
                current_date += timedelta(days=1)
                continue
            self.suggestions = self._load_suggestions(str(suggestion_file))
            self._run_intraday_for_date(current_date)
            current_date += timedelta(days=1)

        self.recorder.export_csv()
        return {"open": len(self.open_trades)}

    # --------------------------- Internal logic ---------------------------
    @staticmethod
    def _load_suggestions(path: str) -> List[Dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # normalize into a list of dicts with at least `symbol` and `score`
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
            zone: List[float] = list(plan.get("entry_zone") or [])
            targets: List[Dict[str, Any]] = list(plan.get("targets") or [])
            stop = plan.get("stop")
            stop_hard = float(stop.get("hard")) if isinstance(stop, dict) and stop.get("hard") is not None else None
            if not sym or len(zone) != 2 or stop_hard is None or not targets:
                continue

            side = self._infer_side(zone, targets)
            # Fetch the *last* closed 5m bar at tick for this symbol to decide entry
            df = self.broker.fetch_candles(sym, interval="5m", from_date=tick - timedelta(minutes=30), to_date=tick)
            if df is None or df.empty:
                continue
            last = df.iloc[-1]
            high = float(last.get("high", last.get("High", float("nan"))))
            low = float(last.get("low", last.get("Low", float("nan"))))
            close = float(last.get("close", last.get("Close", float("nan"))))

            z_lo, z_hi = float(min(zone)), float(max(zone))

            def in_zone(px: float) -> bool:
                return z_lo <= px <= z_hi

            enter = in_zone(close) or (low <= z_hi and high >= z_lo and in_zone((high + low + close) / 3.0))
            if not enter:
                logger.debug(f"[{sym}] Zone mismatch at {tick}: close={close}, zone={zone}, high={high}, low={low}")
                continue

            # ✅ Always 1 share for win-rate testing
            qty = 1
            investment = round(close * qty)

            trade_id = f"{sym}-{tick.strftime('%Y%m%d%H%M')}-{len(self.open_trades)+1}"
            t1_level = float(targets[0].get("level"))

            trade = OpenTrade(
                trade_id=trade_id,
                symbol=sym,
                side=side,
                qty=qty,
                entry_price=close,
                entry_time=tick,
                stop=float(stop_hard),
                t1=float(t1_level),
                meta={
                    "zone": zone,
                    "targets": targets,
                    "plan": plan,
                    "investment": investment,
                    "fixed_qty_mode": True,  # optional flag for later debugging
                },
            )
            self.open_trades.append(trade)

            logger.info(f"✅ ENTRY: {sym} at {close:.2f} (tick: {tick.strftime('%H:%M')})")
            trade_logger.info(json.dumps({
                "event": "ENTRY",
                "symbol": sym,
                "trade_id": trade_id,
                "time": tick.strftime("%Y-%m-%d %H:%M"),
                "price": close,
                "side": side,
                "zone": zone,
                "stop": stop_hard,
                "t1": t1_level,
                "investment": investment
            }))

            # Record using project TradeRecorder API
            self.recorder.record_entry(symbol=sym, date=tick.isoformat(), price=close, investment=investment)
            diagnostics_tracker.record_intraday_entry_diagnostics(
                symbol=sym,
                entry_time=tick,
                price=close,
                trade_id = trade_id,
                plan=plan,
                df=df,
                reasons=row.get("intraday")
            )
            events.append({"symbol": sym, "trade_id": trade_id, "reason": "entry_zone_met"})
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

            exit_reason = None
            exit_price = None

            if trade.side == "long":
                if low <= trade.stop:
                    exit_reason = "STOP"
                    exit_price = trade.stop
                elif high >= trade.t1:
                    exit_reason = "T1"
                    exit_price = trade.t1
            else:
                if high >= trade.stop:
                    exit_reason = "STOP"
                    exit_price = trade.stop
                elif low <= trade.t1:
                    exit_reason = "T1"
                    exit_price = trade.t1

            if exit_reason:
                logger.debug(f"[{trade.symbol}] Exit triggered at {tick}: close={close}, reason={exit_reason}, price={exit_price}")
                trade_logger.info(json.dumps({
                    "event": "EXIT",
                    "symbol": trade.symbol,
                    "trade_id": trade.trade_id,
                    "time": tick.strftime("%Y-%m-%d %H:%M"),
                    "price": exit_price,
                    "reason": exit_reason
                }))
                # Record with project TradeRecorder
                self.recorder.record_exit(symbol=trade.symbol, date=tick.isoformat(), exit_price=exit_price)
                pnl = (exit_price - trade.entry_price) * (1 if trade.side == "long" else -1)
                diagnostics_tracker.record_intraday_exit_diagnostics(
                   trade_id=trade.trade_id, exit_price=exit_price, pnl=pnl, exit_time=tick.strftime("%Y-%m-%d %H:%M"), reason=exit_reason
                )
                self.open_trades.remove(trade)
                events.append({"symbol": trade.symbol, "trade_id": trade.trade_id, "reason": exit_reason})
        return events

    def _force_flatten(self, day: Optional[datetime.date] = None):
        if not self.open_trades:
            return

        day = day or self.cfg.test_date.date()
        eod_candidates = [
            (dt_time(*END_TIME), "default EOD flatten"),
        ]

        for eod_time, label in eod_candidates:
            if not self.open_trades:
                return

            tick = datetime.combine(day, eod_time)

            for trade in list(self.open_trades):
                df = self.broker.fetch_candles(
                    trade.symbol,
                    interval="5m",
                    from_date=tick - timedelta(minutes=30),
                    to_date=tick
                )

                if df is None or df.empty:
                    exit_price = trade.meta.get("last_close", trade.entry_price)
                else:
                    last = df.iloc[-1]
                    exit_price = float(last.get("close", last.get("Close", trade.entry_price)))

                pnl = (exit_price - trade.entry_price) * (1 if trade.side == "long" else -1)
                self.recorder.record_exit(
                    symbol=trade.symbol,
                    date=tick.isoformat(),
                    exit_price=exit_price
                )
                diagnostics_tracker.record_intraday_exit_diagnostics(
                   trade_id=trade.trade_id, exit_price=exit_price, pnl=pnl, exit_time=tick.strftime("%Y-%m-%d %H:%M"), reason="EOD"
                )
                trade_logger.info(json.dumps({
                    "event": "EXIT",
                    "symbol": trade.symbol,
                    "trade_id": trade.trade_id,
                    "time": tick.strftime("%Y-%m-%d %H:%M"),
                    "price": exit_price,
                    "reason": "EOD",
                    "pnl": pnl
                }))
                self.open_trades.remove(trade)


# ----------------------------- Convenience CLI -----------------------------
if __name__ == "__main__":
    TEST_DAY = datetime.strptime("2023-01-02", "%Y-%m-%d")
    END_DAY = datetime.strptime("2023-01-02", "%Y-%m-%d")

    ENGINE = IntradayBacktestEngine(
        EngineConfig(
            test_date=TEST_DAY,
            end_date=END_DAY,
        )
    )
    ENGINE.run()
