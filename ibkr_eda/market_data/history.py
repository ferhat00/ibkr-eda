"""Historical market data (OHLCV bars)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from ib_async import Contract

from ibkr_eda.utils.transformers import history_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient

# Map shorthand period strings to TWS durationStr format
_PERIOD_MAP = {
    "1d": "1 D",
    "1w": "1 W",
    "1m": "1 M",
    "3m": "3 M",
    "6m": "6 M",
    "1y": "1 Y",
    "5y": "5 Y",
}

# Map shorthand bar strings to TWS barSizeSetting format
_BAR_MAP = {
    "1min": "1 min",
    "5min": "5 mins",
    "15min": "15 mins",
    "30min": "30 mins",
    "1h": "1 hour",
    "1d": "1 day",
    "1w": "1 week",
    "1m": "1 month",
}


class History:
    """Fetch historical market data via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        conid: int,
        period: str = "1y",
        bar: str = "1d",
        outside_rth: bool = False,
    ) -> list:
        """Return raw ib_async BarData objects.

        Args:
            conid: Contract ID.
            period: Time period (e.g., '1d', '1w', '1m', '3m', '6m', '1y', '5y').
            bar: Bar size (e.g., '1min', '5min', '1h', '1d', '1w', '1m').
            outside_rth: Include data outside regular trading hours.
        """
        contract = Contract(conId=conid)
        self._client.ib.qualifyContracts(contract)
        duration = _PERIOD_MAP.get(period, period)
        bar_size = _BAR_MAP.get(bar, bar)
        return self._client.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=not outside_rth,
        )

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
