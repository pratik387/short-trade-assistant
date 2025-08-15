from datetime import datetime, timedelta, time as dt_time
import threading
import time
import os
from typing import List

import pandas as pd

from config.logging_config import get_loggers
from services.indicator_enrichment_service import compute_intraday_breakout_score
from util.util import get_previous_trading_day

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
    _rate_limit()
    return broker.fetch_candles(symbol=symbol, interval="5minute", from_date=from_date, to_date=to_date)

def rate_limited_fetch_daily(symbol, broker, lookback_days=5):
    _rate_limit()
    to_date = datetime.now()
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

def _passes_precision_breakout(df5, last, level_px, params):
    try:
        bar_time = last.name.time() if isinstance(last.name, pd.Timestamp) else pd.to_datetime(last.name).time()
    except Exception:
        return False

    # time gates (avoid lunch/too late unless exceptional)
    vol_ratio = _sf(last.get("volume_ratio"), 0.0)
    if params["lunch_start"] <= bar_time <= params["lunch_end"] and vol_ratio < (params["vol_min"] * 1.25):
        return False
    if bar_time >= params["late_cutoff"]:
        return False

    # prices & indicators (NA-safe)
    close_px = _sf(last.get("close"), float("nan"))
    vwap_px  = _sf(last.get("vwap"),  float("nan"))
    rsi      = _sf(last.get("RSI"),   float("nan"))
    adx      = _sf(last.get("ADX_ACTIVE"), float("nan"))

    ma20_ser   = df5["close"].ewm(span=20, adjust=False).mean()
    ma20       = _sf(ma20_ser.iloc[-1], float("nan"))
    ma20_slope = _sf(ma20_ser.diff().tail(3).mean(), 0.0)

    if not (pd.notna(close_px) and pd.notna(level_px)):
        return False

    # primary trigger
    broke    = close_px > level_px * (1 + params["buf_bpct"]/100.0)
    vol_ok   = vol_ratio >= params["vol_min"]
    vwap_ok  = pd.notna(vwap_px) and (close_px >= vwap_px * (1 - params["vwap_grace"]/100.0))
    trend_ok = pd.notna(ma20) and (close_px >= ma20) and (ma20_slope >= params["ma20_min_slope"])
    rsi_ok   = pd.notna(rsi) and (params["rsi_lo"] <= rsi <= params["rsi_hi"])
    adx_ok   = pd.notna(adx) and (params["adx_lo"] <= adx <= params["adx_hi"])
    if not (broke and vol_ok and vwap_ok and trend_ok and rsi_ok and adx_ok):
        return False

    # confirmation: retest & hold
    win = df5.tail(max(params["confirm_bars"], 2))
    low_min   = _sf(win["low"].min(), float("nan"))
    retest_ok = pd.notna(low_min) and (low_min >= level_px * (1 - params["retest_bpct"]/100.0))
    hold_ok   = close_px >= level_px
    vwap_hold = pd.notna(vwap_px) and (close_px >= vwap_px)
    if not (retest_ok and hold_ok and vwap_hold):
        return False

    # chase guard
    dist = distance_bpct(level_px, close_px)
    if pd.notna(dist) and dist > params["max_breakout_dist"]:
        return False

    return True


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
    relax_vwap_bpct = float(gate_cfg.get("vwap_relax_bpct", 0.2))
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

            relax_vwap_bpct = float(gate_cfg.get("vwap_relax_bpct", 0.2))

            vwap_check = True
            if require_above_vwap:
                vwap_check = (pd.notna(vwap_px) and close_px >= vwap_px * (1 - relax_vwap_bpct / 100))

            if not (vr >= min_vr and vwap_check):
                dbg_counts["gate_fail"] += 1
                logger.debug(f"— ⛔ {sym}: gate fail (VR={vr:.2f} < {min_vr} or close not within {relax_vwap_bpct:.2f}% of VWAP)")
                continue


            logger.debug(f"— 🔎 {sym}: VR={vr:.2f} | above_vwap={above} | close={close_px:.2f} | vwap={vwap_px:.2f}")
            
            level_px = float("nan")
            level_name = None

            dfd = rate_limited_fetch_daily(sym, broker, lookback_days=5)
            if dfd is not None and not dfd.empty:
                try:
                    y_hi, _ = yesterday_levels(dfd)
                    if pd.notna(y_hi):
                        level_px = y_hi
                        level_name = "y_high(daily)"
                except Exception:
                    pass

            if pd.isna(level_px):
                orb_hi, _ = opening_range(df5)
                level_px = orb_hi
                level_name = "orb15_high"

            if pd.isna(level_px):
                dbg_counts["level_fail"] += 1
                continue

            logger.debug(f"— 📏 {sym}: level={level_name} @ {level_px:.2f}")

            if not _passes_precision_breakout(df5, last, level_px, params):
                dist = distance_bpct(level_px, close_px)
                dbg_counts["break_fail"] += 1
                logger.debug(f"— ⛔ {sym}: precision breakout fail (close={close_px:.2f}, level={level_px:.2f}, dist={dist:.2f}%)")
                continue

            dist = distance_bpct(level_px, close_px)
            adx_val = _sf(last.get("ADX_ACTIVE"), 0.0)
            adx_slope = _sf(last.get("adx_slope"), 0.0)
            rsi_val = _sf(last.get("RSI"), 0.0)
            rsi_slope = _sf(last.get("rsi_slope"), 0.0)

            try:
                atr_proxy = float((df5["high"] - df5["low"]).rolling(5).mean().iloc[-1])
                if pd.isna(atr_proxy):
                    atr_proxy = float((df5["high"] - df5["low"]).tail(5).mean())
            except Exception:
                atr_proxy = 0.0

            rows.append({
                "symbol": sym,
                "daily_score": float(s.get("score", 0.0)),
                "level": {"name": level_name, "px": float(level_px)},
                "intraday": {
                    "volume_ratio": vr,
                    "rsi": rsi_val,
                    "rsi_slope": rsi_slope,
                    "adx": adx_val,
                    "adx_slope": adx_slope,
                    "above_vwap": above,
                    "dist_from_level_bpct": float(dist if dist == dist else 9.99),
                },
                "last_close": close_px,
                "vwap": vwap_px,
                "atr5": float(atr_proxy or 0.0),
                "df": df5,
            })
            dbg_counts["final_pass"] += 1

        except Exception as e:
            logger.info(f"— ⚠️ {sym}: exception, skipping → {e}")

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
        df = r.get("df")
        if df is None or df.empty:
            continue
        plan = generate_trade_plan(df=df, symbol=r["symbol"], config=config)
        if not plan:
            continue
        r["plan"] = {
            "entry_note": plan["entry"]["trigger"],
            "entry_zone": plan["entry"]["zone"],
            "stop": plan["stop"],
            "targets": plan["targets"],
            "confidence": plan["strategy"],
            "rr_first": plan["targets"][0]["rr"] if plan.get("targets") else None,
        }
        final_ranked.append(r)

    logger.info(
        "[Intraday Summary] start=%d | fetch_skip=%d | gate_fail=%d | level_fail=%d | break_fail=%d | final_pass=%d",
        dbg_counts["start"], dbg_counts["fetch_skip"], dbg_counts["gate_fail"], dbg_counts["level_fail"], dbg_counts["break_fail"], dbg_counts["final_pass"]
    )
    logger.info(f"✅ Prepared {len(final_ranked)} ranked picks with plans")
    return final_ranked
