"""High-level option chain access with automatic provider selection."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.options.provider import OptionChainData, OptionQuote
from ibkr_eda.utils.transformers import option_quotes_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient
    from ibkr_eda.options.provider import OptionsProvider

logger = logging.getLogger(__name__)


class OptionChains:
    """Fetch option chains with automatic IBKR / fallback provider selection."""

    def __init__(
        self,
        client: IBKRClient | None = None,
        provider: OptionsProvider | None = None,
        fallback_kwargs: dict | None = None,
    ):
        self._client = client
        self._provider = provider
        self._fallback_kwargs = fallback_kwargs or {}

    def _resolve_provider(self) -> OptionsProvider:
        if self._provider is not None:
            # If the cached provider is IBKR-backed but the connection has since
            # dropped, transparently switch to the free fallback so callers don't
            # get "Not connected" errors.
            from ibkr_eda.options.ibkr_provider import IBKROptionsProvider
            if isinstance(self._provider, IBKROptionsProvider):
                if self._client is None or not self._client.ib.isConnected():
                    logger.info(
                        "IBKR connection lost — switching option chain provider "
                        "to FallbackOptionsProvider."
                    )
                    from ibkr_eda.options.fallback_provider import FallbackOptionsProvider
                    self._provider = FallbackOptionsProvider(**self._fallback_kwargs)
            return self._provider
        if self._client and self._client.ib.isConnected():
            from ibkr_eda.options.ibkr_provider import IBKROptionsProvider
            self._provider = IBKROptionsProvider(self._client)
        else:
            from ibkr_eda.options.fallback_provider import FallbackOptionsProvider
            self._provider = FallbackOptionsProvider(**self._fallback_kwargs)
        return self._provider

    # ------------------------------------------------------------------
    # Expirations
    # ------------------------------------------------------------------

    def get_expirations(self, symbol: str, exchange: str = "SMART") -> list[str]:
        """Return sorted list of available expiry dates (YYYYMMDD)."""
        return self._resolve_provider().get_expirations(symbol, exchange)

    async def get_expirations_async(
        self, symbol: str, exchange: str = "SMART",
    ) -> list[str]:
        """Async variant of get_expirations."""
        return await self._resolve_provider().get_expirations_async(symbol, exchange)

    # ------------------------------------------------------------------
    # Raw (list[OptionQuote])
    # ------------------------------------------------------------------

    def get_raw(self, symbol: str, expiry: str, exchange: str = "SMART") -> list[OptionQuote]:
        """Return raw OptionQuote list for *symbol* + *expiry*."""
        provider = self._resolve_provider()
        try:
            return provider.get_chain(symbol, expiry, exchange)
        except Exception as exc:
            from ibkr_eda.options.ibkr_provider import IBKROptionsProvider
            if isinstance(provider, IBKROptionsProvider):
                logger.warning(
                    "IBKR chain fetch failed (%s) — retrying with FallbackOptionsProvider.",
                    exc,
                )
                from ibkr_eda.options.fallback_provider import FallbackOptionsProvider
                self._provider = FallbackOptionsProvider(**self._fallback_kwargs)
                return self._provider.get_chain(symbol, expiry, exchange)
            raise

    async def get_raw_async(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> list[OptionQuote]:
        """Async variant of get_raw."""
        provider = self._resolve_provider()
        try:
            return await provider.get_chain_async(symbol, expiry, exchange)
        except Exception as exc:
            from ibkr_eda.options.ibkr_provider import IBKROptionsProvider
            if isinstance(provider, IBKROptionsProvider):
                logger.warning(
                    "IBKR chain fetch failed (%s) — retrying with FallbackOptionsProvider.",
                    exc,
                )
                from ibkr_eda.options.fallback_provider import FallbackOptionsProvider
                self._provider = FallbackOptionsProvider(**self._fallback_kwargs)
                return await self._provider.get_chain_async(symbol, expiry, exchange)
            raise

    # ------------------------------------------------------------------
    # Transformed (OptionChainData with DataFrames)
    # ------------------------------------------------------------------

    def get(self, symbol: str, expiry: str, exchange: str = "SMART") -> OptionChainData:
        """Return option chain as OptionChainData (calls/puts DataFrames)."""
        quotes = self.get_raw(symbol, expiry, exchange)
        return self._to_chain_data(quotes, symbol, expiry)

    async def get_async(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> OptionChainData:
        """Async variant of get."""
        quotes = await self.get_raw_async(symbol, expiry, exchange)
        return self._to_chain_data(quotes, symbol, expiry)

    def get_df(self, symbol: str, expiry: str, exchange: str = "SMART") -> pd.DataFrame:
        """Return flat DataFrame with all calls and puts."""
        quotes = self.get_raw(symbol, expiry, exchange)
        return option_quotes_to_df(quotes)

    async def get_df_async(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Async variant of get_df."""
        quotes = await self.get_raw_async(symbol, expiry, exchange)
        return option_quotes_to_df(quotes)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _to_chain_data(
        quotes: list[OptionQuote], symbol: str, expiry: str,
    ) -> OptionChainData:
        calls = [q for q in quotes if q.right == "C"]
        puts = [q for q in quotes if q.right == "P"]
        und_price = next(
            (q.underlying_price for q in quotes if q.underlying_price), 0.0,
        )
        return OptionChainData(
            symbol=symbol,
            underlying_price=und_price,
            expiry=expiry,
            calls=option_quotes_to_df(calls),
            puts=option_quotes_to_df(puts),
        )
