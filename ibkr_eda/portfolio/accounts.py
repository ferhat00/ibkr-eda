"""Account listing, summary, and allocation data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class Accounts:
    """Access account-level data via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def list_accounts(self) -> list[dict]:
        """Return all managed accounts."""
        accounts = self._client.ib.managedAccounts()
        return [{"accountId": a} for a in accounts]

    def get_summary_raw(self, account_id: str | None = None) -> list:
        """Return raw account summary (list of AccountValue objects)."""
        acct = account_id or self._client.account_id
        return self._client.ib.accountSummary(acct)

    _SUMMARY_COLUMNS = ["metric", "amount", "currency"]

    async def get_summary_async(self, account_id: str | None = None) -> pd.DataFrame:
        """Async version of get_summary — required when called from a running event loop (e.g. Jupyter)."""
        acct = account_id or self._client.account_id
        raw = await self._client.ib.accountSummaryAsync(acct)
        if not raw:
            # Return empty DataFrame with the correct schema so callers can safely
            # do summary["metric"] without KeyError (pd.DataFrame() has RangeIndex columns)
            return pd.DataFrame(columns=self._SUMMARY_COLUMNS)
        rows = [{"metric": av.tag, "amount": av.value, "currency": av.currency} for av in raw]
        return pd.DataFrame(rows)

    def get_summary(self, account_id: str | None = None) -> pd.DataFrame:
        """Return account summary as a DataFrame (one row per metric)."""
        raw = self.get_summary_raw(account_id)
        if not raw:
            return pd.DataFrame(columns=self._SUMMARY_COLUMNS)
        rows = []
        for av in raw:
            rows.append({
                "metric": av.tag,
                "amount": av.value,
                "currency": av.currency,
            })
        return pd.DataFrame(rows)

    def get_allocation(self, account_id: str | None = None) -> dict[str, pd.DataFrame]:
        """Return asset allocation computed from current positions.

        Returns a dict with key 'assetClass' mapping to a DataFrame
        with columns: name, direction, weight.
        """
        acct = account_id or self._client.account_id
        all_positions = self._client.ib.positions()
        positions = [p for p in all_positions if p.account == acct]

        if not positions:
            return {}

        # Group by asset class (secType)
        totals: dict[str, float] = {}
        for p in positions:
            sec_type = p.contract.secType
            value = abs(p.position * p.avgCost)
            totals[sec_type] = totals.get(sec_type, 0.0) + value

        grand_total = sum(totals.values())
        if grand_total == 0:
            return {}

        rows = []
        for name, value in totals.items():
            rows.append({
                "name": name,
                "direction": "long",
                "weight": value / grand_total,
            })
        return {"assetClass": pd.DataFrame(rows)}
