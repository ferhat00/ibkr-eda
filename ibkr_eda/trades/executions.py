"""Trade executions (filled trades)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import trades_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Executions:
    """Fetch trade execution data from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self) -> list[dict]:
        """Return raw trade executions JSON."""
        return self._client.get("/iserver/account/trades")

    def get(self) -> pd.DataFrame:
        """Return trade executions as a DataFrame."""
        raw = self.get_raw()
        if not raw:
            return pd.DataFrame()
        return trades_to_df(raw)
