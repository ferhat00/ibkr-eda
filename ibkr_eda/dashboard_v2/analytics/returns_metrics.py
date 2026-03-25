"""Portfolio performance metrics: Sharpe, Sortino, VaR, CVaR, etc."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ibkr_eda.dashboard_v2.config import RISK_FREE_RATE


def compute_metrics_table(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.DataFrame,
    rf: float = RISK_FREE_RATE,
) -> pd.DataFrame:
    """Compute full metrics table for portfolio and benchmarks.

    Returns DataFrame with metrics as index and Portfolio/benchmark
    columns.
    """
    series = {"Portfolio": portfolio_returns}
    if isinstance(benchmark_returns, pd.Series):
        name = benchmark_returns.name or "Benchmark"
        series[name] = benchmark_returns.dropna()
    else:
        for col in benchmark_returns.columns:
            series[col] = benchmark_returns[col].dropna()

    rows = {}
    for name, rets in series.items():
        rows[name] = _compute_single(rets, rf)

    return pd.DataFrame(rows)


def _compute_single(rets: pd.Series, rf: float) -> dict:
    """Compute all metrics for a single return series."""
    rets = rets.dropna()
    n = len(rets)
    if n < 2:
        return {}

    # Annualised return (geometric)
    total = (1 + rets).prod()
    years = n / 252
    annual_return = total ** (1 / years) - 1 if years > 0 else 0

    # Annualised volatility
    annual_vol = rets.std() * np.sqrt(252)

    # Sharpe
    sharpe = (annual_return - rf) / annual_vol if annual_vol > 0 else 0

    # Sortino (downside deviation)
    downside = rets[rets < 0]
    downside_std = downside.std() * np.sqrt(252) if len(downside) > 0 else 0
    sortino = (annual_return - rf) / downside_std if downside_std > 0 else 0

    # Max drawdown
    cum = (1 + rets).cumprod()
    running_max = cum.cummax()
    dd = (cum - running_max) / running_max
    max_dd = dd.min()

    # Calmar
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

    # VaR and CVaR (95% daily)
    var_95 = np.percentile(rets, 5)
    cvar_95 = rets[rets <= var_95].mean() if len(rets[rets <= var_95]) > 0 else var_95

    # Win rate
    win_rate = (rets > 0).sum() / n

    # Skewness / kurtosis
    skew = stats.skew(rets)
    kurt = stats.kurtosis(rets)  # excess kurtosis

    # Gain/Pain ratio
    gains = rets[rets > 0].sum()
    losses = abs(rets[rets < 0].sum())
    gain_pain = gains / losses if losses > 0 else 0

    return {
        "Annual Return": f"{annual_return:.2%}",
        "Annual Volatility": f"{annual_vol:.2%}",
        "Sharpe Ratio": f"{sharpe:.3f}",
        "Sortino Ratio": f"{sortino:.3f}",
        "Calmar Ratio": f"{calmar:.3f}",
        "Max Drawdown": f"{max_dd:.2%}",
        "VaR (95% daily)": f"{var_95:.2%}",
        "CVaR (95% daily)": f"{cvar_95:.2%}",
        "Win Rate (daily)": f"{win_rate:.2%}",
        "Best Day": f"{rets.max():.2%}",
        "Worst Day": f"{rets.min():.2%}",
        "Skewness": f"{skew:.3f}",
        "Excess Kurtosis": f"{kurt:.3f}",
        "Gain/Pain Ratio": f"{gain_pain:.3f}",
    }


def compute_cumulative_returns(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.DataFrame,
) -> pd.DataFrame:
    """Compute cumulative return series (base 1.0) for portfolio and benchmarks."""
    result = pd.DataFrame(index=portfolio_returns.index)
    result["Portfolio"] = (1 + portfolio_returns).cumprod()

    for col in benchmark_returns.columns:
        aligned = benchmark_returns[col].reindex(portfolio_returns.index).fillna(0)
        result[col] = (1 + aligned).cumprod()

    return result
