# @role: Fibonacci support/resistance zone detector
# @used_by: technical_analysis.py, technical_analysis_exit.py
# @filter_type: utility
# @tags: indicator, fibonacci, levels
def calculate_fibonacci_levels(series):
    """
    Given a price series (usually 20-day close), calculate key Fibonacci retracement levels.
    Returns a dictionary with levels: 0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0
    """
    if series.empty or len(series) < 2:
        return {}

    high = series.max()
    low = series.min()
    diff = high - low

    return {
        "0.0": round(high, 2),
        "0.236": round(high - 0.236 * diff, 2),
        "0.382": round(high - 0.382 * diff, 2),
        "0.5": round(high - 0.5 * diff, 2),
        "0.618": round(high - 0.618 * diff, 2),
        "0.786": round(high - 0.786 * diff, 2),
        "1.0": round(low, 2)
    }


def is_fibonacci_support_zone(close_price, levels):
    """
    Check if current close price is near any retracement support level (especially 0.618, 0.5, 0.382).
    A tolerance of 1.5% is considered.
    """
    if not levels or not isinstance(levels, dict):
        return False

    tolerance = 0.015  # 1.5%

    for key in ["0.618", "0.5", "0.382"]:
        level = levels.get(key)
        if level and abs(close_price - level) / close_price <= tolerance:
            return True
    return False