"""Custom exception hierarchy for IBKR TWS API errors."""


class IBKRError(Exception):
    """Base exception for all IBKR API errors."""


class IBKRAuthError(IBKRError):
    """Not authenticated or session expired."""


class IBKRRateLimitError(IBKRError):
    """Rate limit / pacing violation."""


class IBKRAPIError(IBKRError):
    """TWS API returned an error."""

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"TWS error {code}: {message}")


class IBKRConnectionError(IBKRError):
    """Cannot reach the IB Gateway."""
