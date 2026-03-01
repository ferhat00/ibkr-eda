"""Transaction history via TWS API execution reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from ib_async import ExecutionFilter

from ibkr_eda.utils.transformers import trades_to_df

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Transactions:
    """Fetch transaction history via the TWS API.

    Note: TWS API execution history is limited to approximately 7 days,
    unlike the Client Portal PA endpoint which supported up to 90 days.
    """

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        account_ids: list[str] | None = None,
        conids: list[int] | None = None,
        currency: str = "USD",
        days: int = 7,
    ) -> list:
        """Return ib_async Fill objects filtered by account."""
        acct = (account_ids or [self._client.account_id])[0]
        filt = ExecutionFilter(acctCode=acct)
        return self._client.ib.reqExecutions(filt)

    def get(
        self,
        account_ids: list[str] | None = None,
        conids: list[int] | None = None,
        currency: str = "USD",
        days: int = 7,
    ) -> pd.DataFrame:
        """Return transaction history as a DataFrame."""
        raw = self.get_raw(account_ids, conids, currency, days)
        if not raw:
            return pd.DataFrame()
        return trades_to_df(raw)
