"""Contract/symbol search."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class ContractSearch:
    """Search for contracts by symbol via the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def search_raw(self, symbol: str, sec_type: str | None = None) -> list[dict]:
        """Return raw contract search results JSON."""
        body: dict = {"symbol": symbol}
        if sec_type:
            body["secType"] = sec_type
        result = self._client.post("/iserver/secdef/search", json=body)
        if isinstance(result, list):
            return result
        return result.get("results", result.get("data", []))

    def search(self, symbol: str, sec_type: str | None = None) -> pd.DataFrame:
        """Search for contracts by symbol and return as a DataFrame."""
        raw = self.search_raw(symbol, sec_type)
        if not raw:
            return pd.DataFrame()
        return pd.json_normalize(raw)
