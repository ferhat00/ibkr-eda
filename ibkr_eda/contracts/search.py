"""Contract/symbol search."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class ContractSearch:
    """Search for contracts by symbol via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def search_raw(self, symbol: str, sec_type: str | None = None) -> list:
        """Return matching ContractDescription objects."""
        descriptions = self._client.ib.reqMatchingSymbols(symbol)
        if not descriptions:
            return []
        if sec_type:
            descriptions = [
                d for d in descriptions
                if d.contract.secType == sec_type
            ]
        return descriptions

    async def search_raw_async(self, symbol: str, sec_type: str | None = None) -> list:
        """Return matching ContractDescription objects (async, for Jupyter / Python 3.14+)."""
        descriptions = await asyncio.ensure_future(self._client.ib.reqMatchingSymbolsAsync(symbol))
        if not descriptions:
            return []
        if sec_type:
            descriptions = [
                d for d in descriptions
                if d.contract.secType == sec_type
            ]
        return descriptions

    def search(self, symbol: str, sec_type: str | None = None) -> pd.DataFrame:
        """Search for contracts by symbol and return as a DataFrame."""
        raw = self.search_raw(symbol, sec_type)
        if not raw:
            return pd.DataFrame()
        rows = []
        for desc in raw:
            c = desc.contract
            rows.append({
                "conid": c.conId,
                "symbol": c.symbol,
                "secType": c.secType,
                "primaryExchange": c.primaryExchange,
                "currency": c.currency,
                "derivativeSecTypes": ", ".join(desc.derivativeSecTypes) if desc.derivativeSecTypes else "",
            })
        return pd.DataFrame(rows)

    async def search_async(self, symbol: str, sec_type: str | None = None) -> pd.DataFrame:
        """Search for contracts by symbol (async, for Jupyter / Python 3.14+)."""
        raw = await self.search_raw_async(symbol, sec_type)
        if not raw:
            return pd.DataFrame()
        rows = []
        for desc in raw:
            c = desc.contract
            rows.append({
                "conid": c.conId,
                "symbol": c.symbol,
                "secType": c.secType,
                "primaryExchange": c.primaryExchange,
                "currency": c.currency,
                "derivativeSecTypes": ", ".join(desc.derivativeSecTypes) if desc.derivativeSecTypes else "",
            })
        return pd.DataFrame(rows)
