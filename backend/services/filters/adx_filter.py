# @role: Calculates ADX and directional movement index
# @used_by: technical_analysis.py, technical_analysis_exit.py
# @filter_type: logic
# @tags: indicator, adx, trend
import pandas as pd
from config.logging_config import get_loggers

logger, trade_logger = get_loggers()


def calculate_adx(df: pd.DataFrame, period: int = 14, strict: bool = True, symbol: str = "") -> pd.DataFrame:
    high, low, close = df['high'], df['low'], df['close']
    if isinstance(high, pd.DataFrame): high = high.squeeze("columns")
    if isinstance(low, pd.DataFrame): low = low.squeeze("columns")
    if isinstance(close, pd.DataFrame): close = close.squeeze("columns")

    plus_dm, minus_dm = high.diff(), low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2, tr3 = abs(high - close.shift()), abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    min_period = period if strict else 10
    atr = tr.ewm(span=period, min_periods=min_period, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(span=period, min_periods=min_period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, min_periods=min_period, adjust=False).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(span=period, min_periods=min_period, adjust=False).mean()

    last_adx, last_dmp, last_dmn = adx.iloc[-1], plus_di.iloc[-1], minus_di.iloc[-1]
    logger.debug(f"[ADX] {symbol} | ADX={last_adx:.2f}, DMP={last_dmp:.2f}, DMN={last_dmn:.2f}")

    return pd.DataFrame({
        'ADX_14': adx,
        'DMP_14': plus_di,
        'DMN_14': minus_di
    }, index=close.index)