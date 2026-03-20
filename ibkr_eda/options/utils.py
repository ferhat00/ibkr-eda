"""Helper functions for options data processing."""

from __future__ import annotations

import math
from datetime import date, datetime


# ---------------------------------------------------------------------------
# VIX detection
# ---------------------------------------------------------------------------

_INDEX_SYMBOLS = {"VIX", "SPX", "NDX", "RUT", "DJX"}


def is_index(symbol: str) -> bool:
    """Return True if *symbol* is a cash-settled index (needs special handling)."""
    return symbol.upper() in _INDEX_SYMBOLS


# ---------------------------------------------------------------------------
# Expiry helpers
# ---------------------------------------------------------------------------

def parse_expiry(expiry: str | date) -> date:
    """Parse expiry to a ``date`` object.

    Accepts ``"YYYYMMDD"``, ``"YYYY-MM-DD"``, or a ``date``/``datetime``.
    """
    if isinstance(expiry, datetime):
        return expiry.date()
    if isinstance(expiry, date):
        return expiry
    expiry = expiry.replace("-", "")
    return datetime.strptime(expiry, "%Y%m%d").date()


def expiry_to_ib(expiry: str | date) -> str:
    """Normalize *expiry* to the ``YYYYMMDD`` string used by ib_async."""
    return parse_expiry(expiry).strftime("%Y%m%d")


def days_to_expiry(expiry: str | date) -> int:
    """Calendar days from today until *expiry*."""
    return (parse_expiry(expiry) - date.today()).days


# ---------------------------------------------------------------------------
# Strike helpers
# ---------------------------------------------------------------------------

def find_atm_strike(strikes: list[float], underlying_price: float) -> float:
    """Return the strike closest to *underlying_price*."""
    if not strikes:
        raise ValueError("strikes list is empty")
    return min(strikes, key=lambda s: abs(s - underlying_price))


def filter_strikes(
    strikes: list[float],
    underlying_price: float,
    num_otm: int = 10,
    num_itm: int = 10,
) -> list[float]:
    """Return strikes within *num_otm* / *num_itm* of the ATM strike.

    Strikes are sorted ascending.  The window is centred on the strike
    nearest to *underlying_price*.
    """
    if not strikes:
        return []
    sorted_strikes = sorted(strikes)
    atm = find_atm_strike(sorted_strikes, underlying_price)
    atm_idx = sorted_strikes.index(atm)
    lo = max(0, atm_idx - num_itm)
    hi = min(len(sorted_strikes), atm_idx + num_otm + 1)
    return sorted_strikes[lo:hi]


# ---------------------------------------------------------------------------
# Contract builders (lazy-import ib_async to keep module light)
# ---------------------------------------------------------------------------

def build_underlying_contract(symbol: str):
    """Return an ib_async Stock or Index contract for *symbol*."""
    from ib_async import Index, Stock

    if is_index(symbol.upper()):
        return Index(symbol.upper(), "CBOE", "USD")
    return Stock(symbol.upper(), "SMART", "USD")


def build_option_contract(
    symbol: str,
    expiry: str,
    strike: float,
    right: str,
    exchange: str = "SMART",
    trading_class: str | None = None,
):
    """Return an ib_async ``Option`` contract.

    VIX options require ``tradingClass="VIX"`` — this is handled
    automatically when *trading_class* is ``None`` and *symbol* is ``"VIX"``.
    """
    from ib_async import Option

    sym = symbol.upper()
    exp = expiry_to_ib(expiry)
    right = right.upper()
    tc = trading_class
    if tc is None and is_index(sym):
        tc = sym
    return Option(sym, exp, strike, right, exchange, tradingClass=tc or "")


# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def mid_price(bid: float | None, ask: float | None) -> float | None:
    """Return midpoint of *bid* and *ask*, or ``None`` if either is missing/NaN."""
    if bid is None or ask is None:
        return None
    if math.isnan(bid) or math.isnan(ask):
        return None
    if bid <= 0 and ask <= 0:
        return None
    return round((bid + ask) / 2, 6)
