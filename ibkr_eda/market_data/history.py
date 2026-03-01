"""Historical market data (OHLCV bars)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.utils.transformers import history_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class History:
    """Fetch historical market data from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        conid: int,
        period: str = "1y",
        bar: str = "1d",
        outside_rth: bool = False,
    ) -> dict:
        """Return raw historical bar data JSON.

        Args:
            conid: Contract ID.
            period: Time period (e.g., '1d', '1w', '1m', '3m', '6m', '1y', '5y').
            bar: Bar size (e.g., '1min', '5min', '1h', '1d', '1w', '1m').
            outside_rth: Include data outside regular trading hours.
        """
        params = {
            "conid": conid,
            "period": period,
            "bar": bar,
            "outsideRth": str(outside_rth).lower(),
        }
        return self._client.get("/iserver/marketdata/history", params=params)

    def get(
        self,
        conid: int,
        period: str = "1y",
        bar: str = "1d",
        outside_rth: bool = False,
    ) -> pd.DataFrame:
        """Return historical bars as a DataFrame with columns:
        timestamp, open, high, low, close, volume.
        """
        raw = self.get_raw(conid, period, bar, outside_rth)
        return history_to_df(raw)
