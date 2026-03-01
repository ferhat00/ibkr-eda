"""Contract details by conid."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class ContractDetails:
    """Fetch contract details from the IBKR Client Portal API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get(self, conid: int) -> dict:
        """Return contract details for a given conid."""
        return self._client.get(f"/iserver/contract/{conid}/info")
