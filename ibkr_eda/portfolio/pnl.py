"""Profit and loss data."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class PnL:
    """Fetch profit & loss data via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self) -> object:
        """Return raw ib_async PnL object."""
        acct = self._client.account_id
        pnl = self._client.ib.reqPnL(acct)
        self._client.ib.sleep(1)  # wait for data to arrive
        self._client.ib.cancelPnL(pnl)
        return pnl

    def get(self) -> pd.DataFrame:
        """Return P&L as a DataFrame."""
        acct = self._client.account_id
        pnl = self._client.ib.reqPnL(acct)
        self._client.ib.sleep(1)
        self._client.ib.cancelPnL(pnl)
        return pd.DataFrame([{
            "account_id": acct,
            "dailyPnL": pnl.dailyPnL,
            "unrealizedPnL": pnl.unrealizedPnL,
            "realizedPnL": pnl.realizedPnL,
        }])

    async def get_async(self) -> pd.DataFrame:
        """Return P&L as a DataFrame (async, for Jupyter / Python 3.14+)."""
        acct = self._client.account_id
        pnl = self._client.ib.reqPnL(acct)
        await asyncio.sleep(1)
        self._client.ib.cancelPnL(pnl)
        return pd.DataFrame([{
            "account_id": acct,
            "dailyPnL": pnl.dailyPnL,
            "unrealizedPnL": pnl.unrealizedPnL,
            "realizedPnL": pnl.realizedPnL,
        }])
