# @role: Exit logic using Bollinger Band breakout or squeeze
# @used_by: technical_analysis_exit.py
# @filter_type: utility
# @tags: exit, bollinger, range
def bollinger_exit_filter(df) -> tuple[bool, str]:
    if "BB_%B" in df.columns and df["BB_%B"].iloc[-1] > 0.9:
        return True, "Near upper Bollinger Band"
    return False, ""