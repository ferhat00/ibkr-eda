"""Configuration management for IBKR IB Gateway (TWS API) connection."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class IBKRConfig:
    """Configuration for the IB Gateway (TWS API) connection."""

    host: str = "127.0.0.1"
    port: int = 4002  # 4001 = live, 4002 = paper
    client_id: int = 1
    timeout: int = 15  # connection timeout in seconds
    account_id: str | None = None
    flex_token: str | None = None      # Flex Web Service access token
    flex_query_id: str | None = None   # Flex Query template ID
    tradier_token: str | None = None   # Tradier sandbox API token (optional)
    options_cache_ttl: int = 300       # Fallback provider cache TTL in seconds
    market_data_type: int = 1         # 1=Live, 2=Frozen, 3=Delayed, 4=Delayed-frozen

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> IBKRConfig:
        """Load configuration from environment variables / .env file."""
        load_dotenv(dotenv_path)
        return cls(
            host=os.getenv("IBKR_TWS_HOST", cls.host),
            port=int(os.getenv("IBKR_TWS_PORT", str(cls.port))),
            client_id=int(os.getenv("IBKR_TWS_CLIENT_ID", str(cls.client_id))),
            timeout=int(os.getenv("IBKR_TIMEOUT", str(cls.timeout))),
            account_id=os.getenv("IBKR_ACCOUNT_ID") or None,
            flex_token=os.getenv("IBKR_FLEX_TOKEN") or None,
            flex_query_id=os.getenv("IBKR_FLEX_QUERY_ID") or None,
            tradier_token=os.getenv("TRADIER_TOKEN") or None,
            options_cache_ttl=int(os.getenv("OPTIONS_CACHE_TTL", "300")),
            market_data_type=int(os.getenv("IBKR_MARKET_DATA_TYPE", "1")),
        )
