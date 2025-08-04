from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
import pandas as pd
from datetime import date

class BaseStrategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def get_mode(self) -> str:
        """Return the strategy mode identifier (e.g., 'intraday', 'short_term')."""
        pass
    
    @abstractmethod
    def preload_and_filter_symbols(self, symbols, data_provider, config, as_of_date: Optional[date] = None) ->  Tuple[List, Dict]:
        pass

    @abstractmethod
    def apply_hard_filters(self, symbol: str, df: pd.DataFrame, ltp: Optional[float] = None) -> bool:
        """
        Apply relevant filters to the symbol's data and return a suggestion dict if valid.
        Return None if the symbol doesn't pass filters.
        """
        pass
