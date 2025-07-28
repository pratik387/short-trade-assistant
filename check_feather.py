import pandas as pd
df = pd.read_feather("C:/Users/pratikhegde/OneDrive - Nagarro/Desktop/Pratik/short-trade-assistant/backend/backtesting/ohlcv_archive/KALYANKJIL.NS/KALYANKJIL.NS_1d_2022-01-01_2025-07-14.feather")
print(df.head(3))
print(df.tail(3))
print(df["date"].min(), df["date"].max())