# logging_config.py — Singleton logger factory

import logging
from pathlib import Path

_agent_logger = None
_trade_logger = None
_current_log_month = None

def get_loggers():
    global _agent_logger, _trade_logger

    if _agent_logger and _trade_logger:
        return _agent_logger, _trade_logger

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter('%(asctime)s — %(levelname)s — %(name)s — %(message)s')

    # Agent Logger
    _agent_logger = logging.getLogger("agent")
    if not _agent_logger.hasHandlers():
        _agent_logger.setLevel(logging.INFO)
        agent_file = logging.FileHandler(log_dir / "agent.log",  encoding="utf-8")
        agent_file.setFormatter(formatter)
        _agent_logger.addHandler(agent_file)

    # Trade Logger
    _trade_logger = logging.getLogger("trade")
    if not _trade_logger.hasHandlers():
        _trade_logger.setLevel(logging.INFO)
        trade_file = logging.FileHandler(log_dir / "trades.log",  encoding="utf-8")
        trade_file.setFormatter(formatter)
        _trade_logger.addHandler(trade_file)

    return _agent_logger, _trade_logger

def switch_agent_log_file(month_str: str):
    """Swap agent logger file handler based on backtest month (e.g., '2025-06')"""
    global _agent_logger, _current_log_month
    if not _agent_logger:
        get_loggers()

    if month_str == _current_log_month:
        return

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"agent.{month_str}.log"

    for h in _agent_logger.handlers[:]:
        _agent_logger.removeHandler(h)

    formatter = logging.Formatter('%(asctime)s — %(levelname)s — %(name)s — %(message)s')
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    _agent_logger.addHandler(file_handler)
    _current_log_month = month_str
