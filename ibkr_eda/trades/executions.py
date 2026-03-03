"""Trade executions (filled trades)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import trades_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Executions:
    """Fetch trade execution data via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self) -> list:
        """Return ib_async Fill objects by requesting from TWS."""
        return self._client.ib.reqExecutions()

    async def get_raw_async(self) -> list:
        """Return ib_async Fill objects (async, for Jupyter / Python 3.14+)."""
        return await asyncio.ensure_future(self._client.ib.reqExecutionsAsync())

    def get(
        self,
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return trade executions as a DataFrame.

        Parameters
        ----------
        account_id : str, optional
            Filter by account ID (e.g. ``"U14593335"``).
        start_date : str, optional
            Include executions on or after this date (``"YYYY-MM-DD"``).
        end_date : str, optional
            Include executions on or before this date (``"YYYY-MM-DD"``).
        """
        raw = self.get_raw()
        if not raw:
            return pd.DataFrame()
        df = trades_to_df(raw)
        if account_id:
            df = df[df["account_id"] == account_id]
        if start_date or end_date:
            trade_dates = pd.to_datetime(df["trade_time"], utc=True).dt.normalize()
            if start_date:
                df = df[trade_dates >= pd.Timestamp(start_date, tz="UTC")]
            if end_date:
                trade_dates = pd.to_datetime(df["trade_time"], utc=True).dt.normalize()
                df = df[trade_dates <= pd.Timestamp(end_date, tz="UTC")]
        return df.reset_index(drop=True)

    async def get_async(
        self,
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return trade executions as a DataFrame (async, for Jupyter / Python 3.14+)."""
        raw = await self.get_raw_async()
        if not raw:
            return pd.DataFrame()
        df = trades_to_df(raw)
        if account_id:
            df = df[df["account_id"] == account_id]
        if start_date or end_date:
            trade_dates = pd.to_datetime(df["trade_time"], utc=True).dt.normalize()
            if start_date:
                df = df[trade_dates >= pd.Timestamp(start_date, tz="UTC")]
            if end_date:
                trade_dates = pd.to_datetime(df["trade_time"], utc=True).dt.normalize()
                df = df[trade_dates <= pd.Timestamp(end_date, tz="UTC")]
        return df.reset_index(drop=True)
