"""Account listing, summary, and allocation data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Accounts:
    """Access account-level data from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def list_accounts(self) -> list[dict]:
        """Return all linked accounts (read-only, no brokerage session needed)."""
        return self._client.get("/portfolio/accounts")

    def get_summary_raw(self, account_id: str | None = None) -> dict:
        """Return raw account summary JSON."""
        acct = account_id or self._client.account_id
        return self._client.get(f"/portfolio/{acct}/summary")

    def get_summary(self, account_id: str | None = None) -> pd.DataFrame:
        """Return account summary as a DataFrame (one row per metric)."""
        raw = self.get_summary_raw(account_id)
        rows = []
        for key, val in raw.items():
            if isinstance(val, dict):
                rows.append({"metric": key, **val})
            else:
                rows.append({"metric": key, "amount": val})
        return pd.DataFrame(rows)

    def get_allocation_raw(self, account_id: str | None = None) -> dict:
        """Return raw asset allocation JSON."""
        acct = account_id or self._client.account_id
        return self._client.get(f"/portfolio/{acct}/allocation")

    def get_allocation(self, account_id: str | None = None) -> dict[str, pd.DataFrame]:
        """Return asset allocation as a dict of DataFrames by category.

        Keys typically include 'assetClass', 'sector', 'group'.
        """
        raw = self.get_allocation_raw(account_id)
        result = {}
        for category, data in raw.items():
            if isinstance(data, dict) and data:
                # Each category is {long: {...}, short: {...}}
                rows = []
                for direction, values in data.items():
                    if isinstance(values, dict):
                        for name, weight in values.items():
                            rows.append({
                                "name": name,
                                "direction": direction,
                                "weight": weight,
                            })
                if rows:
                    result[category] = pd.DataFrame(rows)
        return result
