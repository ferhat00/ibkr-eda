"""Optimal VIX hedge selection and rollover cost estimation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ibkr_eda.hedging.config import HEDGE_PROFILES, VIX_MULTIPLIER
from ibkr_eda.hedging.scenarios import ScenarioEngine


class HedgeAdvisor:
    """Select optimal VIX call hedges across conservative / moderate / aggressive profiles."""

    def __init__(
        self,
        vix_calls: pd.DataFrame,
        engine: ScenarioEngine,
        current_vix: float,
    ) -> None:
        self.calls = vix_calls.copy()
        self.engine = engine
        self.current_vix = current_vix

    # ------------------------------------------------------------------
    # Per-profile recommendation
    # ------------------------------------------------------------------

    def recommend(self, profile: str = "moderate") -> pd.Series | None:
        """Return the best VIX call for *profile*, or ``None`` if none qualifies.

        Scoring: ``payoff_ratio_40 × log1p(open_interest)`` to balance
        leverage with liquidity.
        """
        cfg = HEDGE_PROFILES.get(profile)
        if cfg is None:
            raise ValueError(f"Unknown profile: {profile!r}. Choose from {list(HEDGE_PROFILES)}")

        df = self.calls.copy()
        if df.empty:
            return None

        # Ensure numeric columns
        for col in ("moneyness", "cost_bps", "days_to_expiry", "payoff_ratio_40",
                     "open_interest", "mid", "strike", "cost_per_contract"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # --- Filters ---
        otm_lo, otm_hi = cfg["otm_range"]
        if "moneyness" in df.columns:
            df = df[(df["moneyness"] >= otm_lo) & (df["moneyness"] <= otm_hi)]

        if "days_to_expiry" in df.columns:
            df = df[
                (df["days_to_expiry"] >= cfg["min_dte"])
                & (df["days_to_expiry"] <= cfg["max_dte"])
            ]

        if "cost_bps" in df.columns:
            df = df[df["cost_bps"] <= cfg["max_cost_bps"]]

        if df.empty:
            return None

        # --- Scoring ---
        pr = df["payoff_ratio_40"].fillna(0) if "payoff_ratio_40" in df.columns else 0
        oi = df["open_interest"].fillna(0) if "open_interest" in df.columns else 1
        df = df.copy()
        df["score"] = pr * np.log1p(oi)

        best_idx = df["score"].idxmax()
        best = df.loc[best_idx].copy()

        # Add contracts needed for this profile's target drawdown
        target_dd = -cfg["target_drawdown"]  # convert to negative
        strike = float(best["strike"])
        mid = float(best.get("mid", 0))
        n = self.engine.contracts_needed(0.5, strike, target_dd)  # 50% coverage
        best["contracts_needed"] = n
        best["total_cost"] = mid * VIX_MULTIPLIER * n
        best["total_cost_bps"] = (
            best["total_cost"] / self.engine.portfolio_value * 10_000
            if self.engine.portfolio_value > 0
            else 0
        )
        best["profile"] = profile
        best["profile_description"] = cfg["description"]

        # Protection at VIX = 40, 60
        for lvl in (40, 60):
            payout = max(0.0, lvl - strike) * VIX_MULTIPLIER * n
            net = payout - best["total_cost"]
            best[f"net_payout_vix_{lvl}"] = net

        return best

    # ------------------------------------------------------------------
    # All profiles
    # ------------------------------------------------------------------

    def recommend_all(self) -> pd.DataFrame:
        """One row per profile with the recommended hedge."""
        rows: list[pd.Series] = []
        for profile in HEDGE_PROFILES:
            rec = self.recommend(profile)
            if rec is not None:
                rows.append(rec)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)

        # Select and order key columns for display
        display_cols = [
            "profile", "profile_description", "strike", "expiry",
            "days_to_expiry", "mid", "cost_per_contract", "cost_bps",
            "breakeven_vix", "contracts_needed", "total_cost", "total_cost_bps",
            "payoff_ratio_40", "net_payout_vix_40", "net_payout_vix_60",
        ]
        present = [c for c in display_cols if c in df.columns]
        return df[present].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Rollover cost
    # ------------------------------------------------------------------

    @staticmethod
    def rollover_cost(
        near_mid: float,
        far_mid: float,
        days_between: int,
        portfolio_value: float,
    ) -> dict:
        """Estimate cost of rolling a VIX call position from near to far expiry.

        Parameters
        ----------
        near_mid : float
            Mid price of the near-expiry contract being sold.
        far_mid : float
            Mid price of the far-expiry contract being bought.
        days_between : int
            Calendar days between the two expirations.
        portfolio_value : float
            Total portfolio NAV.

        Returns
        -------
        Dict with roll_cost, roll_cost_per_contract, annualized_cost_bps.
        """
        roll_cost = (far_mid - near_mid) * VIX_MULTIPLIER
        ann_factor = 365 / max(days_between, 1)
        annualized_cost = roll_cost * ann_factor
        annualized_bps = (
            annualized_cost / portfolio_value * 10_000
            if portfolio_value > 0
            else 0.0
        )
        return {
            "near_mid": near_mid,
            "far_mid": far_mid,
            "days_between": days_between,
            "roll_cost_per_contract": roll_cost,
            "annualized_cost_per_contract": annualized_cost,
            "annualized_cost_bps": annualized_bps,
        }

    # ------------------------------------------------------------------
    # Summary card data
    # ------------------------------------------------------------------

    def summary_card(self) -> dict:
        """Key recommendation data for notebook HTML display."""
        rec = self.recommend("moderate")
        if rec is None:
            return {"available": False}

        return {
            "available": True,
            "profile": "moderate",
            "strike": float(rec.get("strike", 0)),
            "expiry": str(rec.get("expiry", "")),
            "days_to_expiry": int(rec.get("days_to_expiry", 0)),
            "mid": float(rec.get("mid", 0)),
            "contracts": int(rec.get("contracts_needed", 0)),
            "total_cost": float(rec.get("total_cost", 0)),
            "total_cost_bps": float(rec.get("total_cost_bps", 0)),
            "breakeven_vix": float(rec.get("breakeven_vix", 0)),
            "current_vix": self.current_vix,
        }
