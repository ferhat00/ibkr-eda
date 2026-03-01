"""Live and recent orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import orders_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Orders:
    """Fetch order data via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self) -> list:
        """Return ib_async Trade objects for open orders."""
        return self._client.ib.openTrades()

    def get(self) -> pd.DataFrame:
        """Return orders as a DataFrame."""
        return orders_to_df(self.get_raw())
