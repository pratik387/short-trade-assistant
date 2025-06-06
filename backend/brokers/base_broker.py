class BaseBroker:
    def place_order(self, symbol: str, quantity: int, action: str) -> dict:
        raise NotImplementedError
