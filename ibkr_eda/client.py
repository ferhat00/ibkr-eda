"""Connection manager for the IB Gateway (TWS API) via ib_async."""

from __future__ import annotations

import logging

import ib_async.util as _ib_util

_ib_util.patchAsyncio()  # allow nested event loops (Jupyter compatibility)

from ib_async import IB  # noqa: E402

from ibkr_eda.config import IBKRConfig
from ibkr_eda.exceptions import IBKRAuthError, IBKRConnectionError

logger = logging.getLogger(__name__)


class IBKRClient:
    """Manages the ib_async IB connection.

    All domain modules receive a reference to this client
    and access self.ib for TWS API calls.
    """

    def __init__(self, config: IBKRConfig | None = None):
        self.config = config or IBKRConfig.from_env()
        self.ib = IB()
        self._account_id: str | None = self.config.account_id

    def connect(self) -> None:
        """Connect to IB Gateway / TWS."""
        if self.ib.isConnected():
            return
        try:
            self.ib.connect(
                self.config.host,
                self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.timeout,
            )
            logger.info(
                "Connected to IB Gateway at %s:%s",
                self.config.host,
                self.config.port,
            )
        except Exception as exc:
            raise IBKRConnectionError(
                f"Cannot connect to IB Gateway at "
                f"{self.config.host}:{self.config.port}. "
                "Is IB Gateway running and logged in?"
            ) from exc

    def disconnect(self) -> None:
        """Disconnect from IB Gateway / TWS."""
        if self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from IB Gateway.")

    @property
    def account_id(self) -> str:
        """Return the configured account ID, or auto-detect."""
        if not self._account_id:
            accounts = self.ib.managedAccounts()
            if not accounts:
                raise IBKRAuthError("No managed accounts returned.")
            self._account_id = accounts[0]
            logger.info("Auto-detected account: %s", self._account_id)
        return self._account_id

    @account_id.setter
    def account_id(self, value: str) -> None:
        self._account_id = value
