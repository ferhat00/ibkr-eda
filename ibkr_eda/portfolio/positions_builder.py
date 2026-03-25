"""Pure functions extracted from the positions-building notebook cell (03_vix_hedge)."""
from __future__ import annotations

import pandas as pd


def build_equity_summary(
    equity_positions: pd.DataFrame,
    prices: dict[str, float],
    total_cash: float,
    net_liquidation: float | None = None,
) -> tuple[pd.DataFrame, float, float]:
    """Attach prices, compute market values and portfolio weights.

    Parameters
    ----------
    equity_positions:
        DataFrame with at least ``ticker`` and ``quantity`` columns.
    prices:
        Map of ticker → last price. Missing tickers produce NaN market values.
    total_cash:
        Cash balance used to compute NAV when ``net_liquidation`` is not given.
    net_liquidation:
        Pre-computed NAV (e.g. from a live account summary). When provided,
        this value is used directly instead of ``total_equity + total_cash``.

    Returns
    -------
    (enriched_df, total_equity, nav)

    Raises
    ------
    ZeroDivisionError
        When the resolved NAV is zero, which would produce infinite weights.
    """
    df = equity_positions.copy()
    df["last_price"] = df["ticker"].map(prices)
    df["market_value"] = df["quantity"] * df["last_price"]

    total_equity = df["market_value"].sum()  # NaN rows are excluded by pandas sum()
    nav = net_liquidation if net_liquidation is not None else total_equity + total_cash

    if nav == 0:
        raise ZeroDivisionError("net_liquidation is 0 — cannot compute weights")

    df["weight"] = df["market_value"] / nav
    return df, total_equity, nav


def extract_summary_value(summary: pd.DataFrame, metric: str) -> float:
    """Extract a float value from an account summary DataFrame by metric name.

    Parameters
    ----------
    summary:
        DataFrame with ``metric`` and ``amount`` columns (amounts may be strings,
        as IBKR returns them).
    metric:
        The metric name to look up, e.g. ``"NetLiquidation"``.

    Returns
    -------
    The parsed float, or ``0.0`` if the metric is absent or non-numeric.
    """
    row = summary[summary["metric"] == metric]
    if row.empty:
        return 0.0
    try:
        return float(row["amount"].iloc[0])
    except (ValueError, TypeError):
        return 0.0
