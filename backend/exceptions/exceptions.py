class InvalidTokenException(Exception):
    """Raised when Kite API access token is invalid or expired."""
    pass

class MarketClosedException(Exception):
    """Raised when market is closed or it's a trading holiday."""
    pass

class DataUnavailableException(Exception):
    """Raised when historical data is unavailable for a stock."""
    pass

class OrderPlacementException(Exception):
    """Raised when placing a Kite order fails permanently."""
    pass

class KiteException(Exception):
    """Raised when placing a Kite connection fails permanently."""
    pass
