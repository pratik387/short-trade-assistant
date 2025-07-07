"""
Configuration for backtest parameters.
"""
BACKTEST_CONFIG = {
    "start_date": "2024-07-01",
    "end_date": "2024-12-30",
    "capital": 100000,
    "capital_per_trade": 20000,
    "minimum_entry_score": 18,
    "max_trades_per_day": 10,
    "max_hold_days": 10,
    "stop_loss_threshold": -5.0,
    "profit_target": 5.0,
    "minimum_holding_days": 3,
    "min_score_gap_to_replace":5
}