class InsufficientFundsError(Exception):
    def __init__(self, available: int, requested: int):
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient funds: requested {requested}p, available {available}p"
        )


class PayoutNotFoundError(Exception):
    pass


