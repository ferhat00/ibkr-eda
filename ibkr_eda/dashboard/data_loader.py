"""Data loading and enrichment for the trade dashboard."""

from __future__ import annotations

import glob
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exchange → Country mapping
# ---------------------------------------------------------------------------
EXCHANGE_COUNTRY: dict[str, str] = {
    # United States
    "ARCA": "US", "NASDAQ": "US", "NYSE": "US", "AMEX": "US",
    "ISLAND": "US", "DARK": "US", "DRCTEDGE": "US", "IBKRATS": "US",
    "BYX": "US", "MEMX": "US", "NYSENAT": "US", "PEARL": "US",
    "IEX": "US", "EDGEA": "US", "BATS": "US",
    # FX
    "IDEALFX": "FX", "FXCONV": "FX",
    # Hong Kong
    "SEHK": "HK", "SEHKSZSE": "HK", "SEHKNTL": "HK",
    # United Kingdom
    "LSE": "UK", "LSEETF": "UK", "TRQXUK": "UK", "TRWBUKETF": "UK",
    # Germany
    "IBIS": "DE", "GETTEX2": "DE", "TGATE": "DE",
    # France
    "SBF": "FR",
    # Netherlands
    "AEB": "NL",
    # Denmark
    "CPH": "DK", "DXEDK": "DK",
    # Canada
    "TSE": "CA", "AEQLIT": "CA", "AEQNEO": "CA", "PURE": "CA",
    # Australia
    "ASX": "AU",
    # Pan-Europe
    "EUDARK": "EU",
    # Japan
    "TSEJ": "JP",
    # Singapore
    "SGX": "SG",
}

SECTYPE_LABEL: dict[str, str] = {
    "STK": "Equities",
    "CASH": "FX / Cash",
    "FUT": "Futures",
    "OPT": "Options",
    "ETF": "ETF",
    "BOND": "Fixed Income",
}

# ---------------------------------------------------------------------------
# Module-level state (single-process; not gunicorn-safe)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_df: pd.DataFrame | None = None
_last_source: str = ""
_last_loaded_at: datetime | None = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _find_csv() -> Path:
    """Auto-detect the first trades CSV in data/."""
    pattern = str(PROJECT_ROOT / "data" / "trades_*.csv")
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"No CSV found matching {pattern}. "
            "Fetch data first via the notebook or use Live Flex."
        )
    return Path(matches[0])


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived analysis columns — mirrors the notebook feature engineering."""
    df = df.copy()
    df["notional"] = df["quantity"] * df["price"]
    df["date"] = df["trade_time"].dt.normalize()
    df["hour"] = df["trade_time"].dt.hour
    df["weekday"] = df["trade_time"].dt.day_name()
    df["month_str"] = df["trade_time"].dt.strftime("%Y-%m")
    df["country"] = df["exchange"].map(EXCHANGE_COUNTRY).fillna("Other")
    df["sec_label"] = df["sec_type"].map(SECTYPE_LABEL).fillna(df["sec_type"])
    return df


def load_from_csv(path: str | None = None) -> pd.DataFrame:
    """Load trade data from a local CSV file."""
    global _df, _last_source, _last_loaded_at

    csv_path = Path(path) if path else _find_csv()
    logger.info("Loading CSV from %s", csv_path)

    df = pd.read_csv(csv_path, parse_dates=["trade_time"])
    df["trade_time"] = pd.to_datetime(df["trade_time"], utc=True)
    df = df.sort_values("trade_time").reset_index(drop=True)
    df = add_derived_columns(df)

    with _lock:
        _df = df
        _last_source = f"csv:{csv_path}"
        _last_loaded_at = datetime.now(timezone.utc)

    logger.info("Loaded %d rows from CSV.", len(df))
    return df


def load_from_flex() -> pd.DataFrame:
    """Load trade data live via the IBKR Flex Web Service."""
    global _df, _last_source, _last_loaded_at

    from ibkr_eda.config import IBKRConfig
    from ibkr_eda.trades.flex import FlexTrades

    config = IBKRConfig.from_env()
    flex = FlexTrades(config)
    df = flex.get()

    if df.empty:
        raise ValueError("Flex query returned no data.")

    df = add_derived_columns(df)

    with _lock:
        _df = df
        _last_source = "live"
        _last_loaded_at = datetime.now(timezone.utc)

    logger.info("Loaded %d rows from Flex.", len(df))
    return df


def get_df() -> pd.DataFrame | None:
    """Thread-safe read of the current DataFrame."""
    with _lock:
        return _df


def get_status() -> dict[str, Any]:
    """Return current data status and available filter options."""
    with _lock:
        df = _df
        source = _last_source
        loaded_at = _last_loaded_at

    if df is None:
        return {"loaded": False, "row_count": 0, "source": "", "filter_options": {}}

    date_min = df["trade_time"].min().strftime("%Y-%m-%d")
    date_max = df["trade_time"].max().strftime("%Y-%m-%d")

    return {
        "loaded": True,
        "row_count": len(df),
        "source": source,
        "last_loaded_at": loaded_at.isoformat() if loaded_at else None,
        "date_range": [date_min, date_max],
        "filter_options": {
            "exchanges": sorted(df["exchange"].dropna().unique().tolist()),
            "sec_types": sorted(df["sec_type"].dropna().unique().tolist()),
            "currencies": sorted(df["currency"].dropna().unique().tolist()),
            "countries": sorted(df["country"].dropna().unique().tolist()),
            "symbols": sorted(df["symbol"].dropna().unique().tolist()),
            "sides": sorted(df["side"].dropna().unique().tolist()),
        },
    }
