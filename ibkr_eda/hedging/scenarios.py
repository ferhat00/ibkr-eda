"""Drawdown scenario modelling and VIX hedge payoff calculations."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ibkr_eda.hedging.config import (
    STRESS_EVENTS,
    VIX_MULTIPLIER,
    VIX_RESPONSE_A,
    VIX_RESPONSE_B,
    StressEvent,
)


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------


def estimate_portfolio_beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """OLS beta of *portfolio_returns* vs *benchmark_returns* (numpy-only)."""
    aligned = pd.concat(
        [portfolio_returns, benchmark_returns], axis=1,
    ).dropna()
    if len(aligned) < 20:
        return 1.0
    x = aligned.iloc[:, 1].values
    y = aligned.iloc[:, 0].values
    # np.polyfit(x, y, 1) → [slope, intercept]
    beta = np.polyfit(x, y, 1)[0]
    return float(beta)


def estimate_vix_at_drawdown(current_vix: float, spx_drawdown: float) -> float:
    """Estimate VIX level given an S&P 500 drawdown (negative fraction).

    Uses a pre-fitted power-law:
        VIX ≈ current_vix + A × |drawdown|^B

    The floor is ``current_vix`` (VIX cannot decline in a sell-off scenario).
    """
    if spx_drawdown >= 0:
        return current_vix
    spike = VIX_RESPONSE_A * abs(spx_drawdown) ** VIX_RESPONSE_B
    return current_vix + spike


# ---------------------------------------------------------------------------
# ScenarioEngine
# ---------------------------------------------------------------------------


class ScenarioEngine:
    """Model portfolio drawdowns and VIX call hedge payoffs."""

    def __init__(
        self,
        portfolio_value: float,
        portfolio_beta: float,
        current_vix: float,
    ) -> None:
        self.portfolio_value = portfolio_value
        self.portfolio_beta = portfolio_beta
        self.current_vix = current_vix

    # ------------------------------------------------------------------
    # Core calculations
    # ------------------------------------------------------------------

    def portfolio_drawdown(self, spx_drawdown: float) -> float:
        """Beta-adjusted portfolio drawdown for a given SPX drawdown."""
        return spx_drawdown * self.portfolio_beta

    def vix_at_drawdown(self, spx_drawdown: float) -> float:
        """Estimated VIX level for a given SPX drawdown."""
        return estimate_vix_at_drawdown(self.current_vix, spx_drawdown)

    def call_payoff(
        self,
        strike: float,
        premium: float,
        num_contracts: int,
        vix_at_expiry: float,
    ) -> float:
        """Net payoff (after premium) of a VIX call position.

        Parameters
        ----------
        strike : float
            VIX call strike price.
        premium : float
            Premium paid per contract (in VIX points, e.g. 2.50).
        num_contracts : int
            Number of contracts.
        vix_at_expiry : float
            VIX level at expiry.

        Returns
        -------
        Net P&L in dollars.
        """
        intrinsic = max(0.0, vix_at_expiry - strike) * VIX_MULTIPLIER * num_contracts
        cost = premium * VIX_MULTIPLIER * num_contracts
        return intrinsic - cost

    def hedged_pnl(
        self,
        spx_drawdown: float,
        strike: float,
        premium: float,
        num_contracts: int,
    ) -> dict:
        """Compute hedged portfolio P&L for a given SPX drawdown.

        Returns dict with: portfolio_loss, hedge_gain, net_pnl,
        unhedged_drawdown_pct, hedged_drawdown_pct.
        """
        port_dd = self.portfolio_drawdown(spx_drawdown)
        port_loss = self.portfolio_value * port_dd  # negative
        vix = self.vix_at_drawdown(spx_drawdown)
        hedge = self.call_payoff(strike, premium, num_contracts, vix)
        net = port_loss + hedge
        return {
            "portfolio_loss": port_loss,
            "vix_estimate": vix,
            "hedge_gain": hedge,
            "net_pnl": net,
            "unhedged_drawdown_pct": port_dd,
            "hedged_drawdown_pct": net / self.portfolio_value if self.portfolio_value else 0,
        }

    # ------------------------------------------------------------------
    # Tabular outputs
    # ------------------------------------------------------------------

    def stress_table(
        self,
        strike: float,
        premium: float,
        num_contracts: int,
    ) -> pd.DataFrame:
        """Hedge payoff under each historical stress event.

        Returns DataFrame with one row per :data:`STRESS_EVENTS` entry.
        """
        rows: list[dict] = []
        for ev in STRESS_EVENTS:
            pnl = self.hedged_pnl(ev.spx_drawdown, strike, premium, num_contracts)
            rows.append({
                "event": ev.name,
                "period": f"{ev.start_date} → {ev.end_date}",
                "spx_drawdown": ev.spx_drawdown,
                "vix_start": ev.vix_start,
                "vix_peak": ev.vix_peak,
                "portfolio_loss": pnl["portfolio_loss"],
                "hedge_gain": pnl["hedge_gain"],
                "net_pnl": pnl["net_pnl"],
                "recovery_pct": (
                    -pnl["hedge_gain"] / pnl["portfolio_loss"]
                    if pnl["portfolio_loss"] < 0
                    else 0.0
                ),
            })
        return pd.DataFrame(rows)

    def drawdown_curve(
        self,
        strike: float,
        premium: float,
        num_contracts: int,
        drawdown_range: np.ndarray | None = None,
    ) -> pd.DataFrame:
        """Continuous hedged vs. unhedged portfolio value across drawdowns.

        Parameters
        ----------
        drawdown_range : array-like, optional
            SPX drawdown fractions (negative). Defaults to 0 → -0.50.

        Returns DataFrame with columns: spx_drawdown, vix_estimate,
        unhedged_value, hedge_payout, hedged_value.
        """
        if drawdown_range is None:
            drawdown_range = np.linspace(0, -0.50, 51)

        rows: list[dict] = []
        for dd in drawdown_range:
            pnl = self.hedged_pnl(dd, strike, premium, num_contracts)
            rows.append({
                "spx_drawdown": dd,
                "vix_estimate": pnl["vix_estimate"],
                "unhedged_value": self.portfolio_value + pnl["portfolio_loss"],
                "hedge_payout": pnl["hedge_gain"],
                "hedged_value": self.portfolio_value + pnl["net_pnl"],
            })
        return pd.DataFrame(rows)

    def payoff_matrix(
        self,
        strikes: list[float],
        premiums: dict[float, float],
        num_contracts: int,
        drawdown_range: np.ndarray | None = None,
    ) -> pd.DataFrame:
        """2-D payoff matrix: rows = strikes, columns = drawdown scenarios.

        Parameters
        ----------
        strikes : list[float]
            Strike prices to evaluate.
        premiums : dict[float, float]
            Mapping strike → mid-price premium.
        num_contracts : int
            Number of contracts for each strike.
        drawdown_range : array-like, optional
            SPX drawdown fractions. Defaults to common scenarios.

        Returns DataFrame indexed by strike, columns are drawdown labels,
        values are net P&L in dollars.
        """
        if drawdown_range is None:
            drawdown_range = np.array(
                [-0.05, -0.10, -0.15, -0.20, -0.25, -0.30, -0.40, -0.50],
            )

        matrix: dict[float, dict[str, float]] = {}
        for k in strikes:
            prem = premiums.get(k, 0)
            row: dict[str, float] = {}
            for dd in drawdown_range:
                label = f"{dd:.0%}"
                pnl = self.hedged_pnl(dd, k, prem, num_contracts)
                row[label] = pnl["net_pnl"]
            matrix[k] = row

        return pd.DataFrame(matrix).T.rename_axis("strike")

    def contracts_needed(
        self,
        target_protection_pct: float,
        strike: float,
        target_drawdown: float = -0.30,
    ) -> int:
        """Estimate contracts needed to cover *target_protection_pct* of loss.

        Parameters
        ----------
        target_protection_pct : float
            Fraction of the portfolio loss to hedge (e.g. 0.5 = 50%).
        strike : float
            VIX call strike.
        target_drawdown : float
            SPX drawdown scenario to hedge against (negative).

        Returns
        -------
        Number of contracts (rounded up).
        """
        vix_at_target = self.vix_at_drawdown(target_drawdown)
        per_contract_payoff = max(0.0, vix_at_target - strike) * VIX_MULTIPLIER
        if per_contract_payoff <= 0:
            return 0
        port_loss = abs(self.portfolio_value * self.portfolio_drawdown(target_drawdown))
        target_hedge = port_loss * target_protection_pct
        return math.ceil(target_hedge / per_contract_payoff)
