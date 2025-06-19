def obv_exit_filter(df) -> tuple[bool, str]:
    if "obv" in df.columns and df["obv"].iloc[-1] < df["obv"].iloc[-2]:
        return True, "Falling OBV"
    return False, ""
