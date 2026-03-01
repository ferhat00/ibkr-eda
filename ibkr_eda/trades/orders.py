"""Live and recent orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import orders_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Orders:
    """Fetch order data from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(self) -> list[dict]:
        """Return raw orders JSON (open and recent)."""
        resp = self._client.get("/iserver/account/orders")
        if isinstance(resp, dict):
            return resp.get("orders", [])
        return resp

    def get(self) -> pd.DataFrame:
        """Return orders as a DataFrame."""
        return orders_to_df(self.get_raw())
