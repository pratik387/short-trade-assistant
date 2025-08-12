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

def plan_trade(df, symbol):
    try:
        close = float(df['close'].iloc[-1])
        high = df['high']
        low = df['low']

        # Identify recent swing high (resistance)
        swing_highs = high.rolling(3, center=True).apply(lambda x: x.iloc[1] > x.iloc[0] and x.iloc[1] > x.iloc[2] if len(x) == 3 else False).dropna()
        swing_highs = swing_highs[swing_highs > 0]
        swing_indices = swing_highs.index.intersection(df.iloc[-40:].index)
        resistance = high.loc[swing_indices].max() if not swing_indices.empty else high.iloc[-20:].max()

        # Reject setups where resistance is too far from current price
        if resistance > close * 1.05:
            return Plan(
                entry_note=f"Rejected: Resistance ({resistance:.2f}) too far from close ({close:.2f})",
                entry_zone=(0, 0), stop=0, targets=[], confidence=0, rr_first=0
            ).__dict__

        # Entry = resistance + buffer
        buffer = max(0.005 * resistance, 0.3)  # 0.5% buffer or ₹0.3 min
        entry_lo = _round2(resistance + buffer)
        entry_hi = _round2(resistance + buffer * 1.5)
        mid_entry = (entry_lo + entry_hi) / 2

        # Stop = recent swing low or support zone below consolidation
        recent_support = low.iloc[-20:].min()
        stop = _round2(recent_support - buffer)
        risk = max(0.05, mid_entry - stop)

        # Target 1 = prior major high (last visible resistance before breakdown)
        earlier_highs = high.iloc[:-40]  # older highs for target reference
        target1 = earlier_highs.max() if not earlier_highs.empty else entry_lo + risk * 1.5

        # Target 2 = fib extension of prior swing
        last_swing_low = low.iloc[-40:].min()
        swing_move = resistance - last_swing_low
        target2 = resistance + 1.618 * swing_move

        t1 = _round2(max(entry_lo + 0.01, target1))
        t2 = _round2(max(t1 + 0.5, target2))

        rr_first = (t1 - mid_entry) / risk
        conf = max(min((rr_first - 1.3), 1), 0) * 100

        return Plan(
            entry_note="Clean breakout above resistance with fib extension targets",
            entry_zone=(entry_lo, entry_hi),
            stop=stop,
            targets=[t1, t2],
            confidence=_round2(conf),
            rr_first=_round2(rr_first)
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
