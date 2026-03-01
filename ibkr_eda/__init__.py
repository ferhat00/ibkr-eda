"""IBKR Exploratory Data Analysis Toolkit.

Usage::

    from ibkr_eda import IBKR

    ib = IBKR()
    ib.keepalive()

    positions = ib.positions.get()
    summary = ib.accounts.get_summary()
    history = ib.history.get(conid=265598, period="1y", bar="1d")
"""

from ibkr_eda.client import IBKRClient
from ibkr_eda.config import IBKRConfig
from ibkr_eda.contracts.details import ContractDetails
from ibkr_eda.contracts.search import ContractSearch
from ibkr_eda.market_data.history import History
from ibkr_eda.market_data.snapshot import Snapshot
from ibkr_eda.performance.analytics import Performance
from ibkr_eda.portfolio.accounts import Accounts
from ibkr_eda.portfolio.pnl import PnL
from ibkr_eda.portfolio.positions import Positions
from ibkr_eda.trades.executions import Executions
from ibkr_eda.trades.orders import Orders
from ibkr_eda.trades.transactions import Transactions


class IBKR:
    """High-level facade — one object gives access to everything.

    Args:
        config: Optional IBKRConfig. If omitted, loads from .env / defaults.
    """

    def __init__(self, config: IBKRConfig | None = None):
        self.client = IBKRClient(config)

        # Portfolio
        self.accounts = Accounts(self.client)
        self.positions = Positions(self.client)
        self.pnl = PnL(self.client)

        # Trades
        self.orders = Orders(self.client)
        self.executions = Executions(self.client)
        self.transactions = Transactions(self.client)

        # Market data
        self.snapshot = Snapshot(self.client)
        self.history = History(self.client)

        # Contracts
        self.contract_search = ContractSearch(self.client)
        self.contract_details = ContractDetails(self.client)

        # Performance
        self.performance = Performance(self.client)

    def status(self) -> dict:
        """Check authentication status."""
        return self.client.auth_status()

    def keepalive(self) -> None:
        """Start background keepalive (calls /tickle every ~4 min)."""
        self.client.start_keepalive()

    def stop_keepalive(self) -> None:
        """Stop background keepalive."""
        self.client.stop_keepalive()


__all__ = ["IBKR", "IBKRClient", "IBKRConfig"]
