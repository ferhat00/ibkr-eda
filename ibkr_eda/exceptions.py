"""Custom exception hierarchy for IBKR Client Portal API errors."""


class IBKRError(Exception):
    """Base exception for all IBKR API errors."""


class IBKRAuthError(IBKRError):
    """Session not authenticated or expired."""


class IBKRRateLimitError(IBKRError):
    """Rate limit exceeded."""


class IBKRAPIError(IBKRError):
    """API returned an error response."""

    def __init__(self, status_code: int, message: str, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} from {url}: {message}")


class IBKRConnectionError(IBKRError):
    """Cannot reach the Client Portal Gateway."""
