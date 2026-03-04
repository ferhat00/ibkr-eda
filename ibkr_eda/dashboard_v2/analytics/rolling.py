"""Rolling metrics: Sharpe ratio, volatility, beta."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ibkr_eda.dashboard_v2.config import RISK_FREE_RATE, ROLLING_WINDOW


def rolling_sharpe(
    returns: pd.Series,
    window: int = ROLLING_WINDOW,
    rf: float = RISK_FREE_RATE,
) -> pd.Series:
    """Rolling annualised Sharpe ratio."""
    daily_rf = (1 + rf) ** (1 / 252) - 1
    excess = returns - daily_rf
    roll_mean = excess.rolling(window).mean() * 252
    roll_std = returns.rolling(window).std() * np.sqrt(252)
    return (roll_mean / roll_std).rename("Rolling Sharpe")


def rolling_volatility(
    returns: pd.Series,
    window: int = ROLLING_WINDOW,
) -> pd.Series:
    """Rolling annualised volatility."""
    return (returns.rolling(window).std() * np.sqrt(252)).rename("Rolling Volatility")


def rolling_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    window: int = ROLLING_WINDOW,
) -> pd.Series:
    """Rolling beta vs a benchmark."""
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    if aligned.shape[1] < 2:
        return pd.Series(dtype=float, name="Rolling Beta")
    p, b = aligned.iloc[:, 0], aligned.iloc[:, 1]
    cov = p.rolling(window).cov(b)
    var = b.rolling(window).var()
    return (cov / var).rename("Rolling Beta")


def rolling_sortino(
    returns: pd.Series,
    window: int = ROLLING_WINDOW,
    rf: float = RISK_FREE_RATE,
) -> pd.Series:
    """Rolling annualised Sortino ratio."""
    daily_rf = (1 + rf) ** (1 / 252) - 1

    def _sortino(x):
        excess_mean = (x.mean() - daily_rf) * 252
        down = x[x < 0]
        if len(down) < 2:
            return np.nan
        down_std = down.std() * np.sqrt(252)
        return excess_mean / down_std if down_std > 0 else np.nan

    return returns.rolling(window).apply(_sortino, raw=False).rename("Rolling Sortino")
