def rsi_exit_filter(df) -> tuple[bool, str]:
    if "RSI" in df.columns:
        rsi = df["RSI"].iloc[-1]
        if rsi > 70 and df["close"].iloc[-1] < df["close"].iloc[-2]:
            return True, "RSI > 70 with price drop"
    return False, ""
