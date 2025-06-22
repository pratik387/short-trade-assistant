# """
# Visualizes backtest results using matplotlib.
# """
# import pandas as pd
# import matplotlib.pyplot as plt

# def plot_pnl(csv_path="backtesting/test_results/trades.csv"):
#     df = pd.read_csv(csv_path)
#     df["pnl"] = df["pnl"].astype(float)

#     df.plot(x="symbol", y="pnl", kind="bar", title="P&L by Symbol")
#     plt.axhline(0, color="black", linewidth=0.8)
#     plt.show()

# if __name__ == "__main__":
#     plot_pnl()
