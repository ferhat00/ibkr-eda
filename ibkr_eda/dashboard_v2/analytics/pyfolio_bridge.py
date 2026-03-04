"""Bridge to pyfolio-reloaded: extract stats for Plotly rendering."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_tearsheet_stats(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
) -> dict:
    """Extract pyfolio performance statistics.

    Uses pyfolio's underlying functions to compute stats, then returns
    them as plain dicts for rendering in Plotly/Dash (not matplotlib).
    """
    try:
        import pyfolio as pf
    except ImportError:
        logger.warning("pyfolio-reloaded not installed, tearsheet unavailable.")
        return {"error": "pyfolio-reloaded not installed"}

    result = {}

    # Performance stats
    try:
        perf_stats = pf.timeseries.perf_stats(
            portfolio_returns,
            factor_returns=benchmark_returns,
        )
        result["perf_stats"] = perf_stats.to_dict()
    except Exception as e:
        logger.warning("pyfolio perf_stats failed: %s", e)
        result["perf_stats"] = {}

    # Drawdown table
    try:
        dd_table = pf.timeseries.gen_drawdown_table(portfolio_returns, top=10)
        result["drawdown_table"] = dd_table.to_dict("records")
    except Exception as e:
        logger.warning("pyfolio drawdown table failed: %s", e)
        result["drawdown_table"] = []

    # Monthly returns
    try:
        monthly = pf.timeseries.aggregate_returns(portfolio_returns, "monthly")
        result["monthly_returns"] = monthly.to_dict()
    except Exception as e:
        logger.warning("pyfolio monthly returns failed: %s", e)

    # Annual returns
    try:
        annual = pf.timeseries.aggregate_returns(portfolio_returns, "yearly")
        result["annual_returns"] = annual.to_dict()
    except Exception as e:
        logger.warning("pyfolio annual returns failed: %s", e)

    return result
