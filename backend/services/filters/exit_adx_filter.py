# @role: Exit rule based on ADX strength and trend direction
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, adx, trend
def adx_exit_filter(df, fallback=True):
    adx = df["ADX_14"].iloc[-1] if "ADX_14" in df.columns else None
    if adx is None:
        return fallback, "Missing ADX value"
    if adx < 30:
        return True, f"ADX below threshold (ADX={adx:.2f})"
    return False, ""