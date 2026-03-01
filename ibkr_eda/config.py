"""Configuration management for IBKR Client Portal API connection."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class IBKRConfig:
    """Configuration for the IBKR Client Portal API client."""

    base_url: str = "https://localhost:5000/v1/api"
    verify_ssl: bool = False
    request_timeout: int = 15
    tickle_interval: int = 240  # seconds (under 5-min session timeout)
    rate_limit: int = 10  # requests per second
    account_id: str | None = None

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> IBKRConfig:
        """Load configuration from environment variables / .env file."""
        load_dotenv(dotenv_path)
        return cls(
            base_url=os.getenv("IBKR_BASE_URL", cls.base_url),
            verify_ssl=os.getenv("IBKR_VERIFY_SSL", "false").lower() == "true",
            request_timeout=int(os.getenv("IBKR_REQUEST_TIMEOUT", str(cls.request_timeout))),
            tickle_interval=int(os.getenv("IBKR_TICKLE_INTERVAL", str(cls.tickle_interval))),
            rate_limit=int(os.getenv("IBKR_RATE_LIMIT", str(cls.rate_limit))),
            account_id=os.getenv("IBKR_ACCOUNT_ID") or None,
        )
