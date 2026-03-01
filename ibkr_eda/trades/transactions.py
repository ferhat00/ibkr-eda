"""Transaction history via Portfolio Analyst (PA) endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Transactions:
    """Fetch transaction history from the IBKR PA endpoint."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get_raw(
        self,
        account_ids: list[str] | None = None,
        conids: list[int] | None = None,
        currency: str = "USD",
        days: int = 90,
    ) -> dict:
        """Return raw transaction history JSON."""
        acct_ids = account_ids or [self._client.account_id]
        body: dict = {
            "acctIds": acct_ids,
            "currency": currency,
            "days": days,
        }
        if conids:
            body["conids"] = conids
        return self._client.post("/pa/transactions", json=body)

    def get(
        self,
        account_ids: list[str] | None = None,
        conids: list[int] | None = None,
        currency: str = "USD",
        days: int = 90,
    ) -> pd.DataFrame:
        """Return transaction history as a DataFrame."""
        raw = self.get_raw(account_ids, conids, currency, days)
        transactions = raw.get("transactions", [])
        if not transactions:
            return pd.DataFrame()
        return pd.json_normalize(transactions)
