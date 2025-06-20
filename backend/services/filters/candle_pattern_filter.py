# @role: Detects bullish candlestick patterns like hammer, engulfing etc.
# @used_by: project_map.py
# @filter_type: utility
# @tags: filter, candle, pattern
def is_bullish_engulfing(df):
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    return (
        prev['close'] < prev['open'] and  # previous was red
        curr['close'] > curr['open'] and  # current is green
        curr['close'] > prev['open'] and
        curr['open'] < prev['close']
    )

def is_hammer(df):
    if len(df) < 1:
        return False
    candle = df.iloc[-1]
    body = abs(candle['close'] - candle['open'])
    lower_wick = candle['open'] - candle['low'] if candle['open'] > candle['close'] else candle['close'] - candle['low']
    upper_wick = candle['high'] - max(candle['close'], candle['open'])

    return (
        lower_wick > 2 * body and  # long lower shadow
        upper_wick < body and      # small upper shadow
        body > 0                   # non-doji body
    )