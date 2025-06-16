def adx_macd_gate(df, fallback=True):
    adx = df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else None
    macd = df["MACD"].iloc[-1] if "MACD" in df.columns else None
    macd_signal = df["MACD_Signal"].iloc[-1] if "MACD_Signal" in df.columns else None

    if None in (adx, macd, macd_signal):
        return fallback, "Missing ADX or MACD values"
    if adx >= 25 and macd >= macd_signal:
        return False, f"Strong trend (ADX={adx:.2f}, MACD={macd:.2f} > Signal={macd_signal:.2f})"
    return True, ""
