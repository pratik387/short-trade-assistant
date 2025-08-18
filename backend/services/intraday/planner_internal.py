import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple, Union
from config.logging_config import get_loggers

logger, _ = get_loggers()

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev_close = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_close), np.abs(l - prev_close)))
    atr = pd.Series(tr).rolling(period, min_periods=period).mean().iloc[-1]
    return float(atr)

def get_date_range_from_df(df: pd.DataFrame) -> Tuple[str, str]:
    idx = pd.to_datetime(df.index)
    return (str(idx.min().date()), str(idx.max().date()))

# ----------------------------
# Configuration
# ----------------------------
@dataclass
class PlannerConfig:
    # session/time
    session_start: str = "09:15"   # IST market open (context only)
    session_end: str = "15:30"     # IST market close (context only)
    opening_range_min: int = 30    # ORB window (minutes)

    # data expectations
    bar_minutes: int = 5           # 5-min candles

    # volatility/range context
    atr_period: int = 14
    choppiness_lookback: int = 30
    choppiness_high: float = 61.8  # above => choppy
    choppiness_low: float = 38.2   # below => trending

    # gap handling (context only)
    max_gap_pct_for_trend: float = 3.0

    # entries
    entry_zone_atr_frac: float = 0.15  # width = ATR * frac
    vwap_reclaim_min_bars_above: int = 2

    # stops/targets
    sl_atr_mult: float = 1.25
    sl_below_swing_ticks: float = 0.0
    t1_rr: float = 1.2
    t2_rr: float = 2.0
    trail_to: str = "vwap_or_ema20"

    # position sizing
    risk_per_trade_rupees: float = 500.0
    fees_slippage_bps: float = 5.0  # placeholder

    # lunch window (guardrail note only)
    enable_lunch_pause: bool = True
    lunch_start: str = "12:15"
    lunch_end: str = "13:15"

# ----------------------------
# Utilities
# ----------------------------
def _merge_config_dict(cfg: "PlannerConfig", user_cfg: Dict[str, Any]) -> "PlannerConfig":
    """Merge flat keys directly onto dataclass. Keep nested blobs on cfg._extras."""
    for k, v in user_cfg.items():
        if hasattr(cfg, k) and not isinstance(getattr(cfg, k), (dict, list)):
            try:
                setattr(cfg, k, v)
            except Exception:
                pass
    extras_keys = [
        "intraday_gate", "late_entry_penalty", "entry_filters", "intraday_params",
        "swing_gate", "swing_params", "minimum_holding_days", "enable_soft_prefilter",
        "planner_precision", "acceptance",
    ]
    cfg._extras = {k: user_cfg.get(k) for k in extras_keys if k in user_cfg}
    return cfg

def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    if "date" not in out.columns:
        out["date"] = out.index.normalize()
    return out

def _session_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return the latest trading session slice present in df."""
    df = _ensure_datetime_index(df)
    latest_day = df["date"].iloc[-1]
    return df[df["date"] == latest_day]

def _opening_range(df_sess: pd.DataFrame, cfg: PlannerConfig) -> Tuple[float, float, pd.Timestamp]:
    start_ts = df_sess.index.min()
    or_end = start_ts + pd.Timedelta(minutes=cfg.opening_range_min)
    or_df = df_sess.loc[(df_sess.index >= start_ts) & (df_sess.index < or_end)]
    return float(or_df["high"].max()), float(or_df["low"].min()), or_end

def _session_vwap(df_sess: pd.DataFrame) -> pd.Series:
    tp = (df_sess["high"] + df_sess["low"] + df_sess["close"]) / 3.0
    cum_pv = (tp * df_sess["volume"]).cumsum()
    cum_v = df_sess["volume"].cumsum().replace(0, np.nan)
    return cum_pv / cum_v

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    s = series.astype(float)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return {"line": macd_line, "signal": signal_line, "hist": hist}

def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    up = h.diff()
    down = -l.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
    adx = dx.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return adx.bfill()

def _choppiness_index(df_sess: pd.DataFrame, lookback: int) -> float:
    # CHOP = 100 * log10(sum(TR) / (max(High)-min(Low))) / log10(n)
    h, l, c = df_sess["high"], df_sess["low"], df_sess["close"]
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    window = tr.tail(lookback)
    if len(window) < lookback or (window.sum() == 0):
        return 100.0
    hh = h.tail(lookback).max()
    ll = l.tail(lookback).min()
    denom = np.log10(lookback)
    numer = np.log10(window.sum() / max(hh - ll, 1e-9))
    return float(100.0 * numer / denom)

def _pivot_swing_low(df_sess: pd.DataFrame, lookback: int = 10) -> float:
    lows = df_sess["low"].tail(lookback + 2)
    return float(lows.min())

def _pivot_swing_high(df_sess: pd.DataFrame, lookback: int = 10) -> float:
    highs = df_sess["high"].tail(lookback + 2)
    return float(highs.max())

def _prev_day_levels(df: pd.DataFrame) -> Dict[str, float]:
    if df is None or df.empty:
        return {"PDH": None, "PDL": None, "PDC": None}
    df = _ensure_datetime_index(df)
    last_day = df["date"].iloc[-1]
    prev_df = df[df["date"] < last_day]
    if prev_df.empty:
        return {"PDH": np.nan, "PDL": np.nan, "PDC": np.nan}
    prev_day = prev_df["date"].iloc[-1]
    day_df = prev_df[prev_df["date"] == prev_day]
    return {
        "PDH": float(day_df["high"].max()),
        "PDL": float(day_df["low"].min()),
        "PDC": float(day_df["close"].iloc[-1]),
    }

def _regime(df_sess: pd.DataFrame, cfg: PlannerConfig) -> str:
    chop = _choppiness_index(df_sess, cfg.choppiness_lookback)
    ema20 = _ema(df_sess["close"], 20)
    ema50 = _ema(df_sess["close"], 50)
    slope = (ema20.iloc[-1] - ema20.iloc[-5]) / max(abs(ema20.iloc[-5]), 1e-9)

    if chop <= cfg.choppiness_low and ema20.iloc[-1] > ema50.iloc[-1] and slope > 0:
        return "trend_up"
    if chop <= cfg.choppiness_low and ema20.iloc[-1] < ema50.iloc[-1] and slope < 0:
        return "trend_down"
    if chop >= cfg.choppiness_high:
        return "choppy"
    return "range"

def _strategy_selector(
    df_sess: pd.DataFrame,
    cfg: PlannerConfig,
    regime: str,
    orh: float, orl: float, or_end: pd.Timestamp,
    vwap: pd.Series,
    pd_levels: Dict[str, float]
) -> Dict[str, Any]:
    last = df_sess.iloc[-1]
    close = float(last["close"])

    ema20 = _ema(df_sess["close"], 20)
    ema50 = _ema(df_sess["close"], 50)

    # Strategy 1: ORB Pullback Long (trend_up)
    if regime == "trend_up" and close > orh and close > vwap.iloc[-1] and ema20.iloc[-1] > ema50.iloc[-1]:
        basis = "orb_pullback_long"
        stop_structure = max(orl, _pivot_swing_low(df_sess, 12))
        return {
            "name": basis,
            "bias": "long",
            "entry_trigger": f"pullback to ~ORH({orh:.2f}) with hold above VWAP",
            "structure_stop": float(stop_structure),
            "context": {
                "reason": ["trend_up", "above_ORH", "above_VWAP", "ema20>ema50"],
                "levels": {"ORH": orh, "ORL": orl, **pd_levels}
            }
        }

    # Strategy 2: VWAP Reclaim Long (range->up or choppy exit)
    if close > vwap.iloc[-1] and df_sess["close"].tail(cfg.vwap_reclaim_min_bars_above).gt(
        vwap.tail(cfg.vwap_reclaim_min_bars_above)
    ).all():
        basis = "vwap_reclaim_long"
        stop_structure = _pivot_swing_low(df_sess, 8)
        return {
            "name": basis,
            "bias": "long",
            "entry_trigger": "reclaim VWAP with 2+ closes above, enter on minor dip",
            "structure_stop": float(stop_structure),
            "context": {"reason": ["VWAP_reclaim"], "levels": {"ORH": orh, "ORL": orl, **pd_levels}}
        }
        
    # Strategy 2b: PDH Break + Hold Long
    if close > pd_levels.get("PDH", float("inf")) and close > vwap.iloc[-1] and ema20.iloc[-1] > ema50.iloc[-1]:
        basis = "pdh_break_hold_long"
        stop_structure = max(orl, _pivot_swing_low(df_sess, 10))
        return {
            "name": basis, "bias": "long",
            "entry_trigger": f"retest/hold above PDH({pd_levels['PDH']:.2f})",
            "structure_stop": float(stop_structure),
            "context": {"reason": ["above_PDH","above_VWAP","ema20>ema50"], "levels": {"ORH": orh, "ORL": orl, **pd_levels}}
        }

    # Strategy 3b: PDL Break + Hold Short
    if close < pd_levels.get("PDL", float("-inf")) and close < vwap.iloc[-1] and ema20.iloc[-1] < ema50.iloc[-1]:
        basis = "pdl_break_hold_short"
        stop_structure = min(orh, _pivot_swing_high(df_sess, 10))
        return {
            "name": basis, "bias": "short",
            "entry_trigger": f"retest/hold below PDL({pd_levels['PDL']:.2f})",
            "structure_stop": float(stop_structure),
            "context": {"reason": ["below_PDL","below_VWAP","ema20<ema50"], "levels": {"ORH": orh, "ORL": orl, **pd_levels}}
        }

    # Strategy 3: Range Break + Retest Short (trend_down)
    if regime == "trend_down" and close < orl and close < vwap.iloc[-1] and ema20.iloc[-1] < ema50.iloc[-1]:
        basis = "range_break_retest_short"
        stop_structure = min(orh, _pivot_swing_high(df_sess, 12))
        return {
            "name": basis,
            "bias": "short",
            "entry_trigger": f"retest of ~ORL({orl:.2f}) rejecting under VWAP",
            "structure_stop": float(stop_structure),
            "context": {
                "reason": ["trend_down", "below_ORL", "below_VWAP", "ema20<ema50"],
                "levels": {"ORH": orh, "ORL": orl, **pd_levels}
            }
        }

    # Fallback: No clean setup now
    return {
        "name": "no_setup",
        "bias": "flat",
        "entry_trigger": "wait",
        "structure_stop": np.nan,
        "context": {"reason": ["no_clear_edge"], "levels": {"ORH": orh, "ORL": orl, **pd_levels}}
    }

def _compose_exits_and_size(
    price: float, bias: str, atr: float, structure_stop: float, cfg: PlannerConfig, qty_scale: float = 1.0
) -> Dict[str, Any]:
    # extras for planner precision
    pp = getattr(cfg, "_extras", {}).get("planner_precision", {}) if hasattr(cfg, "_extras") else {}
    min_tick = float(pp.get("min_tick", 0.05))

    if np.isnan(structure_stop):
        return {"eligible": False, "reason": "no_structure_stop"}

    fallback_zone = False
    if np.isnan(atr) or atr == 0.0:
        logger.warning(f"⚠️ ATR unavailable for price={price}, using fallback")
        atr = price * 0.005
        fallback_zone = True

    vol_stop = price - cfg.sl_atr_mult * atr if bias == "long" else price + cfg.sl_atr_mult * atr
    if bias == "long":
        hard_sl = max(structure_stop - cfg.sl_below_swing_ticks, vol_stop)
        risk_per_share = max(price - hard_sl, 0.0)
    else:
        hard_sl = min(structure_stop + cfg.sl_below_swing_ticks, vol_stop)
        risk_per_share = max(hard_sl - price, 0.0)

    # tick-size guard
    if risk_per_share < min_tick:
        return {
            "eligible": False,
            "reason": f"risk_below_tick<{min_tick}",
            "risk_per_share": round(risk_per_share, 4),
            "hard_sl": round(hard_sl, 2),
            "targets": [],
            "trail": cfg.trail_to,
            "entry_zone": None,
            "qty": 0,
            "notional": 0.0,
        }

    base_qty = max(int(cfg.risk_per_trade_rupees // risk_per_share), 0)
    qty = max(int(base_qty * qty_scale), 0)
    notional = qty * price

    t1 = price + (cfg.t1_rr * risk_per_share) if bias == "long" else price - (cfg.t1_rr * risk_per_share)
    t2 = price + (cfg.t2_rr * risk_per_share) if bias == "long" else price - (cfg.t2_rr * risk_per_share)

    # Entry zone
    if fallback_zone:
        entry_zone = [round(price - 0.01, 2), round(price, 2)]
    else:
        entry_width = max(atr * cfg.entry_zone_atr_frac, 0.01)
        entry_zone = [round(price - entry_width, 2), round(price + entry_width, 2)]

    return {
        "eligible": qty > 0,
        "risk_per_share": round(risk_per_share, 4),
        "qty": int(qty),
        "notional": round(notional, 2),
        "hard_sl": round(hard_sl, 2),
        "targets": [
            {"name": "T1", "level": round(t1, 2), "rr": cfg.t1_rr, "action": "book_30%"},
            {"name": "T2", "level": round(t2, 2), "rr": cfg.t2_rr, "action": "trail_rest"},
        ],
        "trail": cfg.trail_to,
        "entry_zone": entry_zone,
    }

# ----------------------------
# Public API
# ----------------------------
def generate_trade_plan(
    df: pd.DataFrame, symbol: str,
    config: Optional[Union[PlannerConfig, Dict[str, Any]]] = None,
    daily_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """Build an intraday trade plan from a 5-min OHLCV DataFrame.

    Expected df columns: [open, high, low, close, volume]; index should be datetime.
    A 'date' column is created if missing (normalized).
    Assumes **screener** already applied symbol-level gating.
    Returns a dict with 'eligible' flag and complete plan, *without* side effects.
    """
    # Accept dataclass or plain dict
    if isinstance(config, dict):
        cfg = _merge_config_dict(PlannerConfig(), config)
    elif isinstance(config, PlannerConfig) or config is None:
        cfg = config or PlannerConfig()
        cfg._extras = {}
    else:
        cfg = PlannerConfig(); cfg._extras = {}

    df = _ensure_datetime_index(df)

    # Focus on the latest session available
    sess = _session_df(df)
    if len(sess) < max(20, cfg.opening_range_min // cfg.bar_minutes + 2):
        logger.warning(f"⚠️ {symbol}: very few candles — plan might be weak")


    # Core features
    sess = sess.copy()
    sess["vwap"] = _session_vwap(sess)
    sess["ema20"] = _ema(sess["close"], 20)
    sess["ema50"] = _ema(sess["close"], 50)
    # Optional indicators for soft sizing / checklist
    rsi_len = int(cfg._extras.get("intraday_params", {}).get("rsi_len", 14)) if hasattr(cfg, "_extras") else 14
    adx_len = int(cfg._extras.get("intraday_params", {}).get("adx_len", 14)) if hasattr(cfg, "_extras") else 14
    sess["rsi14"] = _rsi(sess["close"], period=rsi_len)
    sess["adx14"] = _adx(sess, period=adx_len)
    macd_pack = _macd(sess["close"])  # 12/26/9
    sess["macd"] = macd_pack["line"]
    sess["macd_hist"] = macd_pack["hist"]
    sess["vol_avg20"] = sess["volume"].rolling(20, min_periods=1).mean()
    sess["vol_ratio"] = sess["volume"] / sess["vol_avg20"]

    # Context
    atr = calculate_atr(df.tail(200), period=cfg.atr_period)
    orh, orl, or_end = _opening_range(sess, cfg)
    pd_levels = _prev_day_levels(daily_df)

    # Gap context using prev close (annotate only)
    gap_pct = np.nan
    if not np.isnan(pd_levels.get("PDC", np.nan)):
        first_open = float(sess.iloc[0]["open"]) if not sess.empty else np.nan
        if not np.isnan(first_open):
            gap_pct = 100.0 * (first_open - pd_levels["PDC"]) / max(pd_levels["PDC"], 1e-9)

    regime = _regime(sess, cfg)
    strat = _strategy_selector(sess, cfg, regime, orh, orl, or_end, sess["vwap"], pd_levels)

    # Soft sizing / checklist using config extras (NO gating here)
    late_penalty = cfg._extras.get("late_entry_penalty", {}) if hasattr(cfg, "_extras") else {}
    intraday_gate = cfg._extras.get("intraday_gate", {}) if hasattr(cfg, "_extras") else {}

    last = sess.iloc[-1]
    qty_scale = 1.0
    cautions: List[str] = []
    must_checks: List[str] = []
    should_checks: List[str] = []

    # Late entry penalties (overextended momentum -> reduce size)
    rsi_above = late_penalty.get("rsi_above")
    macd_above = late_penalty.get("macd_above")
    if rsi_above is not None and float(last["rsi14"]) > rsi_above:
        qty_scale *= 0.6
        cautions.append(f"late_entry_rsi>{rsi_above}")
    if macd_above is not None and float(last["macd_hist"]) > macd_above:
        qty_scale *= 0.8
        cautions.append(f"late_entry_macd_hist>{macd_above}")

    # Intraday gate snapshot -> must/should checks (not enforced here)
    mv = intraday_gate.get("min_volume_ratio")
    if mv is not None:
        should_checks.append(f"vol_ratio>={mv}")
        if float(last["vol_ratio"]) < mv:
            qty_scale *= 0.8
            cautions.append("weak_volume_ratio")

    if intraday_gate.get("require_above_vwap", True):
        must_checks.append("price_above_vwap" if strat["bias"] == "long" else "price_below_vwap")

    rmin, rmax = intraday_gate.get("min_rsi"), intraday_gate.get("max_rsi")
    if rmin is not None and rmax is not None:
        should_checks.append(f"RSI in [{rmin},{rmax}]")
        rsi_now = float(last["rsi14"])
        if not (rmin <= rsi_now <= rmax):
            qty_scale *= 0.85
            cautions.append("rsi_out_of_band")

    adxmin, adxmax = intraday_gate.get("min_adx"), intraday_gate.get("max_adx")
    if adxmin is not None and adxmax is not None:
        should_checks.append(f"ADX in [{adxmin},{adxmax}]")
        adx_now = float(last["adx14"])
        if not (adxmin <= adx_now <= adxmax):
            qty_scale *= 0.9
            cautions.append("adx_out_of_band")

    if strat["name"] == "no_setup":
        logger.debug(f"❌ {symbol} skipped: no setup")
        return {}

    entry_ref_price = float(sess.iloc[-1]["close"])  # refined by caller
    exits = _compose_exits_and_size(entry_ref_price, strat["bias"], atr, strat["structure_stop"], cfg, qty_scale=qty_scale)
    
    pp = cfg._extras.get("planner_precision") if hasattr(cfg, "_extras") else {}
    measured_move = max(orh - orl, atr) if strat["bias"] in ("long","short") else atr
    rps = float(exits.get("risk_per_share", 1e-6))
    rr_clip_max = float(pp.get("rr_clip_max", 6.0))
    
    # --- target feasibility tightening ---
    t1_max_pct = float(pp.get("t1_max_pct"))
    t1_max_mm_frac = float(pp.get("t1_max_mm_frac"))
    t2_max_pct = float(pp.get("t2_max_pct"))
    t2_max_mm_frac = float(pp.get("t2_max_mm_frac"))

    def _cap_move(max_pct, max_mm_frac):
        return min(entry_ref_price * (max_pct / 100.0), measured_move * max_mm_frac)

    cap1 = _cap_move(t1_max_pct, t1_max_mm_frac)
    cap2 = _cap_move(t2_max_pct, t2_max_mm_frac)

    t1_orig = exits["targets"][0]["level"] if exits.get("targets") else np.nan
    t2_orig = exits["targets"][1]["level"] if exits.get("targets") and len(exits["targets"]) > 1 else np.nan

    if strat["bias"] == "long":
        t1_feasible = entry_ref_price + min(max(t1_orig - entry_ref_price, 0.0), cap1)
        t2_feasible = entry_ref_price + min(max(t2_orig - entry_ref_price, 0.0), cap2)
    else:  # short
        t1_feasible = entry_ref_price - min(max(entry_ref_price - t1_orig, 0.0), cap1)
        t2_feasible = entry_ref_price - min(max(entry_ref_price - t2_orig, 0.0), cap2)

    # Minimum epsilon to avoid div/0. Use ATR if available; else 0.1% of price or 0.01 absolute.
    eps = max(entry_ref_price * 0.001, 0.01)
    try:
        if (not rps) or rps <= 0:
            atr_col = "atr5" if "atr5" in df.columns else ("ATR" if "ATR" in df.columns else None)
            if atr_col is not None:
                atr_val = float(df[atr_col].iloc[-1])
                rps = max(abs(atr_val) * 0.25, eps)
            else:
                rps = eps
    except Exception:
        rps = eps
    
    t1_rr_eff = (t1_feasible - entry_ref_price) / rps if strat["bias"] == "long" else (entry_ref_price - t1_feasible) / rps
    t2_rr_eff = (t2_feasible - entry_ref_price) / rps if strat["bias"] == "long" else (entry_ref_price - t2_feasible) / rps

    # write back
    if exits.get("targets"):
        exits["targets"][0]["level"] = round(float(t1_feasible), 2)
        exits["targets"][0]["rr"] = round(float(t1_rr_eff), 2)
    if exits.get("targets") and len(exits["targets"]) > 1:
        exits["targets"][1]["level"] = round(float(t2_feasible), 2)
        exits["targets"][1]["rr"] = round(float(t2_rr_eff), 2)

    
    if strat["bias"] == "long":
        next_objective = orh + 0.5 * measured_move
        structural_rr = (next_objective - entry_ref_price) / max(rps, 1e-6)
    elif strat["bias"] == "short":
        next_objective = orl - 0.5 * measured_move
        structural_rr = (entry_ref_price - next_objective) / max(rps, 1e-6)
    else:
        next_objective = float("nan")
        structural_rr = float("nan")

    if not np.isnan(structural_rr):
        structural_rr = float(np.clip(structural_rr, 0.0, rr_clip_max))

    acc_cfg = cfg._extras.get("acceptance") if hasattr(cfg, "_extras") else {}
    acc_bars = int(acc_cfg.get("bars"))
    acc_bpct = float(acc_cfg.get("retest_bpct"))
    need_vwap = bool(acc_cfg.get("need_vwap_hold"))

    _lvl = orh if strat["bias"] == "long" else orl
    win = sess.tail(max(acc_bars, 2))

    if strat["bias"] == "long":
        # low did NOT violate more than acc_bpct below level
        retest_ok = (win["low"].min() >= _lvl * (1 - acc_bpct/100.0))
        hold_ok = (win["close"].iloc[-1] >= _lvl) and (not need_vwap or win["close"].iloc[-1] >= win["vwap"].iloc[-1])
    elif strat["bias"] == "short":
        # high did NOT violate more than acc_bpct above level
        retest_ok = (win["high"].max() <= _lvl * (1 + acc_bpct/100.0))
        hold_ok = (win["close"].iloc[-1] <= _lvl) and (not need_vwap or win["close"].iloc[-1] <= win["vwap"].iloc[-1])
    else:
        retest_ok = False
        hold_ok  = False

    acceptance_ok = bool(retest_ok and hold_ok)

    start_date, end_date = get_date_range_from_df(df)
    plan = {
        "symbol": symbol,
        "eligible": exits.get("eligible", False),
        "regime": regime,
        "strategy": strat["name"],
        "bias": strat["bias"],
        "entry": {
            "reference": round(entry_ref_price, 2),
            "trigger": strat["entry_trigger"],
            "zone": exits.get("entry_zone"),
            "must": must_checks + (["acceptance_ok"] if acceptance_ok else []),
            "should": should_checks,
            "filters": [
                "above_VWAP" if strat["bias"] == "long" else "below_VWAP",
                "ORB_context",
                "volume_persistency>avg20",
            ],
        },
        "stop": {
            "hard": exits.get("hard_sl"),
            "type": "max(structure,ATR)",
            "structure": None if np.isnan(strat["structure_stop"]) else round(float(strat["structure_stop"]), 2),
        },
        "targets": exits.get("targets", []),
        "trail": exits.get("trail"),
        "sizing": {
            "risk_per_share": exits.get("risk_per_share"),
            "risk_rupees": cfg.risk_per_trade_rupees,
            "qty": exits.get("qty"),
            "notional": exits.get("notional"),
            "qty_scale": round(qty_scale, 2),
        },
        "levels": strat["context"]["levels"],
        "indicators": {
            "vwap": round(float(sess["vwap"].iloc[-1]), 2),
            "ema20": round(float(sess["ema20"].iloc[-1]), 2),
            "ema50": round(float(sess["ema50"].iloc[-1]), 2),
            "atr": round(float(atr), 2),
            "rsi14": round(float(sess["rsi14"].iloc[-1]), 2),
            "adx14": round(float(sess["adx14"].iloc[-1]), 2),
            "macd_hist": round(float(sess["macd_hist"].iloc[-1]), 4),
            "vol_ratio": round(float(sess["vol_ratio"].iloc[-1]), 2),
        },
        "notes": {
            "gap_pct": None if np.isnan(gap_pct) else round(float(gap_pct), 2),
            "opening_range_end": str(or_end),
            "cautions": cautions,
        },
        "guardrails": [
            "avoid_entries <5m before/after lunch window" if cfg.enable_lunch_pause else None,
            "cancel trade after 45m if trigger not met",
        ],
        "date_range": {"start": start_date, "end": end_date},
        "quality": {
            "structural_rr": None if np.isnan(structural_rr) else round(float(structural_rr), 2),
            "acceptance_ok": acceptance_ok,
            "t1_feasible": bool(not np.isnan(t1_orig) and (abs(t1_feasible - t1_orig) < 1e-6 or (abs(t1_feasible - entry_ref_price) <= cap1 + 1e-9))),
            "t2_feasible": bool(not np.isnan(t2_orig) and (abs(t2_feasible - t2_orig) < 1e-6 or (abs(t2_feasible - entry_ref_price) <= cap2 + 1e-9)))
        },

    }
    plan["guardrails"] = [g for g in plan["guardrails"] if g]
    return plan
