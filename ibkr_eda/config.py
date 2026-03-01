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
        )
