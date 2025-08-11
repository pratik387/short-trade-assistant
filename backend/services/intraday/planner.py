# services/intraday/planner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, List
import math

@dataclass
class Plan:
    entry_note: str
    entry_zone: Tuple[float, float]
    stop: float
    targets: List[float]
    confidence: float
    rr_first: float  # R:R to first target

def _round2(x: float) -> float:
    return float(f"{x:.2f}")

def _pad(level_px: float, atr_proxy: float) -> float:
    """
    Buffer above/below level. Use the larger of:
      - 0.15% of level
      - 0.30 * ATR proxy (keeps buffer meaningful for volatile names)
    """
    return max(level_px * 0.0015, atr_proxy * 0.30)

def _risk(mid_entry: float, stop: float) -> float:
    return max(0.05, mid_entry - stop)  # never let risk collapse to zero

def make_plan(level_px: float, last_close: float, atr_proxy: float, vwap: float | float('nan')) -> dict:
    """
    Build a simple, robust plan:
      - Entry = 'retest preferred' zone just above level (pad-scaled)
      - Stop  = min(level - pad, last_close - 1.25*ATR)  (whichever is tighter but sensible)
      - Targets = 1R and 2R from mid-entry
      - Confidence bump if price ~ level and above VWAP

    Args:
      level_px: chosen trigger level (y-high or ORB-15 high)
      last_close: latest close (from 5m/1m)
      atr_proxy: small timeframe ATR-like volatility (can be 5m true ATR or H-L rolling mean)
      vwap: session vwap (nan allowed)

    Returns:
      dict with plan fields ready to serialize
    """
    pad = _pad(level_px, atr_proxy)

    # Entry zone just above level — retest bias
    entry_lo = _round2(level_px + 0.5 * pad)
    entry_hi = _round2(level_px + 1.5 * pad)

    # Stop selection — keep it tight but not silly
    stop1 = level_px - pad
    stop2 = last_close - 1.25 * atr_proxy if atr_proxy > 0 else stop1
    stop  = _round2(min(stop1, stop2))

    # Mid-entry and R multiples
    mid_entry = (entry_lo + entry_hi) / 2.0
    risk = _risk(mid_entry, stop)
    t1 = _round2(mid_entry + 1.0 * risk)
    t2 = _round2(mid_entry + 2.0 * risk)

    # Confidence: base + vwap + proximity to level
    conf = 0.60
    try:
        if not (vwap != vwap):  # nan check
            if last_close > vwap:
                conf += 0.15
    except Exception:
        pass
    if abs((last_close / level_px) - 1.0) <= 0.004:  # within ~0.4%
        conf += 0.15
    conf = min(conf, 0.95)

    return {
        "entry_note": "retest preferred; momentum ok above entry_hi",
        "entry_zone": (entry_lo, entry_hi),
        "stop": stop,
        "targets": [t1, t2],
        "confidence": round(conf, 2),
        "rr_first": round((t1 - mid_entry) / risk, 2)
    }
