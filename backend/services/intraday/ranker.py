# services/intraday/ranker.py
from __future__ import annotations
from typing import List, Dict

def _intraday_strength(iv: Dict) -> float:
    """
    Heuristic intraday strength score.
    Tunables are conservative; we can calibrate after paper tests.
    """
    vol_ratio = float(iv.get('volume_ratio', 0) or 0)
    rsi       = float(iv.get('rsi', 0) or 0)
    rsi_slope = float(iv.get('rsi_slope', 0) or 0)
    adx       = float(iv.get('adx', 0) or 0)
    adx_slope = float(iv.get('adx_slope', 0) or 0)
    above_vwap = 1 if iv.get('above_vwap', 0) else 0
    dist_bpct = float(iv.get('dist_from_level_bpct', 9.99) or 9.99)

    # Components (caps keep outliers tame)
    s_vol  = min(vol_ratio / 2.0, 1.2)                  # 0..1.2
    s_rsi  = max((rsi - 50.0) / 20.0, -0.5)             # -0.5..1.0
    s_rsis = max(min(rsi_slope, 0.8), 0.0)              # 0..0.8
    s_adx  = max((adx - 18.0) / 20.0, -0.5)             # -0.5..1.0
    s_adxs = max(min(adx_slope, 0.8), 0.0)              # 0..0.8
    s_vwap = 0.3 if above_vwap else -0.3

    # Prefer near level (<=0.6%); mildly OK up to 1.0%; penalize farther
    if 0.0 <= dist_bpct <= 0.6:
        s_dist = 0.4
    elif dist_bpct <= 1.0:
        s_dist = 0.1
    else:
        s_dist = -0.3

    return s_vol + s_rsi + s_rsis + s_adx + s_adxs + s_vwap + s_dist

def rank_candidates(rows: List[Dict], top_n: int = 7) -> List[Dict]:
    """
    Mutates rows to include 'intraday_score' and 'rank_score', then returns top N.
    """
    for r in rows:
        iv = r.get('intraday', {}) or {}
        r['intraday_score'] = _intraday_strength(iv)
        r['rank_score'] = 0.6 * float(r.get('daily_score', 0.0)) + 0.4 * r['intraday_score']

    rows.sort(key=lambda x: x.get('rank_score', 0.0), reverse=True)
    return rows[:top_n]
