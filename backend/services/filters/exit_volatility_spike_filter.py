from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def volatility_spike_exit(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("volatility_spike_exit")
    if not filter_cfg.get("enabled", False):
        return []

    weight = filter_cfg.get("weight", 3)
    spike_pct = filter_cfg.get("atr_spike_pct", 25)

    if "ATR" not in df.columns or len(df) < 2:
        return []

    atr_now = df["ATR"].iloc[-1]
    atr_prev = df["ATR"].iloc[-2]
    spike = ((atr_now - atr_prev) / atr_prev) * 100 if atr_prev != 0 else 0

    logger.info(f"[EXIT-VOL] {symbol} | ATR Now={atr_now:.2f}, Prev={atr_prev:.2f}, Spike={spike:.2f}%")

    if spike >= spike_pct:
        return [{
            "filter": "volatility_spike_exit",
            "weight": weight,
            "reason": f"Volatility spike: ATR increased {spike:.2f}%",
            "triggered": True
        }]
    return [{
        "filter": "volatility_spike_exit",
        "weight": 0,
        "reason": f"ATR stable: Spike {spike:.2f}% < threshold {spike_pct}%",
        "triggered": False
    }]