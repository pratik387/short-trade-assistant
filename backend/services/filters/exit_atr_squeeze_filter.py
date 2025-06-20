# @role: Detects low volatility ATR squeeze for early exit trigger
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, atr, volatility
def atr_squeeze_filter(df) -> tuple[bool, str]:
    if "ATR" not in df.columns:
        return False, ""
    atr_range = df["ATR"].iloc[-1] / df["close"].iloc[-1]
    if atr_range < 0.01:
        return True, "ATR squeeze detected"
    return False, ""