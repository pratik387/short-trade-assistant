import logging
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from backend.services.data_fetcher import fetch_kite_data
from backend.services.technical_analysis import prepare_indicators, calculate_score
from backend.services.config import load_filter_config, get_index_symbols
from backend.services.email_alert import send_exit_email

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[1]
PORTFOLIO_PATH = BASE_DIR / "data" / "portfolio.json"

class ExitService:
    def __init__(self, interval: str = 'day', index: str = 'all'):
        self.interval = interval
        self.index = index
        cfg = load_filter_config()
        # Exit criteria configuration with hard and soft rule toggles and weights
        self.exit_cfg = cfg.get('exit_criteria', {
            # HARD exit parameters
            'use_profit_target': True,
            'profit_target_pct': 0.02,
            'use_stop_loss': True,
            'stop_loss_pct': 0.01,
            'use_time_exit': False,
            'max_holding_minutes': 240,
            'use_pivot_break': False,
            # SOFT exit parameters (weights)
            'use_ma_cross': True,
            'ma_short': 20,
            'ma_long': 50,
            'weight_ma_cross': 3,
            'use_rsi_drop': True,
            'rsi_upper': 70,
            'rsi_lower': 50,
            'weight_rsi_drop': 2,
            'use_trailing_atr': True,
            'atr_multiplier': 3,
            'weight_atr_nudge': 1,
            'use_volume_exhaust': False,
            'volume_exhaust_mult': 2,
            'weight_volume_exhaust': 1,
            'soft_exit_threshold': 4
        })

    def check_exits(self) -> None:
        """
        Load tracked positions from portfolio.json (symbol -> entry_info),
        fetch latest data, evaluate exit criteria, and trigger email if met.
        entry_info may include price and timestamp for time-based exits.
        """
        try:
            with open(PORTFOLIO_PATH, 'r') as f:
                entry_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load portfolio: {e}")
            return

        for symbol, info in entry_data.items():
            # info can be {"price": x, "timestamp": "ISO8601"}
            entry_price = info.get('price') if isinstance(info, dict) else info
            entry_time = None
            if isinstance(info, dict) and 'timestamp' in info:
                entry_time = datetime.fromisoformat(info['timestamp'])

            token = self._get_token(symbol)
            df = fetch_kite_data(symbol, token, self.interval)
            if df.empty:
                continue
            df = prepare_indicators(df)
            latest = df.iloc[-1]
            exit_reason = self._should_exit(df, latest, entry_price, entry_time)
            if exit_reason:
                send_exit_email(symbol)
                logger.info(f"Exit triggered for {symbol}, reason: {exit_reason}")
                # Optionally update portfolio.json to remove exited symbol

    def _should_exit(self, df: pd.DataFrame, latest: pd.Series, entry_price: float, entry_time: datetime):
        price = latest['close']
        cfg = self.exit_cfg
        # 1) HARD EXITS
        # 1.a) Profit target
        if cfg.get('use_profit_target', False):
            if price >= entry_price * (1 + cfg.get('profit_target_pct', 0.02)):
                return 'profit_target'
        # 1.b) Stop-loss
        if cfg.get('use_stop_loss', False):
            if price <= entry_price * (1 - cfg.get('stop_loss_pct', 0.01)):
                return 'stop_loss'
        # 1.c) Time-based exit
        if cfg.get('use_time_exit', False) and entry_time:
            hold_duration = datetime.now() - entry_time
            if hold_duration >= timedelta(minutes=cfg.get('max_holding_minutes', 240)):
                return 'time_exit'
        # 1.d) Pivot break (hard)
        if cfg.get('use_pivot_break', False) and 'pivot' in latest:
            if price < latest['pivot']:
                return 'pivot_break'

        # 2) SOFT EXIT SCORE
        exit_score = 0
        # 2.a) EMA crossover (short < long)
        if cfg.get('use_ma_cross', False):
            short = df['close'].ewm(span=cfg.get('ma_short', 20), adjust=False).mean().iloc[-1]
            long = df['close'].ewm(span=cfg.get('ma_long', 50), adjust=False).mean().iloc[-1]
            if short < long:
                exit_score += cfg.get('weight_ma_cross', 3)
        # 2.b) RSI drop from overbought
        if cfg.get('use_rsi_drop', False):
            rsi_prev = df['RSI'].iloc[-2]
            rsi_now = latest.get('RSI', None)
            if rsi_now is not None and rsi_prev > cfg.get('rsi_upper', 70) and rsi_now < cfg.get('rsi_lower', 50):
                exit_score += cfg.get('weight_rsi_drop', 2)
        # 2.c) ATR nudge
        if cfg.get('use_trailing_atr', False):
            atr_val = latest.get('atr', None)
            if atr_val is not None:
                # If price < entry_price + 1×ATR, treat as nudge
                if price < (entry_price + atr_val * cfg.get('weight_atr_nudge', 1)):
                    exit_score += cfg.get('weight_atr_nudge', 1)
        # 2.d) Volume exhaustion
        if cfg.get('use_volume_exhaust', False) and len(df) >= 6:
            vol_ma = df['volume'].rolling(5).mean().iloc[-2]
            if vol_ma and latest['volume'] > cfg.get('volume_exhaust_mult', 2) * vol_ma:
                prev_close = df['close'].iloc[-2]
                if abs(latest['close'] - prev_close) / prev_close < 0.002:
                    exit_score += cfg.get('weight_volume_exhaust', 1)

        if exit_score >= cfg.get('soft_exit_threshold', 4):
            return 'soft_exit_score'
        return None

    def _get_token(self, symbol: str) -> int:
        instruments = get_index_symbols(self.index)
        for item in instruments:
            if item['symbol'] == symbol:
                return item.get('instrument_token')
        return None

# Helper for scheduler

def run_exit_checks():
    service = ExitService()
    service.check_exits()
