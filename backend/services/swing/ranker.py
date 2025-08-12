from typing import List, Dict

def _swing_strength(iv: Dict) -> float:
    rsi       = float(iv.get('rsi', 0) or 0)
    rsi_slope = float(iv.get('rsi_slope', 0) or 0)
    adx       = float(iv.get('adx', 0) or 0)
    adx_slope = float(iv.get('adx_slope', 0) or 0)

    s_rsi  = max((rsi - 50.0) / 20.0, -0.5)             # -0.5 to 1.0
    s_rsis = max(min(rsi_slope, 0.5), 0.0)              # 0 to 0.5
    s_adx  = max((adx - 20.0) / 20.0, -0.5)             # -0.5 to 1.0
    s_adxs = max(min(adx_slope, 0.5), 0.0)              # 0 to 0.5

    return s_rsi + s_rsis + s_adx + s_adxs

def rank_candidates(rows: List[Dict], top_n: int = 10) -> List[Dict]:
    for r in rows:
        iv = r.get('swing', {}) or {}
        r['swing_score'] = _swing_strength(iv)
        r['rank_score'] = 0.5 * float(r.get('daily_score', 0.0)) + 0.5 * r['swing_score']

    rows.sort(key=lambda x: x.get('rank_score', 0.0), reverse=True)
    return rows[:top_n]
