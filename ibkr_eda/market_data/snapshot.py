"""Real-time market data snapshots."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient

# Common market data field IDs
FIELDS = {
    "last": "31",
    "bid": "84",
    "ask": "86",
    "open": "7295",
    "high": "70",
    "low": "71",
    "close": "7291",
    "volume": "87",
    "change": "82",
    "change_pct": "83",
    "market_cap": "7289",
    "pe_ratio": "7290",
    "div_yield": "7287",
    "52w_high": "7293",
    "52w_low": "7294",
    "symbol": "55",
    "name": "7051",
}


class Snapshot:
    """Fetch market data snapshots from the IBKR Client Portal API.

    Note: The first call to the snapshot endpoint for a conid "subscribes" to
    the data but may return empty/partial results. A second call after a short
    delay returns the actual data. This class handles the two-call pattern
    automatically.
    """

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        conids: list[int],
        fields: list[str] | None = None,
        retry_delay: float = 0.5,
    ) -> list[dict]:
        """Return raw market data snapshot JSON.

        Args:
            conids: List of contract IDs (max 100).
            fields: List of field IDs (max 50). Defaults to common fields.
            retry_delay: Seconds to wait before the second (data) call.
        """
        if fields is None:
            fields = [FIELDS["last"], FIELDS["change_pct"], FIELDS["volume"],
                      FIELDS["bid"], FIELDS["ask"]]

        params = {
            "conids": ",".join(str(c) for c in conids),
            "fields": ",".join(fields),
        }

        # First call subscribes
        self._client.get("/iserver/marketdata/snapshot", params=params)
        time.sleep(retry_delay)
        # Second call gets the data
        return self._client.get("/iserver/marketdata/snapshot", params=params)

    def get(
        self,
        conids: list[int],
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        """Return market data snapshot as a DataFrame."""
        raw = self.get_raw(conids, fields)
        if not raw:
            return pd.DataFrame()
        return pd.json_normalize(raw)

    def unsubscribe(self, conid: int) -> dict:
        """Unsubscribe from market data for a conid."""
        return self._client.get(f"/iserver/marketdata/{conid}/unsubscribe")

    def unsubscribe_all(self) -> dict:
        """Unsubscribe from all market data."""
        return self._client.get("/iserver/marketdata/unsubscribeall")
