"""Contract details by conid."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ib_async import Contract

if TYPE_CHECKING:
    from ibkr_eda.client import IBKRClient


class ContractDetails:
    """Fetch contract details via the TWS API."""

    def __init__(self, client: IBKRClient):
        self._client = client

    def get(self, conid: int) -> dict:
        """Return contract details for a given conid."""
        contract = Contract(conId=conid)
        details_list = self._client.ib.reqContractDetails(contract)
        if not details_list:
            return {}
        d = details_list[0]
        return {
            "conid": d.contract.conId,
            "symbol": d.contract.symbol,
            "secType": d.contract.secType,
            "exchange": d.contract.exchange,
            "currency": d.contract.currency,
            "localSymbol": d.contract.localSymbol,
            "longName": d.longName,
            "category": d.category,
            "industry": d.industry,
            "minTick": d.minTick,
        }
