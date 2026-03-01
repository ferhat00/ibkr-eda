"""Portfolio performance analytics via the PA endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Performance:
    """Fetch portfolio performance data from the IBKR PA endpoint."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        account_ids: list[str] | None = None,
        freq: str = "D",
    ) -> dict:
        """Return raw portfolio performance JSON.

        Args:
            account_ids: List of account IDs. Defaults to the primary account.
            freq: Frequency — 'D' (daily), 'M' (monthly), 'Q' (quarterly).
        """
        acct_ids = account_ids or [self._client.account_id]
        body = {
            "acctIds": acct_ids,
            "freq": freq,
        }
        return self._client.post("/pa/performance", json=body)

    def get(
        self,
        account_ids: list[str] | None = None,
        freq: str = "D",
    ) -> pd.DataFrame:
        """Return portfolio performance as a DataFrame.

        Extracts the cumulative returns time series from the PA response.
        """
        raw = self.get_raw(account_ids, freq)

        # The PA response nests data under various keys depending on API version
        # Common structure: {"currencyType": "base", "data": [...], ...}
        # or nested under "nav", "cps" (cumulative performance series)
        if not raw:
            return pd.DataFrame()

        # Try to extract time-series data from common response shapes
        if "nav" in raw and isinstance(raw["nav"], dict):
            nav_data = raw["nav"].get("data", [])
            if nav_data:
                return pd.json_normalize(nav_data)

        if "cps" in raw and isinstance(raw["cps"], dict):
            cps_data = raw["cps"].get("data", [])
            if cps_data:
                return pd.json_normalize(cps_data)

        # Fallback: flatten whatever the response contains
        return pd.json_normalize(raw)
