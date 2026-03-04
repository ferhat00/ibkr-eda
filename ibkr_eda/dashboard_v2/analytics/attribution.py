"""Holdings performance attribution and waterfall chart data."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_holdings_contribution(
    weights: pd.DataFrame,
    asset_returns: pd.DataFrame,
) -> pd.Series:
    """Compute total contribution of each holding to portfolio return.

    Parameters
    ----------
    weights : DataFrame indexed by date, columns = symbols (daily weights)
    asset_returns : DataFrame indexed by date, columns = symbols (daily returns)

    Returns
    -------
    Series indexed by symbol with total contribution values.
    """
    aligned_w, aligned_r = weights.align(asset_returns, join="inner")
    daily_contrib = aligned_w * aligned_r
    total = daily_contrib.sum()
    return total.sort_values(ascending=False)


def compute_waterfall(contributions: pd.Series, top_n: int = 20) -> dict:
    """Format contribution data for waterfall chart.

    Returns dict with keys: labels, values, measure (for plotly waterfall).
    """
    # Take top N by absolute value
    top = contributions.reindex(
        contributions.abs().sort_values(ascending=False).head(top_n).index
    ).sort_values(ascending=False)

    labels = top.index.tolist()
    values = top.values.tolist()
    measure = ["relative"] * len(labels)

    # Add total bar
    labels.append("Total")
    values.append(sum(values))
    measure.append("total")

    return {"labels": labels, "values": values, "measure": measure}


def compute_risk_return_scatter(
    asset_returns: pd.DataFrame,
) -> pd.DataFrame:
    """Compute annualised return vs risk for each asset.

    Returns DataFrame with columns: symbol, annual_return, annual_vol.
    """
    stats = []
    for col in asset_returns.columns:
        rets = asset_returns[col].dropna()
        if len(rets) < 20:
            continue
        ann_ret = (1 + rets.mean()) ** 252 - 1
        ann_vol = rets.std() * np.sqrt(252)
        stats.append({
            "symbol": col,
            "annual_return": ann_ret,
            "annual_vol": ann_vol,
        })
    return pd.DataFrame(stats)
