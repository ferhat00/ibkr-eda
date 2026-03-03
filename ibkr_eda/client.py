"""Connection manager for the IB Gateway (TWS API) via ib_async."""

from __future__ import annotations

import asyncio
import logging

import ib_async.util as _ib_util

from ib_async import IB

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
        # nest_asyncio is needed for sync connect() inside a running loop (Jupyter).
        # It is NOT applied for the async path to avoid breaking Python 3.14 Task
        # context tracking (which makes asyncio.timeout() fail).
        _ib_util.patchAsyncio()
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

    async def connect_async(self) -> None:
        """Connect to IB Gateway / TWS (async, for Jupyter / Python 3.14+).

        Does NOT apply nest_asyncio so that Python 3.14's asyncio.timeout()
        (used internally by asyncio.wait_for) can locate the current Task via
        asyncio.current_task().
        """
        if self.ib.isConnected():
            return
        try:
            await self.ib.connectAsync(
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
