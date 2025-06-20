# @role: Exit signal based on On-Balance Volume (OBV) divergence
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, obv, volume
def obv_exit_filter(df) -> tuple[bool, str]:
    if "obv" in df.columns and df["obv"].iloc[-1] < df["obv"].iloc[-2]:
        return True, "Falling OBV"
    return False, ""