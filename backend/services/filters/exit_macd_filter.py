def macd_exit_filter(df, fallback=True):
    macd = df["MACD"].iloc[-1] if "MACD" in df.columns else None
    macd_signal = df["MACD_Signal"].iloc[-1] if "MACD_Signal" in df.columns else None
    if None in (macd, macd_signal):
        return fallback, "Missing MACD or Signal"
    if macd < macd_signal:
        return True, f"MACD crossover down (MACD={macd:.2f}, Signal={macd_signal:.2f})"
    return False, ""