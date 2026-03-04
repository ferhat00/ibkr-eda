"""Static and rolling correlation analysis."""

from __future__ import annotations

import pandas as pd

from ibkr_eda.dashboard_v2.config import ROLLING_WINDOW


def compute_correlation_matrix(asset_returns: pd.DataFrame) -> pd.DataFrame:
    """Static Pearson correlation matrix across all assets."""
    return asset_returns.corr()


def compute_rolling_correlation(
    asset_returns: pd.DataFrame,
    window: int = ROLLING_WINDOW,
) -> dict[str, pd.DataFrame]:
    """Rolling pairwise correlation for each asset pair.

    Returns dict mapping "A_vs_B" → Series of rolling correlation.
    """
    cols = asset_returns.columns.tolist()
    result = {}
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            key = f"{a} vs {b}"
            result[key] = asset_returns[a].rolling(window).corr(asset_returns[b])
    return result
