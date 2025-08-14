# services/intraday_screener.py
from datetime import datetime, timedelta, time as dt_time
import threading
import time
import os
from typing import List

import pandas as pd

from config.logging_config import get_loggers
from services.indicator_enrichment_service import compute_intraday_breakout_score
from util.util import get_previous_trading_day

# helpers you already have in separate files
from services.intraday.levels import (
    opening_range,
    yesterday_levels,    # used only in rare fallback
    broke_above,
    distance_bpct,
)
from services.intraday.ranker import rank_candidates
# from services.intraday.planner import make_plan
from services.intraday.planner_internal import generate_trade_plan

logger, _ = get_loggers()

# -------------------- Rate limiter (for REST fetches) --------------------
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
    return broker.fetch_candles(
        symbol=symbol, interval="5minute", from_date=from_date, to_date=to_date
    )

def rate_limited_fetch_daily(symbol, broker, lookback_days=5):
    """Tiny DAILY fallback for y-high if cache missing."""
    _rate_limit()
    to_date = datetime.now()
    from_date = to_date - timedelta(days=lookback_days + 3)
    return broker.fetch_candles(
        symbol=symbol, interval="day", from_date=from_date, to_date=to_date
    )

# -------------------- Daily cache helper (cache → broker → ORB fallback) --------------------
# cache/swing_ohlcv_cache/<SYMBOL>/<SYMBOL>_day.feather
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # -> backend/
_CACHE_ROOT = os.path.join(_BASE_DIR, "cache", "swing_ohlcv_cache")

def _daily_cache_path(symbol: str) -> str:
    return os.path.abspath(os.path.join(_CACHE_ROOT, symbol, f"{symbol}_day.feather"))

def get_yesterday_levels_from_cache(symbol: str):
    """
    Returns (y_high, y_low) from daily Feather cache, or (nan, nan) if missing.
    Assumes columns: date, open, high, low, close, volume.
    """
    try:
        path = _daily_cache_path(symbol)
        if not os.path.exists(path):
            return float("nan"), float("nan")
        df = pd.read_feather(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        else:
            df = df.sort_index()
            if "date" not in df.columns:
                df = df.reset_index().rename(columns={"index": "date"})
                df["date"] = pd.to_datetime(df["date"])
        if len(df) < 2:
            return float("nan"), float("nan")
        latest_day = df["date"].iloc[-1].date()
        today = datetime.now().date()
        prev_row = df.iloc[-2] if latest_day == today else df.iloc[-1]
        return float(prev_row["high"]), float(prev_row["low"])
    except Exception:
        return float("nan"), float("nan")

# =====================================================================
# ============ Single-path Phase‑1: rank + plans output ===============
# =====================================================================

def screen_and_rank_intraday_candidates(
    suggestions,
    broker,
    config,
    top_n=7,
    *,
    override_from_date: datetime | None = None,
    override_to_date: datetime | None = None,
) -> List[dict]:
    """
    Phase‑1 (REST‑only):
      1) fetch last ~60 mins of 5m bars
      2) compute intraday features (RSI/ADX/VWAP/volume/etc.) on CLOSED bars
      3) lenient gate: price > vwap AND volume_ratio >= 1.3
      4) require break of (Yesterday High from cache → broker → ORB‑15) with buffer
      5) rank by 0.6*daily_score + 0.4*intraday_strength
      6) attach a deterministic plan (entry zone, stop, targets)
    Returns top N rows, JSON‑ready.
    """
    logger.info("🔍 [Intraday] Phase‑1 screen+rank (REST‑only) starting…")

    rows = []

    # time window like before
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
    
    # ✅ apply overrides individually (don’t tie them together)
    if override_to_date is not None:
        to_date = override_to_date
    if override_from_date is not None:
        from_date = override_from_date

    gate_cfg = config.get("intraday_gate")
    min_vr = float(gate_cfg.get("min_volume_ratio"))
    require_above_vwap = bool(gate_cfg.get("require_above_vwap"))

    # Debug counters
    dbg_counts = {
        "start": 0,
        "fetch_skip": 0,
        "gate_fail": 0,
        "level_fail": 0,
        "break_fail": 0,
        "final_pass": 0,
    }

    for s in suggestions:
        sym = s.get("symbol")
        if not sym:
            continue
        dbg_counts["start"] += 1
        try:
            logger.info(f"— ▶️ {sym}: fetching 5m {from_date} → {to_date}")
            df5 = rate_limited_fetch_5m(sym, broker, from_date, to_date)
            if df5 is None or df5.empty or len(df5) < 6:
                dbg_counts["fetch_skip"] += 1
                logger.debug(f"— ⛔ {sym}: insufficient 5m bars (have={0 if df5 is None else len(df5)})")
                continue

            df5 = compute_intraday_breakout_score(df5, config, symbol=sym, mode="normal")
            last = df5.iloc[-1]

            # ----------------- Lenient gate -----------------
            vr = float(last.get("volume_ratio", 0) or 0)
            above = int(last.get("above_vwap", 0) or 0)
            
            close_px = float(last.get("close", float('nan')))
            vwap_px = float(last.get("vwap", float('nan')))
            if pd.notna(vwap_px):
                vwap_str = f"{vwap_px:.2f}"
            else:
                vwap_str = "nan"

            logger.debug(
                f"— 🔎 {sym}: VR={vr:.2f} | above_vwap={above} | close={close_px:.2f} | vwap={vwap_str}"
            )
            
            relax_vwap_bpct = float(gate_cfg.get("vwap_relax_bpct", 0.2))  # 0.2% default buffer

            vwap_check = True
            if require_above_vwap:
                if pd.notna(vwap_px) and close_px >= vwap_px * (1 - relax_vwap_bpct / 100):
                    vwap_check = True
                else:
                    vwap_check = False

            if not (vr >= min_vr and vwap_check):
                dbg_counts["gate_fail"] += 1
                logger.debug(f"— ⛔ {sym}: gate fail (VR={vr:.2f} < {min_vr} or close not within {relax_vwap_bpct:.2f}% of VWAP)")
                continue


            # ----------------- Level selection -----------------
            y_hi, _y_lo = get_yesterday_levels_from_cache(sym)
            level_px = y_hi
            chosen_level_name = "y_high(cache)"

            if not (level_px == level_px):  # NaN check
                logger.debug(f"— ℹ️ {sym}: y_high cache missing; trying broker daily…")
                dfd = rate_limited_fetch_daily(sym, broker, lookback_days=5)
                if dfd is not None and not dfd.empty:
                    try:
                        y2_hi, _ = yesterday_levels(dfd)
                        level_px = y2_hi
                        chosen_level_name = "y_high(broker)"
                    except Exception:
                        dfd = dfd.copy()
                        if "date" in dfd.columns:
                            dfd["date"] = pd.to_datetime(dfd["date"])
                            dfd = dfd.sort_values("date")
                        if len(dfd) >= 2:
                            level_px = float(dfd.iloc[-2]["high"])
                            chosen_level_name = "y_high(broker-manual)"
                        else:
                            level_px = float("nan")

            if not (level_px == level_px):  # still NaN → ORB fallback
                logger.info(f"— ℹ️ {sym}: y_high unavailable; using ORB‑15 fallback…")
                orb_hi, _ = opening_range(df5)
                level_px = orb_hi
                chosen_level_name = "orb15_high"

            if pd.isna(level_px):
                dbg_counts["level_fail"] += 1
                logger.info(f"— ⛔ {sym}: level selection failed (NaN after fallbacks)")
                continue

            logger.info(f"— 📏 {sym}: level={chosen_level_name} @ {level_px:.2f}")

            # ----------------- Breakout check -----------------
            if not broke_above(level_px, close_px):
                dist = distance_bpct(level_px, close_px)
                dbg_counts["break_fail"] += 1
                logger.debug(f"— ⛔ {sym}: no break (close={close_px:.2f}, level={level_px:.2f}, dist={dist:.2f}%)")
                continue

            # ----------------- Feature collection for ranking/plan -----------------
            dist = distance_bpct(level_px, close_px)

            adx_val = float(last.get("ADX_ACTIVE", 0) or 0)
            adx_slope = float(last.get("adx_slope", 0) or 0)

            rsi_val = float(last.get("RSI", 0) or 0)
            rsi_slope = float(last.get("rsi_slope", 0) or 0)

            # ATR-like proxy: mean of last 5 ranges (robust for planning)
            try:
                atr_proxy = float((df5["high"] - df5["low"]).rolling(5).mean().iloc[-1])
                if pd.isna(atr_proxy):
                    atr_proxy = float((df5["high"] - df5["low"]).tail(5).mean())
            except Exception:
                atr_proxy = 0.0

            rows.append(
                {
                    "symbol": sym,
                    "daily_score": float(s.get("score", 0.0)),
                    "level": {
                        "name": chosen_level_name,
                        "px": float(level_px),
                    },
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
                    "vwap": float(last.get("vwap", float("nan"))),
                    "atr5": float(atr_proxy or 0.0),
                    "df": df5,
                }
            )
            dbg_counts["final_pass"] += 1
            logger.info(f"— ✅ {sym}: PASSED gate+break | ADX={adx_val:.2f} (slope {adx_slope:.2f}), RSI={rsi_val:.2f} (slope {rsi_slope:.2f}), VR={vr:.2f}, dist={dist:.2f}%")

        except Exception as e:
            # We log at info as requested
            logger.info(f"— ⚠️ {sym}: exception, skipping → {e}")

    # ----------------- Rank & attach plans -----------------
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

    # Summary
    logger.info(
        "[Intraday Summary] start=%d | fetch_skip=%d | gate_fail=%d | level_fail=%d | break_fail=%d | final_pass=%d",
        dbg_counts["start"],
        dbg_counts["fetch_skip"],
        dbg_counts["gate_fail"],
        dbg_counts["level_fail"],
        dbg_counts["break_fail"],
        dbg_counts["final_pass"],
    )
    logger.info(f"✅ Prepared {len(final_ranked)} ranked picks with plans")
    return final_ranked
