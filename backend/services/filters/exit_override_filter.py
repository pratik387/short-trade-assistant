def check_overrides(df, ma_short=20, ma_long=50, rsi_lower=50):
    short_ma = df["close"].rolling(ma_short).mean().iloc[-1]
    long_ma = df["close"].rolling(ma_long).mean().iloc[-1]
    rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else None

    if short_ma < long_ma:
        return True, "MA crossdown override triggered"
    if rsi and rsi < rsi_lower:
        return True, f"RSI dropped below {rsi_lower} (current: {rsi:.2f})"
    return False, ""
