"""Current portfolio positions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import positions_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Positions:
    """Fetch current positions via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self, account_id: str | None = None) -> list:
        """Return raw ib_async Position objects from the local cache.

        If *account_id* is None, returns positions for all managed accounts.
        """
        all_positions = self._client.ib.positions()
        if account_id is None:
            return list(all_positions)
        return [p for p in all_positions if p.account == account_id]

    async def get_raw_async(self, account_id: str | None = None) -> list:
        """Fetch positions live from TWS and return raw ib_async Position objects.

        If *account_id* is None, returns positions for all managed accounts.
        """
        all_positions = await self._client.ib.reqPositionsAsync()
        if account_id is None:
            return list(all_positions)
        return [p for p in all_positions if p.account == account_id]

    def get(self, account_id: str | None = None) -> pd.DataFrame:
        """Fetch all positions from the local cache and return as a DataFrame.

        If *account_id* is None, returns positions for all managed accounts.
        """
        raw = self.get_raw(account_id)
        if not raw:
            return pd.DataFrame()
        return positions_to_df(raw)

    async def get_async(self, account_id: str | None = None) -> pd.DataFrame:
        """Fetch positions live from TWS and return as a DataFrame. Use in async (Jupyter) contexts.

        If *account_id* is None, returns positions for all managed accounts.
        """
        raw = await self.get_raw_async(account_id)
        if not raw:
            return pd.DataFrame()
        return positions_to_df(raw)
