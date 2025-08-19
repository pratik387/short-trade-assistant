from datetime import datetime, timedelta, time as dt_time
import threading
import time
from typing import List

import pandas as pd

from config.logging_config import get_loggers
from services.indicator_enrichment_service import compute_intraday_breakout_score
from util.util import get_previous_trading_day
from brokers.mock.mock_broker import MockBroker

from services.intraday.levels import (
    opening_range,
    yesterday_levels,
    distance_bpct,
)
from services.intraday.ranker import rank_candidates
from services.intraday.planner_internal import generate_trade_plan

logger, _ = get_loggers()

# -------------------- Rate limiter --------------------
rate_limit_lock = threading.Lock()
last_api_call_time = [0]
API_MIN_INTERVAL = 0.35

def _rate_limit():
    with rate_limit_lock:
        elapsed = time.time() - last_api_call_time[0]
        if elapsed < API_MIN_INTERVAL:
            time.sleep(API_MIN_INTERVAL - elapsed)
        last_api_call_time[0] = time.time()

def rate_limited_fetch_5m(symbol, broker, from_date, to_date):
    if isinstance(broker, MockBroker):
        return broker.fetch_candles(symbol=symbol, interval="5minute",
                                    from_date=from_date, to_date=to_date)
    _rate_limit()
    return broker.fetch_candles(symbol=symbol, interval="5minute", from_date=from_date, to_date=to_date)

def rate_limited_fetch_daily(symbol, broker, to_date, lookback_days=5):
    if isinstance(broker, MockBroker):
        from_date = to_date - timedelta(days=lookback_days + 3)
        return broker.fetch_candles(symbol=symbol, interval="day", from_date=from_date, to_date=to_date)
    _rate_limit()
    from_date = to_date - timedelta(days=lookback_days + 3)
    return broker.fetch_candles(symbol=symbol, interval="day", from_date=from_date, to_date=to_date)

# ---- NA-safe helpers ----
def _sf(val, default=0.0):
    return float(val) if pd.notna(val) else default

def _si(val, default=0):
    return int(val) if pd.notna(val) else default

def _precision_params(config):
    if not isinstance(config, dict) or "precision_screener" not in config:
        raise ValueError("Missing required 'precision_screener' block in filters_config.json")
    p = config["precision_screener"]
    required = [
        "buffer_bpct","min_vol_ratio","vwap_grace_bpct","rsi_range","adx_range",
        "ma20_min_slope","max_breakout_dist_bpct","confirm_bars","retest_bpct",
        "lunch_window","late_cutoff"
    ]
    missing = [k for k in required if k not in p]
    if missing:
        raise ValueError(f"precision_screener missing keys: {missing}")
    return {
        "buf_bpct": float(p["buffer_bpct"]),
        "vol_min": float(p["min_vol_ratio"]),
        "vwap_grace": float(p["vwap_grace_bpct"]),
        "rsi_lo": float(p["rsi_range"][0]),
        "rsi_hi": float(p["rsi_range"][1]),
        "adx_lo": float(p["adx_range"][0]),
        "adx_hi": float(p["adx_range"][1]),
        "ma20_min_slope": float(p["ma20_min_slope"]),
        "max_breakout_dist": float(p["max_breakout_dist_bpct"]),
        "confirm_bars": int(p["confirm_bars"]),
        "retest_bpct": float(p["retest_bpct"]),
        "lunch_start": dt_time(*map(int, str(p["lunch_window"]["start"]).split(":"))),
        "lunch_end":   dt_time(*map(int, str(p["lunch_window"]["end"]).split(":"))),
        "late_cutoff": dt_time(*map(int, str(p["late_cutoff"]).split(":"))),
    }

def _passes_precision_breakout(df5, last, level_px: float, params: dict, side: str):
    """
    Unified precision check for both LONG breakouts and SHORT breakdowns.
    Returns (ok: bool, confirmations: dict)
    confirmations = {"retest_ok": bool, "vwap_hold": bool}
    """
    try:
        bar_time = last.name.time() if isinstance(last.name, pd.Timestamp) else pd.to_datetime(last.name).time()
    except Exception:
        return False, {"retest_ok": False, "vwap_hold": False}

    # --- Hard lunch & late cutoff ---
    lunch_start = params["lunch_start"]; lunch_end = params["lunch_end"]
    if lunch_start <= bar_time <= lunch_end:
        return False, {"retest_ok": False, "vwap_hold": False}
    late_cutoff = params["late_cutoff"]
    if bar_time >= late_cutoff:
        return False, {"retest_ok": False, "vwap_hold": False}

    # prices & indicators (NA-safe)
    close_px = _sf(last.get("close"), float("nan"))
    vwap_px  = _sf(last.get("vwap"),  float("nan"))
    rsi      = _sf(last.get("RSI"),   float("nan"))
    adx      = _sf(last.get("ADX_ACTIVE"), float("nan"))
    vol_ratio  = _sf(last.get("volume_ratio"), 0.0)

    # 20-EMA + slope over recent few bars
    ma20_ser   = df5["close"].ewm(span=20, adjust=False).mean()
    ma20       = _sf(ma20_ser.iloc[-1], float("nan"))
    ma20_slope = _sf(ma20_ser.diff().tail(3).mean(), 0.0)

    if not (pd.notna(close_px) and pd.notna(level_px)):
        return False, {"retest_ok": False, "vwap_hold": False}

    # thresholds
    buf      = params["buf_bpct"] / 100.0
    vol_ok   = vol_ratio >= params["vol_min"]
    rsi_ok   = pd.notna(rsi) and (params["rsi_lo"] <= rsi <= params["rsi_hi"])
    adx_ok   = pd.notna(adx) and (params["adx_lo"] <= adx <= params["adx_hi"])
    dist_bp  = distance_bpct(level_px, close_px)
    not_chased = (pd.notna(dist_bp) and dist_bp <= params["max_breakout_dist"])

    if side == "long":
        broke    = close_px > level_px * (1 + buf)
        vwap_ok  = pd.notna(vwap_px) and (close_px >= vwap_px * (1 - params["vwap_grace"]/100.0))
        trend_ok = pd.notna(ma20) and (close_px >= ma20) and (ma20_slope >= params["ma20_min_slope"])
        win = df5.tail(max(params["confirm_bars"], 2))
        low_min   = _sf(win["low"].min(), float("nan"))
        retest_ok = pd.notna(low_min) and (low_min >= level_px * (1 - params["retest_bpct"]/100.0))
        hold_ok   = close_px >= level_px
        vwap_hold = pd.notna(vwap_px) and (close_px >= vwap_px)
    else:
        broke    = close_px < level_px * (1 - buf)
        vwap_ok  = pd.notna(vwap_px) and (close_px <= vwap_px * (1 + params["vwap_grace"]/100.0))
        trend_ok = pd.notna(ma20) and (close_px <= ma20) and (ma20_slope <= -params["ma20_min_slope"])
        win = df5.tail(max(params["confirm_bars"], 2))
        high_max  = _sf(win["high"].max(), float("nan"))
        retest_ok = pd.notna(high_max) and (high_max <= level_px * (1 + params["retest_bpct"]/100.0))
        hold_ok   = close_px <= level_px
        vwap_hold = pd.notna(vwap_px) and (close_px <= vwap_px)

    confirmations = {"retest_ok": bool(retest_ok), "vwap_hold": bool(vwap_hold)}

    if not (broke and vol_ok and vwap_ok and trend_ok and rsi_ok and adx_ok):
        return False, confirmations
    if not (retest_ok and hold_ok and vwap_hold):
        return False, confirmations
    if not not_chased:
        return False, confirmations

    return True, confirmations



def screen_and_rank_intraday_candidates(suggestions, broker, config, top_n=7, *, override_from_date=None, override_to_date=None) -> List[dict]:
    logger.info("🔍 [Intraday] Phase‑1 screen+rank (REST‑only) starting…")

    rows = []
    now = datetime.now().replace(second=0, microsecond=0)
    market_open = now.replace(hour=9, minute=15)
    market_close = now.replace(hour=15, minute=30)

    if now < market_open or now > market_close:
        prev_day = get_previous_trading_day(datetime.now())
        to_date = datetime.combine(prev_day, dt_time(15, 30))
        logger.info(f"ℹ️ [Intraday] Market not live; using last session up to {to_date}")
    else:
        to_date = datetime.now() - timedelta(minutes=5)
        logger.info(f"ℹ️ [Intraday] Live window ends at {to_date}")
    from_date = to_date - timedelta(minutes=90)
    if override_to_date is not None:
        to_date = override_to_date
    if override_from_date is not None:
        from_date = override_from_date

    gate_cfg = config.get("intraday_gate")
    min_vr = float(gate_cfg.get("min_volume_ratio"))
    require_above_vwap = bool(gate_cfg.get("require_above_vwap"))
    params = _precision_params(config)

    dbg_counts = {"start": 0, "fetch_skip": 0, "gate_fail": 0, "level_fail": 0, "break_fail": 0, "final_pass": 0}

    for s in suggestions:
        sym = s.get("symbol")
        if not sym:
            continue
        dbg_counts["start"] += 1
        try:
            logger.debug(f"— ▶️ {sym}: fetching 5m {from_date} → {to_date}")
            df5 = rate_limited_fetch_5m(sym, broker, from_date, to_date)
            if df5 is None or df5.empty or len(df5) < 6:
                dbg_counts["fetch_skip"] += 1
                logger.debug(f"— ⛔ {sym}: insufficient 5m bars (have={0 if df5 is None else len(df5)})")
                continue

            df5 = compute_intraday_breakout_score(df5, config, symbol=sym, mode="normal")
            last = df5.iloc[-1]

            vr = _sf(last.get("volume_ratio"), 0.0)
            above = _si(last.get("above_vwap"), 0)

            close_px = _sf(last.get("close"), float("nan"))
            vwap_px  = _sf(last.get("vwap"),  float("nan"))
            vwap_str = f"{vwap_px:.2f}" if pd.notna(vwap_px) else "nan"

            logger.debug(
                f"— 🔎 {sym}: VR={vr:.2f} | above_vwap={above} | close={close_px:.2f} | vwap={vwap_str}"
            )

            relax_vwap_bpct = float(gate_cfg.get("vwap_relax_bpct"))

            vwap_check = True
            if require_above_vwap:
                vwap_check = (pd.notna(vwap_px) and abs((close_px - vwap_px) / vwap_px) * 100.0 <= relax_vwap_bpct)

            if not (vr >= min_vr and vwap_check):
                dbg_counts["gate_fail"] += 1
                logger.debug(f"— ⛔ {sym}: gate fail (VR={vr:.2f} < {min_vr} or |close-vwap| > {relax_vwap_bpct:.2f}%)")
                continue

            logger.debug(f"— 🔎 {sym}: VR={vr:.2f} | above_vwap={above} | close={close_px:.2f} | vwap={vwap_px:.2f}")
            
            level_px = float("nan")
            level_name = None

            dfd = rate_limited_fetch_daily(sym, broker, to_date, lookback_days=5)
            # Resolve yesterday levels robustly
            y_hi = y_lo = None
            try:
                y_levels = yesterday_levels(dfd) if (dfd is not None and not dfd.empty) else None
                if isinstance(y_levels, (list, tuple)) and len(y_levels) >= 2:
                    y_hi, y_lo = float(y_levels[0]), float(y_levels[1])
            except Exception:
                pass

            # Opening range
            orb_hi = orb_lo = None
            try:
                orb_hi, orb_lo = opening_range(df5)
                orb_hi = float(orb_hi) if pd.notna(orb_hi) else None
                orb_lo = float(orb_lo) if pd.notna(orb_lo) else None
            except Exception:
                pass

            made_any = False
            for side in ("long", "short"):
                if side == "long":
                    level_px = y_hi if (y_hi is not None and pd.notna(y_hi)) else (orb_hi if orb_hi is not None else float("nan"))
                    level_name = "y_high(daily)" if (y_hi is not None and pd.notna(y_hi)) else ("orb15_high" if orb_hi is not None else None)
                else:
                    level_px = y_lo if (y_lo is not None and pd.notna(y_lo)) else (orb_lo if orb_lo is not None else float("nan"))
                    level_name = "y_low(daily)" if (y_lo is not None and pd.notna(y_lo)) else ("orb15_low" if orb_lo is not None else None)

                if (level_name is None) or pd.isna(level_px):
                    continue

                logger.debug(f"— 📏 {sym} [{side}]: level={level_name} @ {level_px:.2f}")
                ok, confirmations = _passes_precision_breakout(df5, last, level_px, params, side=side)
                if not ok:
                    continue

                dist = distance_bpct(level_px, close_px)
                adx_val   = _sf(last.get("ADX_ACTIVE"), 0.0)
                adx_slope = _sf(last.get("adx_slope"), 0.0)
                rsi_val   = _sf(last.get("RSI"), 0.0)
                rsi_slope = _sf(last.get("rsi_slope"), 0.0)

                try:
                    atr_proxy = float((df5["high"] - df5["low"]).rolling(5).mean().iloc[-1])
                    if pd.isna(atr_proxy):
                        atr_proxy = float((df5["high"] - df5["low"]).tail(5).mean())
                except Exception:
                    atr_proxy = 0.0

                rows.append({
                    "symbol": sym,
                    "intraday_score": float(s.get("intraday_score", s.get("score", 0.0))),
                    "level": {"name": level_name, "px": float(level_px)},
                    "intraday": {
                        "volume_ratio": vr,
                        "rsi": rsi_val,
                        "rsi_slope": rsi_slope,
                        "adx": adx_val,
                        "adx_slope": adx_slope,
                        "ma20_slope": float(df5["close"].ewm(span=20, adjust=False).mean().diff().tail(3).mean()),
                        "above_vwap": _si(last.get("above_vwap"), 0),
                        "dist_from_level_bpct": float(dist if dist == dist else 9.99),
                        "squeeze_pctile": _sf(last.get("squeeze_pctile"), float("nan")),
                        "squeeze_ok": _si(last.get("squeeze_ok"), 0), 
                        "retest_ok": confirmations.get("retest_ok"),
                        "vwap_hold": confirmations.get("vwap_hold"),
                        "acceptance_ok": True,
                        "bias": side,
                    },
                    "last_close": close_px,
                    "vwap": vwap_px,
                    "atr5": float(atr_proxy or 0.0),
                    "df": df5,
                    "daily_df": dfd,
                })
                made_any = True

            if not made_any:
                dbg_counts["break_fail"] += 1
                logger.debug(f"— ⛔ {sym}: precision break fail (neither long nor short)")
                continue

            dbg_counts["final_pass"] += 1

        except Exception as e:
            logger.exception(f"— ⚠️ {sym}: exception, skipping → {e}")

    final_ranked = []
    ranked = rank_candidates(rows, top_n=top_n)
    for r in ranked:
        # plan = make_plan(
        #     symbol=r["symbol"],
        #     indicators=r["intraday"],
        #     context={
        #         "price": r["last_close"],
        #         "vwap": r.get("vwap", float("nan")),
        #         "orb_high": r["level"]["px"],
        #         "orb_low": None,  # optional
        #         "prev_high": r["level"]["px"],
        #         "prev_low": None
        #     }
        # )
        session_start = datetime.combine(to_date.date(), dt_time(9, 15))
        plan_df = rate_limited_fetch_5m(r["symbol"], broker, session_start, to_date)
        if plan_df is None or plan_df.empty:
            continue
        daily_df = r.get("daily_df")
        plan = generate_trade_plan(df=plan_df, symbol=r["symbol"], config=config, daily_df=daily_df)
        if not plan:
            continue
        # --- NEW: structural RR guard ---
        struct_rr = (plan.get("quality", {}) or {}).get("structural_rr")
        if struct_rr is not None and struct_rr < 1.0:
            # skip low-upside / near overhead-supply structures
            continue
        r["plan"] = plan
        final_ranked.append(r)

    logger.info(
        "[Intraday Summary] start=%d | fetch_skip=%d | gate_fail=%d | level_fail=%d | break_fail=%d | final_pass=%d",
        dbg_counts["start"], dbg_counts["fetch_skip"], dbg_counts["gate_fail"], dbg_counts["level_fail"], dbg_counts["break_fail"], dbg_counts["final_pass"]
    )
    logger.info(f"✅ Prepared {len(final_ranked)} ranked picks with plans")
    return final_ranked
