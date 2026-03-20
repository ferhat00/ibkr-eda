"""Core data structures and provider protocol for options data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class OptionQuote:
    """Single option contract quote with Greeks."""

    symbol: str                    # underlying symbol
    expiry: str                    # "YYYYMMDD"
    strike: float
    right: str                     # "C" or "P"
    last: float | None = None
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None       # (bid + ask) / 2
    volume: int | None = None
    open_interest: int | None = None
    implied_vol: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    underlying_price: float | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class OptionChainData:
    """Full option chain for one symbol + expiry."""

    symbol: str
    underlying_price: float
    expiry: str
    calls: pd.DataFrame
    puts: pd.DataFrame


@dataclass(frozen=True, slots=True)
class VolSurfaceData:
    """Implied volatility surface across strikes and expirations."""

    symbol: str
    underlying_price: float
    strikes: np.ndarray            # 1-D array of strike prices
    expiries: list[str]            # list of "YYYYMMDD" strings
    call_iv: np.ndarray            # 2-D: [expiry_idx, strike_idx]
    put_iv: np.ndarray             # 2-D: [expiry_idx, strike_idx]
    timestamp: datetime


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class OptionsProvider(Protocol):
    """Interface for options data providers (IBKR TWS or fallback)."""

    def get_expirations(self, symbol: str, exchange: str = "SMART") -> list[str]:
        """Return sorted list of available expiry strings (YYYYMMDD)."""
        ...

    async def get_expirations_async(
        self, symbol: str, exchange: str = "SMART",
    ) -> list[str]:
        """Async variant of get_expirations."""
        ...

    def get_chain(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> list[OptionQuote]:
        """Return all option quotes for a symbol + expiry."""
        ...

    async def get_chain_async(
        self, symbol: str, expiry: str, exchange: str = "SMART",
    ) -> list[OptionQuote]:
        """Async variant of get_chain."""
        ...

    def get_greeks(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        """Return Greeks for a single option contract."""
        ...

    async def get_greeks_async(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        """Async variant of get_greeks."""
        ...

    def get_iv_surface(
        self, symbol: str, exchange: str = "SMART",
    ) -> VolSurfaceData:
        """Build implied volatility surface for a symbol."""
        ...

    async def get_iv_surface_async(
        self, symbol: str, exchange: str = "SMART",
    ) -> VolSurfaceData:
        """Async variant of get_iv_surface."""
        ...
