import pandas as pd

df = pd.read_feather("C:/Users/pratikhegde/OneDrive - Nagarro/Desktop/Pratik/short-trade-assistant/backend/cache/swing_ohlcv_cache/ADANIENT.NS/ADANIENT.NS_day.feather")

print(df.info())
print(df.tail(3))
print("Latest date:", df["date"].max())