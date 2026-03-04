"""Monte Carlo simulation for VaR and CVaR."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ibkr_eda.dashboard_v2.config import MC_HORIZON_DAYS, MC_SIMULATIONS


def simulate(
    returns: pd.Series,
    n_simulations: int = MC_SIMULATIONS,
    horizon: int = MC_HORIZON_DAYS,
    seed: int = 42,
) -> dict:
    """Run Monte Carlo simulation using bootstrap resampling.

    Returns
    -------
    dict with keys:
        paths         – ndarray (n_simulations × horizon) cumulative returns
        final_returns – 1-D array of terminal cumulative returns
        var_95        – 95% VaR (loss) over horizon
        cvar_95       – 95% CVaR over horizon
        var_99        – 99% VaR
        cvar_99       – 99% CVaR
        percentiles   – dict of 5th/25th/50th/75th/95th percentile paths
    """
    rng = np.random.default_rng(seed)
    rets = returns.dropna().values

    # Bootstrap: sample daily returns with replacement
    sampled = rng.choice(rets, size=(n_simulations, horizon), replace=True)
    paths = np.cumprod(1 + sampled, axis=1)
    final = paths[:, -1] - 1  # terminal return

    var_95 = np.percentile(final, 5)
    cvar_95 = final[final <= var_95].mean() if np.any(final <= var_95) else var_95
    var_99 = np.percentile(final, 1)
    cvar_99 = final[final <= var_99].mean() if np.any(final <= var_99) else var_99

    # Percentile paths for fan chart
    pct_keys = [5, 25, 50, 75, 95]
    percentile_paths = {
        p: np.percentile(paths, p, axis=0) for p in pct_keys
    }

    return {
        "paths": paths,
        "final_returns": final,
        "var_95": float(var_95),
        "cvar_95": float(cvar_95),
        "var_99": float(var_99),
        "cvar_99": float(cvar_99),
        "percentiles": percentile_paths,
    }
