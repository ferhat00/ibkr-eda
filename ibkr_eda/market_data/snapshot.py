"""Real-time market data snapshots."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pandas as pd
from ib_async import Contract

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Snapshot:
    """Fetch market data snapshots via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        conids: list[int],
        fields: list[str] | None = None,
    ) -> list:
        """Return ib_async Ticker objects for the given conids.

        Args:
            conids: List of contract IDs.
            fields: Ignored (kept for API compatibility). TWS returns all fields.
        """
        tickers = []
        for conid in conids:
            contract = Contract(conId=conid)
            self._client.ib.qualifyContracts(contract)
            ticker = self._client.ib.reqMktData(contract, snapshot=True)
            tickers.append(ticker)
        # Wait for snapshot data to arrive
        self._client.ib.sleep(2)
        return tickers

    async def get_raw_async(
        self,
        conids: list[int],
        fields: list[str] | None = None,
    ) -> list:
        """Return ib_async Ticker objects (async, for Jupyter / Python 3.14+)."""
        tickers = []
        for conid in conids:
            contract = Contract(conId=conid)
            await asyncio.ensure_future(self._client.ib.qualifyContractsAsync(contract))
            ticker = self._client.ib.reqMktData(contract, snapshot=True)
            tickers.append(ticker)
        await asyncio.sleep(2)
        return tickers

    def get(
        self,
        conids: list[int],
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return market data snapshot as a DataFrame."""
        raw = self.get_raw(conids, fields)
        if not raw:
            return pd.DataFrame()
        rows = []
        for t in raw:
            rows.append({
                "conid": t.contract.conId,
                "symbol": t.contract.symbol,
                "last": t.last,
                "bid": t.bid,
                "ask": t.ask,
                "high": t.high,
                "low": t.low,
                "close": t.close,
                "volume": t.volume,
            })
        return pd.DataFrame(rows)

    async def get_async(
        self,
        conids: list[int],
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return market data snapshot as a DataFrame (async, for Jupyter / Python 3.14+)."""
        raw = await self.get_raw_async(conids, fields)
        if not raw:
            return pd.DataFrame()
        rows = []
        for t in raw:
            rows.append({
                "conid": t.contract.conId,
                "symbol": t.contract.symbol,
                "last": t.last,
                "bid": t.bid,
                "ask": t.ask,
                "high": t.high,
                "low": t.low,
                "close": t.close,
                "volume": t.volume,
            })
        return pd.DataFrame(rows)
