"""VIX portfolio insurance: hedge analysis, scenarios, and recommendations."""

from ibkr_eda.hedging.recommendations import HedgeAdvisor
from ibkr_eda.hedging.scenarios import ScenarioEngine, estimate_portfolio_beta, estimate_vix_at_drawdown
from ibkr_eda.hedging.vix_data import VIXData

__all__ = [
    "HedgeAdvisor",
    "ScenarioEngine",
    "VIXData",
    "estimate_portfolio_beta",
    "estimate_vix_at_drawdown",
]
