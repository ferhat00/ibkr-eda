"""Core HTTP client for the IBKR Client Portal REST API."""

from __future__ import annotations

import logging
import threading
from typing import Any

import requests
import urllib3

from ibkr_eda.config import IBKRConfig
from ibkr_eda.exceptions import (
    IBKRAPIError,
    IBKRAuthError,
    IBKRConnectionError,
    IBKRRateLimitError,
)
from ibkr_eda.utils.rate_limiter import RateLimiter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


class IBKRClient:
    """Low-level HTTP client for the IBKR Client Portal Gateway.

    Handles session management, rate limiting, SSL, and keepalive.
    All domain modules receive a reference to this client.
    """

    def __init__(self, config: IBKRConfig | None = None):
        self.config = config or IBKRConfig.from_env()
        self._session = requests.Session()
        self._session.verify = self.config.verify_ssl
        self._rate_limiter = RateLimiter(self.config.rate_limit)
        self._tickle_timer: threading.Timer | None = None
        self._account_id: str | None = self.config.account_id

    # ── HTTP primitives ──────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None) -> Any:
        """Send a GET request to the gateway."""
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> Any:
        """Send a POST request to the gateway."""
        return self._request("POST", path, json=json)

    def delete(self, path: str, params: dict | None = None) -> Any:
        """Send a DELETE request to the gateway."""
        return self._request("DELETE", path, params=params)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.config.base_url}{path}"
        self._rate_limiter.wait()
        try:
            resp = self._session.request(
                method, url, timeout=self.config.request_timeout, **kwargs
            )
        except requests.ConnectionError as exc:
            raise IBKRConnectionError(
                f"Cannot reach gateway at {self.config.base_url}. "
                "Is the Client Portal Gateway running?"
            ) from exc

        if resp.status_code == 401:
            raise IBKRAuthError(
                "Session not authenticated. Log in via the gateway browser UI, "
                "then call client.reauthenticate()."
            )
        if resp.status_code == 429:
            raise IBKRRateLimitError("Rate limit exceeded (10 req/sec).")
        if not resp.ok:
            raise IBKRAPIError(resp.status_code, resp.text, url)

        if not resp.content:
            return {}
        return resp.json()

    # ── Session management ───────────────────────────────────────────

    def auth_status(self) -> dict:
        """Check current authentication status."""
        return self.get("/iserver/auth/status")

    def tickle(self) -> dict:
        """Keep the session alive."""
        return self.post("/tickle")

    def reauthenticate(self) -> dict:
        """Reauthenticate the brokerage session."""
        return self.post("/iserver/reauthenticate")

    def validate_sso(self) -> dict:
        """Validate the SSO session."""
        return self.get("/sso/validate")

    def start_keepalive(self) -> None:
        """Start a background daemon that calls /tickle periodically."""

        def _tick() -> None:
            try:
                self.tickle()
                logger.debug("Tickle sent.")
            except Exception as exc:
                logger.warning("Tickle failed: %s", exc)
            self._tickle_timer = threading.Timer(self.config.tickle_interval, _tick)
            self._tickle_timer.daemon = True
            self._tickle_timer.start()

        _tick()

    def stop_keepalive(self) -> None:
        """Stop the background keepalive timer."""
        if self._tickle_timer:
            self._tickle_timer.cancel()
            self._tickle_timer = None

    # ── Account resolution ───────────────────────────────────────────

    @property
    def account_id(self) -> str:
        """Return the configured account ID, or auto-detect from the API."""
        if not self._account_id:
            accounts = self.get("/portfolio/accounts")
            if not accounts:
                raise IBKRAuthError("No accounts returned. Check authentication.")
            self._account_id = accounts[0]["accountId"]
            logger.info("Auto-detected account: %s", self._account_id)
        return self._account_id

    @account_id.setter
    def account_id(self, value: str) -> None:
        self._account_id = value
