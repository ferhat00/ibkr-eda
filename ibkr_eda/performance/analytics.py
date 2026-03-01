"""Portfolio performance analytics.

Note: The Portfolio Analyst (PA) endpoint is not available via the TWS API.
Use the PnL module for daily P&L data instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Performance:
    """Portfolio performance analytics (not available via TWS API)."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        account_ids: list[str] | None = None,
        freq: str = "D",
    ) -> dict:
        """Not available via TWS API."""
        raise NotImplementedError(
            "Portfolio performance analytics (PA endpoint) is not available "
            "via the TWS API. Use ib.pnl.get() for daily P&L data instead."
        )

    def get(
        self,
        account_ids: list[str] | None = None,
        freq: str = "D",
    ) -> pd.DataFrame:
        """Not available via TWS API."""
        raise NotImplementedError(
            "Portfolio performance analytics (PA endpoint) is not available "
            "via the TWS API. Use ib.pnl.get() for daily P&L data instead."
        )
