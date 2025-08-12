def compute_levels_swing(df):
    try:
        # Use past 20 bars for level analysis
        recent = df.tail(20)

        high = recent['high'].max()
        low = recent['low'].min()
        close = df['close'].iloc[-1]

        # Calculate resistance and support zones using recent highs/lows
        resistance_zone = (round(high * 0.995, 2), round(high * 1.01, 2))
        support_zone = (round(low * 0.99, 2), round(low * 1.005, 2))

        # Mid-level between high and low
        mid = round((high + low) / 2, 2)

        return {
            "support_zone": support_zone,
            "resistance_zone": resistance_zone,
            "mid_level": mid,
            "is_close_near_resistance": close >= resistance_zone[0],
            "is_close_near_support": close <= support_zone[1],
        }

    except Exception as e:
        return {
            "support_zone": (0, 0),
            "resistance_zone": (0, 0),
            "mid_level": 0,
            "is_close_near_resistance": False,
            "is_close_near_support": False,
            "error": str(e),
        }