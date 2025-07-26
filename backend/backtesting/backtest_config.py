"""
Configuration for backtest parameters.
"""
BACKTEST_CONFIG = {
    "start_date": "2023-05-01",
    "end_date": "2025-06-01",
    "capital": 100000,
    "capital_per_trade": 20000,
    "minimum_entry_score": 1.9,
    "max_trades_per_day": 10,
    "maximum_holding_days": 15,
    "stop_loss_threshold": -5.0,
    "profit_target": 5.0,
    "min_score_gap_to_replace":5
}