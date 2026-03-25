"""Risk contribution analysis per asset."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_risk_contribution(
    asset_returns: pd.DataFrame,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Compute component risk contribution for each asset.

    If weights are not provided, uses equal weights.

    Returns DataFrame with columns: asset, weight, marginal_risk,
    risk_contribution, pct_contribution.
    """
    assets = asset_returns.columns.tolist()
    n = len(assets)

    if weights is None:
        w = np.ones(n) / n
    else:
        w = np.array([weights.get(a, 0) for a in assets])
        if w.sum() > 0:
            w = w / w.sum()

    active = (w > 0).sum()
    if active < 2:
        import warnings
        warnings.warn(
            f"compute_risk_contribution: only {active} asset(s) have non-zero weight — "
            "result will be degenerate. Check that weights keys match asset column names."
        )

    cov = asset_returns.cov().values * 252  # annualised
    port_var = w @ cov @ w
    port_vol = np.sqrt(port_var)

    # Marginal risk contribution
    marginal = cov @ w / port_vol
    # Component risk contribution
    component = w * marginal
    # Percentage contribution (share of total portfolio volatility)
    total_rc = component.sum()
    pct = component / total_rc if total_rc > 0 else component

    return pd.DataFrame({
        "asset": assets,
        "weight": w,
        "marginal_risk": marginal,
        "risk_contribution": component,
        "pct_contribution": pct,
    })
