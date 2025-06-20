# @role: Stochastic oscillator (%K) filter for momentum reversal
# @used_by: technical_analysis.py
# @filter_type: utility
# @tags: indicator, stochastic, oscillator
def calculate_stochastic(df):
    df = df.copy()
    low_min = df['low'].rolling(window=14).min()
    high_max = df['high'].rolling(window=14).max()
    df['stochastic_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    df['stochastic_k'] = df['stochastic_k'].fillna(0)
    return df[['stochastic_k']]