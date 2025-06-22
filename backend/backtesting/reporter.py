"""
Generates summary report from trade logs.
"""
import pandas as pd

def generate_report(csv_path="backtesting/test_results/trades.csv"):
    df = pd.read_csv(csv_path)
    df["pnl"] = df["pnl"].astype(float)

    print("Total Trades:", len(df))
    print("Average P&L:", round(df["pnl"].mean(), 2), "%")
    print("Win Rate:", round((df["pnl"] > 0).sum() / len(df) * 100, 2), "%")

if __name__ == "__main__":
    generate_report()
