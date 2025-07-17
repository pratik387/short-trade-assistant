from config.logging_config import get_loggers

logger, trade_logger = get_loggers()

def supply_absorption_filter(df, config, symbol, **kwargs):
    if config is None:
        return []

    filter_cfg = config.get("supply_absorption_filter")
    if not filter_cfg.get("enabled", False):
        return []

    lookback = filter_cfg.get("range_days", 3)
    price_range_pct = filter_cfg.get("price_range_pct", 1)
    volume_threshold_pct = filter_cfg.get("volume_drop_pct", 30)
    weight = filter_cfg.get("weight", 4)

    recent = df[-lookback:]
    high = recent["high"].max()
    low = recent["low"].min()
    range_pct = ((high - low) / low) * 100 if low != 0 else 0
    vol_now = recent["volume"].iloc[-1]
    vol_avg = recent["volume"].mean()
    vol_drop = ((vol_avg - vol_now) / vol_avg) * 100 if vol_avg != 0 else 0

    logger.info(f"[EXIT-SUPPLY] {symbol} | Range={range_pct:.2f}%, Vol Drop={vol_drop:.2f}%")

    if range_pct <= price_range_pct and vol_drop >= volume_threshold_pct:
        return [{
            "filter": "supply_absorption_filter",
            "weight": weight,
            "reason": f"Tight range ({range_pct:.2f}%) & volume drop ({vol_drop:.2f}%)",
            "triggered": True
        }]
    else:
        return [{
            "filter": "supply_absorption_filter",
            "weight": 0,
            "reason": f"No tight range or volume drop: Range={range_pct:.2f}%, Vol Drop={vol_drop:.2f}%",
            "triggered": False
        }]