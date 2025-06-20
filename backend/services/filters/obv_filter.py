# @role: Calculates On-Balance Volume (OBV) for volume trend
# @used_by: technical_analysis.py, technical_analysis_exit.py
# @filter_type: utility
# @tags: indicator, obv, volume
import pandas as pd

def calculate_obv(df):
    df = df.copy()
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i - 1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['obv'] = obv
    return df[['obv']]