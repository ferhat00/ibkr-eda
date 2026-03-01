"""Current portfolio positions with auto-pagination."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import positions_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Positions:
    """Fetch current positions from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self, account_id: str | None = None, page: int = 0) -> list[dict]:
        """Return a single page of raw positions JSON."""
        acct = account_id or self._client.account_id
        return self._client.get(f"/portfolio/{acct}/positions/{page}")

    def get(self, account_id: str | None = None) -> pd.DataFrame:
        """Fetch all positions (auto-paginating) and return as a DataFrame."""
        acct = account_id or self._client.account_id
        all_positions: list[dict] = []
        page = 0
        while True:
            batch = self._client.get(f"/portfolio/{acct}/positions/{page}")
            if not batch:
                break
            all_positions.extend(batch)
            page += 1
        if not all_positions:
            return pd.DataFrame()
        return positions_to_df(all_positions)
