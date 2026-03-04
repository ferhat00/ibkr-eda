"""Portfolio optimization using riskfolio-lib."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_efficient_frontier(
    asset_returns: pd.DataFrame,
    n_points: int = 50,
    rf: float = 0.045,
) -> dict:
    """Compute efficient frontier and optimal portfolios.

    Returns dict with:
        frontier   – list of {return, risk, sharpe} points
        portfolios – dict of portfolio type → {weights, return, risk, sharpe}
    """
    import riskfolio as rp

    # Drop assets with insufficient data
    min_obs = 60
    valid_cols = [c for c in asset_returns.columns if asset_returns[c].dropna().shape[0] >= min_obs]
    if len(valid_cols) < 2:
        return {"error": "Need at least 2 assets with 60+ days of data"}

    returns = asset_returns[valid_cols].dropna()

    port = rp.Portfolio(returns=returns)
    port.assets_stats(method_mu="hist", method_cov="hist")

    portfolios = {}

    # Max Sharpe
    try:
        w = port.optimization(model="Classic", rm="MV", obj="Sharpe", rf=rf / 252)
        if w is not None and not w.empty:
            portfolios["Max Sharpe"] = _portfolio_stats(w, returns, rf)
    except Exception as e:
        logger.warning("Max Sharpe optimization failed: %s", e)

    # Min Volatility
    try:
        w = port.optimization(model="Classic", rm="MV", obj="MinRisk", rf=rf / 252)
        if w is not None and not w.empty:
            portfolios["Min Volatility"] = _portfolio_stats(w, returns, rf)
    except Exception as e:
        logger.warning("Min Vol optimization failed: %s", e)

    # Risk Parity (equal risk contribution)
    try:
        w = port.rp_optimization(model="Classic", rm="MV", rf=rf / 252)
        if w is not None and not w.empty:
            portfolios["Risk Parity"] = _portfolio_stats(w, returns, rf)
    except Exception as e:
        logger.warning("Risk Parity optimization failed: %s", e)

    # Max Diversification
    try:
        w = port.optimization(model="Classic", rm="MV", obj="MaxRet", rf=rf / 252)
        if w is not None and not w.empty:
            portfolios["Max Return"] = _portfolio_stats(w, returns, rf)
    except Exception as e:
        logger.warning("Max Return optimization failed: %s", e)

    # Efficient frontier points
    frontier = []
    try:
        ef = port.efficient_frontier(
            model="Classic", rm="MV", points=n_points, rf=rf / 252
        )
        if ef is not None and not ef.empty:
            for i in range(ef.shape[1]):
                w_col = ef.iloc[:, i]
                stats = _portfolio_stats(w_col.to_frame(), returns, rf)
                frontier.append({
                    "return": stats["annual_return"],
                    "risk": stats["annual_vol"],
                    "sharpe": stats["sharpe"],
                })
    except Exception as e:
        logger.warning("Efficient frontier computation failed: %s", e)

    return {"frontier": frontier, "portfolios": portfolios}


def _portfolio_stats(
    weights: pd.DataFrame, returns: pd.DataFrame, rf: float
) -> dict:
    """Compute stats for a portfolio given weights and asset returns."""
    w = weights.values.flatten()
    asset_names = returns.columns.tolist()

    port_returns = returns.values @ w
    annual_return = float(np.mean(port_returns) * 252)
    annual_vol = float(np.std(port_returns) * np.sqrt(252))
    sharpe = (annual_return - rf) / annual_vol if annual_vol > 0 else 0

    weight_dict = {asset_names[i]: float(w[i]) for i in range(len(w)) if abs(w[i]) > 1e-6}

    return {
        "weights": weight_dict,
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "sharpe": sharpe,
    }
