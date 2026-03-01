"""Profit and loss data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class PnL:
    """Fetch profit & loss data from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self) -> dict:
        """Return raw partitioned PnL JSON."""
        return self._client.get("/iserver/account/pnl/partitioned")

    def get(self) -> pd.DataFrame:
        """Return partitioned PnL as a DataFrame.

        The API returns PnL partitioned by account and sub-account.
        This flattens it into a single DataFrame.
        """
        raw = self.get_raw()
        rows = []
        for acct_id, acct_data in raw.items():
            if isinstance(acct_data, dict):
                row = {"account_id": acct_id}
                row.update(acct_data)
                rows.append(row)
        if not rows:
            return pd.DataFrame()
        return pd.json_normalize(rows)
