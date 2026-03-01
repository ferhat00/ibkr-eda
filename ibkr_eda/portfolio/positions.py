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
        """Return raw ib_async Position objects."""
        acct = account_id or self._client.account_id
        all_positions = self._client.ib.positions()
        return [p for p in all_positions if p.account == acct]

    def get(self, account_id: str | None = None) -> pd.DataFrame:
        """Fetch all positions and return as a DataFrame."""
        raw = self.get_raw(account_id)
        if not raw:
            return pd.DataFrame()
        return positions_to_df(raw)
