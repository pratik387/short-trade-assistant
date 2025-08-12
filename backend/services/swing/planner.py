from dataclasses import dataclass
from typing import Tuple, List

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
    return max(level_px * 0.0015, atr_proxy * 0.30)

def _risk(mid_entry: float, stop: float) -> float:
    return max(0.05, mid_entry - stop)  # never let risk collapse to zero

def plan_trade(df, symbol):
    try:
        last = df.iloc[-1]
        close = float(last["close"])

        # Volatility proxy (ATR-style) using past few bars
        atr_proxy = df['high'].rolling(5).max().iloc[-1] - df['low'].rolling(5).min().iloc[-1]
        atr_proxy = max(0.1, atr_proxy)

        # Use recent swing high as breakout level
        lookback = 15
        recent_high = df['high'].iloc[-lookback:].max()
        entry_pad = _pad(recent_high, atr_proxy)
        entry_lo = _round2(recent_high + entry_pad)
        entry_hi = _round2(recent_high + entry_pad * 1.5)

        # Use recent swing low as stop
        recent_low = df['low'].iloc[-lookback:].min()
        stop = _round2(recent_low - _pad(recent_low, atr_proxy))

        mid_entry = (entry_lo + entry_hi) / 2
        risk = _risk(mid_entry, stop)

        # Targets = reward based on risk
        t1 = _round2(entry_lo + risk * 1.5)
        t2 = _round2(entry_lo + risk * 2.5)

        rr_first = (t1 - mid_entry) / risk
        conf = max(min((rr_first - 1.3), 1), 0) * 100

        return Plan(
            entry_note="Buy on breakout above recent resistance; avoid choppy range",
            entry_zone=(entry_lo, entry_hi),
            stop=stop,
            targets=[t1, t2],
            confidence=_round2(conf),
            rr_first=_round2(rr_first),
        ).__dict__

    except Exception as e:
        return Plan(
            entry_note=f"Failed to compute plan: {e}",
            entry_zone=(0, 0),
            stop=0,
            targets=[],
            confidence=0,
            rr_first=0,
        ).__dict__
