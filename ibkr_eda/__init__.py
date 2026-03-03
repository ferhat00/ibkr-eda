"""IBKR Exploratory Data Analysis Toolkit.

Usage::

    from ibkr_eda import IBKR

    ib = IBKR()  # auto-connects to IB Gateway

    positions = ib.positions.get()
    summary = ib.accounts.get_summary()
    history = ib.history.get(conid=265598, period="1y", bar="1d")

    ib.disconnect()
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
from ibkr_eda.trades.flex import FlexTrades
from ibkr_eda.trades.orders import Orders
from ibkr_eda.trades.transactions import Transactions


class IBKR:
    """High-level facade — one object gives access to everything.

    Automatically connects to IB Gateway on creation.

    Args:
        config: Optional IBKRConfig. If omitted, loads from .env / defaults.
        auto_connect: Set to False to skip auto-connect (use ``create_async`` instead).

    For Jupyter / Python 3.14+, use the async factory instead::

        ib = await IBKR.create_async()
    """

    def __init__(self, config: IBKRConfig | None = None, auto_connect: bool = True):
        self.client = IBKRClient(config)
        self._init_modules()
        if auto_connect:
            self.client.connect()

    def _init_modules(self) -> None:
        # Portfolio
        self.accounts = Accounts(self.client)
        self.positions = Positions(self.client)
        self.pnl = PnL(self.client)

        # Trades
        self.orders = Orders(self.client)
        self.executions = Executions(self.client)
        self.transactions = Transactions(self.client)

        # Long-history via Flex Web Service (no TWS connection required)
        cfg = self.client.config
        if cfg.flex_token and cfg.flex_query_id:
            self.flex_trades: FlexTrades | None = FlexTrades(cfg)
        else:
            self.flex_trades = None

        # Market data
        self.snapshot = Snapshot(self.client)
        self.history = History(self.client)

        # Contracts
        self.contract_search = ContractSearch(self.client)
        self.contract_details = ContractDetails(self.client)

        # Performance
        self.performance = Performance(self.client)

    @classmethod
    async def create_async(cls, config: IBKRConfig | None = None) -> "IBKR":
        """Create and connect to IB Gateway (async, for Jupyter / Python 3.14+).

        Usage::

            ib = await IBKR.create_async()
        """
        instance = cls(config, auto_connect=False)
        await instance.client.connect_async()
        return instance

    def status(self) -> dict:
        """Check connection status."""
        return {
            "connected": self.client.ib.isConnected(),
            "accounts": self.client.ib.managedAccounts(),
        }

    def connect(self) -> None:
        """Connect to IB Gateway (if not already connected)."""
        self.client.connect()

    def disconnect(self) -> None:
        """Disconnect from IB Gateway."""
        self.client.disconnect()

    def keepalive(self) -> None:
        """No-op. TWS connection is persistent. Kept for backward compatibility."""
        pass

    def stop_keepalive(self) -> None:
        """Alias for disconnect(). Kept for backward compatibility."""
        self.disconnect()


__all__ = ["IBKR", "IBKRClient", "IBKRConfig"]
