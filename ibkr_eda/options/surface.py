"""Implied volatility surface builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.options.provider import VolSurfaceData
from ibkr_eda.options.utils import find_atm_strike

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient
    from ibkr_eda.options.provider import OptionsProvider

logger = logging.getLogger(__name__)


class VolSurface:
    """Build implied volatility surfaces with automatic provider selection."""

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
    # Raw (VolSurfaceData)
    # ------------------------------------------------------------------

    def get_raw(self, symbol: str, exchange: str = "SMART") -> VolSurfaceData:
        """Return VolSurfaceData with 2-D IV arrays."""
        return self._resolve_provider().get_iv_surface(symbol, exchange)

    async def get_raw_async(self, symbol: str, exchange: str = "SMART") -> VolSurfaceData:
        """Async variant of get_raw."""
        return await self._resolve_provider().get_iv_surface_async(symbol, exchange)

    # ------------------------------------------------------------------
    # Transformed (DataFrame)
    # ------------------------------------------------------------------

    def get(self, symbol: str, exchange: str = "SMART") -> pd.DataFrame:
        """Return IV surface as a DataFrame (index=strike, columns=expiry, values=call IV)."""
        surface = self.get_raw(symbol, exchange)
        df = pd.DataFrame(
            surface.call_iv,
            index=surface.expiries,
            columns=surface.strikes,
        )
        return df.T  # strikes as index, expiries as columns

    async def get_async(self, symbol: str, exchange: str = "SMART") -> pd.DataFrame:
        """Async variant of get."""
        surface = await self.get_raw_async(symbol, exchange)
        df = pd.DataFrame(
            surface.call_iv,
            index=surface.expiries,
            columns=surface.strikes,
        )
        return df.T

    def get_term_structure(self, symbol: str, exchange: str = "SMART") -> pd.DataFrame:
        """Return ATM implied volatility by expiry (term structure)."""
        surface = self.get_raw(symbol, exchange)
        strikes_list = surface.strikes.tolist()
        atm = find_atm_strike(strikes_list, surface.underlying_price)
        atm_idx = strikes_list.index(atm)
        rows = []
        for ei, exp in enumerate(surface.expiries):
            rows.append({
                "expiry": exp,
                "atm_strike": atm,
                "call_iv": surface.call_iv[ei, atm_idx],
                "put_iv": surface.put_iv[ei, atm_idx],
            })
        return pd.DataFrame(rows)

    async def get_term_structure_async(
        self, symbol: str, exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Async variant of get_term_structure."""
        surface = await self.get_raw_async(symbol, exchange)
        strikes_list = surface.strikes.tolist()
        atm = find_atm_strike(strikes_list, surface.underlying_price)
        atm_idx = strikes_list.index(atm)
        rows = []
        for ei, exp in enumerate(surface.expiries):
            rows.append({
                "expiry": exp,
                "atm_strike": atm,
                "call_iv": surface.call_iv[ei, atm_idx],
                "put_iv": surface.put_iv[ei, atm_idx],
            })
        return pd.DataFrame(rows)

    def get_skew(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Return IV skew (IV by strike) for a single expiry."""
        from ibkr_eda.utils.transformers import option_quotes_to_df

        provider = self._resolve_provider()
        chain = provider.get_chain(symbol, expiry, exchange)
        calls = [q for q in chain if q.right == "C"]
        puts = [q for q in chain if q.right == "P"]

        rows = []
        call_map = {q.strike: q.implied_vol for q in calls}
        put_map = {q.strike: q.implied_vol for q in puts}
        all_strikes = sorted(set(call_map) | set(put_map))
        for s in all_strikes:
            rows.append({
                "strike": s,
                "call_iv": call_map.get(s),
                "put_iv": put_map.get(s),
            })
        return pd.DataFrame(rows)

    async def get_skew_async(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> pd.DataFrame:
        """Async variant of get_skew."""
        provider = self._resolve_provider()
        chain = await provider.get_chain_async(symbol, expiry, exchange)
        calls = [q for q in chain if q.right == "C"]
        puts = [q for q in chain if q.right == "P"]

        call_map = {q.strike: q.implied_vol for q in calls}
        put_map = {q.strike: q.implied_vol for q in puts}
        all_strikes = sorted(set(call_map) | set(put_map))
        rows = []
        for s in all_strikes:
            rows.append({
                "strike": s,
                "call_iv": call_map.get(s),
                "put_iv": put_map.get(s),
            })
        return pd.DataFrame(rows)
