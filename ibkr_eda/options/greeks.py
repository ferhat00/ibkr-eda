"""Single and multi-contract Greeks lookup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.options.provider import OptionQuote
from ibkr_eda.utils.transformers import option_quotes_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient
    from ibkr_eda.options.provider import OptionsProvider

logger = logging.getLogger(__name__)


class Greeks:
    """Fetch option Greeks with automatic IBKR / fallback provider selection."""

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
            return self._provider
        if self._client and self._client.ib.isConnected():
            from ibkr_eda.options.ibkr_provider import IBKROptionsProvider
            self._provider = IBKROptionsProvider(self._client)
        else:
            from ibkr_eda.options.fallback_provider import FallbackOptionsProvider
            self._provider = FallbackOptionsProvider(**self._fallback_kwargs)
        return self._provider

    # ------------------------------------------------------------------
    # Raw (single OptionQuote)
    # ------------------------------------------------------------------

    def get_raw(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        """Return Greeks for a single option contract."""
        return self._resolve_provider().get_greeks(
            symbol, expiry, strike, right, exchange,
        )

    async def get_raw_async(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        """Async variant of get_raw."""
        return await self._resolve_provider().get_greeks_async(
            symbol, expiry, strike, right, exchange,
        )

    # ------------------------------------------------------------------
    # Transformed (DataFrame)
    # ------------------------------------------------------------------

    def get(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Return single-row DataFrame with all Greek columns."""
        quote = self.get_raw(symbol, expiry, strike, right, exchange)
        return option_quotes_to_df([quote])

    async def get_async(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Async variant of get."""
        quote = await self.get_raw_async(symbol, expiry, strike, right, exchange)
        return option_quotes_to_df([quote])

    def get_multiple(
        self,
        symbol: str,
        expiry: str,
        strikes: list[float],
        right: str,
        exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Return DataFrame of Greeks for multiple strikes."""
        quotes: list[OptionQuote] = []
        for strike in strikes:
            q = self.get_raw(symbol, expiry, strike, right, exchange)
            quotes.append(q)
        return option_quotes_to_df(quotes)

    async def get_multiple_async(
        self,
        symbol: str,
        expiry: str,
        strikes: list[float],
        right: str,
        exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Async variant of get_multiple."""
        quotes: list[OptionQuote] = []
        for strike in strikes:
            q = await self.get_raw_async(symbol, expiry, strike, right, exchange)
            quotes.append(q)
        return option_quotes_to_df(quotes)
