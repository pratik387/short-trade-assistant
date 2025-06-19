def fibonacci_exit_filter(df) -> tuple[bool, str]:
    if "fibonacci_resistance" not in df.columns or "close" not in df.columns:
        return False, ""
    close = df["close"].iloc[-1]
    resistance = df["fibonacci_resistance"].iloc[-1]
    if close >= resistance * 0.99:
        return True, "Price near Fibonacci resistance"
    return False, ""