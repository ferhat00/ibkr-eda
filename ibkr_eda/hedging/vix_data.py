"""VIX options chain fetching and enrichment for hedge analysis.

VIX options are **European-style** and **cash-settled**.  They settle against
the Special Opening Quotation (SOQ) of the VIX index — *not* the spot VIX
level.  The SOQ is calculated from the opening prices of S&P 500 options on
settlement morning and can differ materially from the prior close or real-time
VIX.  All payoff models in this module use spot VIX as a proxy since the SOQ
is not observable in advance.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ibkr_eda.hedging.config import VIX_MULTIPLIER
from ibkr_eda.options.utils import days_to_expiry

if TYPE_CHECKING:
    from ibkr_eda.options.chain import OptionChains

logger = logging.getLogger(__name__)


class VIXData:
    """Fetch and enrich VIX call options for portfolio insurance analysis."""

    def __init__(
        self,
        options: OptionChains | None = None,
        source: str | None = None,
        tradier_token: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        options:
            Pre-built OptionChains instance (e.g. from a live IBKR connection).
            When provided, *source* and *tradier_token* are ignored.
        source:
            Which free data backend to use: ``'yfinance'``, ``'cboe'``,
            ``'tradier'``, or ``'barchart'``.  ``None`` (default) tries all
            four in order, falling through to the next source if no bid/ask
            prices are available.
        tradier_token:
            Tradier sandbox bearer token.  Required when ``source='tradier'``.
        """
        if options is not None:
            self._options = options
        else:
            from ibkr_eda.options.chain import OptionChains
            from ibkr_eda.options.fallback_provider import FallbackOptionsProvider

            self._options = OptionChains(
                provider=FallbackOptionsProvider(
                    tradier_token=tradier_token,
                    source=source,
                )
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_expirations(self) -> list[str]:
        """Return sorted list of available VIX option expiry dates (YYYYMMDD)."""
        return self._options.get_expirations("VIX")

    async def get_expirations_async(self) -> list[str]:
        """Async variant — required in Jupyter where an event loop is already running."""
        return await self._options.get_expirations_async("VIX")

    def get_calls(
        self,
        expiry: str,
        portfolio_value: float,
        min_oi: int = 0,
    ) -> pd.DataFrame:
        """Fetch VIX calls for *expiry* and enrich with hedge metrics.

        Parameters
        ----------
        expiry : str
            Expiry date (YYYYMMDD or YYYY-MM-DD).
        portfolio_value : float
            Total portfolio NAV — used to express costs in basis points.
        min_oi : int
            Minimum open interest filter (0 = no filter).

        Returns
        -------
        DataFrame with columns from the raw chain plus:
            days_to_expiry, moneyness, cost_per_contract, cost_bps,
            breakeven_vix, payoff_at_40, payoff_at_60, payoff_at_80,
            payoff_ratio_40.
        """
        df = self._options.get_df("VIX", expiry)
        if df.empty:
            logger.warning("Empty chain returned for VIX expiry %s", expiry)
            return df

        # Filter to calls only
        df = df[df["right"] == "C"].copy()
        if df.empty:
            return df

        df = self._enrich(df, portfolio_value)

        # Apply open-interest filter
        if min_oi > 0 and "open_interest" in df.columns:
            oi = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)
            df = df[oi >= min_oi]

        return df.sort_values("strike").reset_index(drop=True)

    async def get_calls_async(
        self,
        expiry: str,
        portfolio_value: float,
        min_oi: int = 0,
    ) -> pd.DataFrame:
        """Async variant of get_calls — required in Jupyter where an event loop is already running."""
        df = await self._options.get_df_async("VIX", expiry)
        if df.empty:
            logger.warning("Empty chain returned for VIX expiry %s", expiry)
            return df

        df = df[df["right"] == "C"].copy()
        if df.empty:
            return df

        df = self._enrich(df, portfolio_value)

        if min_oi > 0 and "open_interest" in df.columns:
            oi = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)
            df = df[oi >= min_oi]

        return df.sort_values("strike").reset_index(drop=True)

    def get_term_structure(self, portfolio_value: float) -> pd.DataFrame:
        """ATM call mid-price across all available expirations.

        Useful for estimating rollover costs and visualising the VIX
        options term structure.
        """
        rows: list[dict] = []
        for exp in self.get_expirations():
            try:
                calls = self.get_calls(exp, portfolio_value)
                if calls.empty:
                    continue
                # Find ATM: closest strike to underlying
                und = pd.to_numeric(calls["underlying_price"], errors="coerce").iloc[0]
                if pd.isna(und) or und <= 0:
                    continue
                idx = (calls["strike"] - und).abs().idxmin()
                atm = calls.loc[idx]
                rows.append({
                    "expiry": exp,
                    "days_to_expiry": atm.get("days_to_expiry", days_to_expiry(exp)),
                    "atm_strike": atm["strike"],
                    "atm_mid": atm.get("mid", atm.get("last")),
                    "cost_per_contract": atm.get("cost_per_contract"),
                    "cost_bps": atm.get("cost_bps"),
                    "underlying_price": und,
                })
            except Exception:
                logger.debug("Skipping expiry %s in term structure", exp, exc_info=True)
                continue

        return pd.DataFrame(rows)

    async def get_term_structure_async(self, portfolio_value: float) -> pd.DataFrame:
        """Async variant of get_term_structure — required in Jupyter where an event loop is already running."""
        rows: list[dict] = []
        for exp in await self.get_expirations_async():
            try:
                calls = await self.get_calls_async(exp, portfolio_value)
                if calls.empty:
                    continue
                und = pd.to_numeric(calls["underlying_price"], errors="coerce").iloc[0]
                if pd.isna(und) or und <= 0:
                    continue
                idx = (calls["strike"] - und).abs().idxmin()
                atm = calls.loc[idx]
                rows.append({
                    "expiry": exp,
                    "days_to_expiry": atm.get("days_to_expiry", days_to_expiry(exp)),
                    "atm_strike": atm["strike"],
                    "atm_mid": atm.get("mid", atm.get("last")),
                    "cost_per_contract": atm.get("cost_per_contract"),
                    "cost_bps": atm.get("cost_bps"),
                    "underlying_price": und,
                })
            except Exception:
                logger.debug("Skipping expiry %s in term structure", exp, exc_info=True)
                continue
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich(df: pd.DataFrame, portfolio_value: float) -> pd.DataFrame:
        """Add hedge-specific computed columns to a VIX calls DataFrame."""
        # Days to expiry
        if "expiry" in df.columns:
            df["days_to_expiry"] = df["expiry"].apply(
                lambda e: days_to_expiry(e) if pd.notna(e) else np.nan,
            )

        # Underlying price
        und = pd.to_numeric(df.get("underlying_price"), errors="coerce")

        # Mid price — always fill NaN values per-row using cascading fallbacks:
        #   1. Existing mid (from provider: usually mid_price(bid,ask) or last)
        #   2. (bid + ask) / 2 where both are valid
        #   3. Last traded price
        #   4. Intrinsic value for ITM calls (conservative floor)
        bid = pd.to_numeric(df.get("bid"), errors="coerce")
        ask = pd.to_numeric(df.get("ask"), errors="coerce")
        last = pd.to_numeric(df.get("last"), errors="coerce")

        if "mid" in df.columns:
            mid = pd.to_numeric(df["mid"], errors="coerce")
        else:
            mid = pd.Series(np.nan, index=df.index)

        # Fallback 1: (bid + ask) / 2 where both positive
        ba_mid = pd.Series(
            np.where((bid > 0) & (ask > 0), (bid + ask) / 2, np.nan),
            index=df.index,
        )
        mid = mid.fillna(ba_mid)

        # Fallback 2: last traded price
        mid = mid.fillna(last)

        # Fallback 3: intrinsic value for ITM calls
        # VIX calls: intrinsic = max(0, underlying - strike)
        if und.notna().any():
            und_scalar = und.dropna().iloc[0] if und.notna().any() else np.nan
            intrinsic = np.maximum(0, und_scalar - df["strike"])
            mid = mid.fillna(intrinsic.where(intrinsic > 0))

        df["mid"] = mid
        mid = pd.to_numeric(df["mid"], errors="coerce")

        # Moneyness: (strike - underlying) / underlying  (positive = OTM for calls)
        df["moneyness"] = np.where(und > 0, (df["strike"] - und) / und, np.nan)

        # Cost metrics
        df["cost_per_contract"] = mid * VIX_MULTIPLIER
        if portfolio_value > 0:
            df["cost_bps"] = df["cost_per_contract"] / portfolio_value * 10_000
        else:
            df["cost_bps"] = np.nan

        # Breakeven VIX level (for long call: strike + premium)
        df["breakeven_vix"] = df["strike"] + mid

        # Payoff at specific VIX levels
        for level in (40, 60, 80):
            col = f"payoff_at_{level}"
            df[col] = np.maximum(0, level - df["strike"]) * VIX_MULTIPLIER

        # Payoff ratio (leverage) at VIX = 40
        cost = df["cost_per_contract"]
        df["payoff_ratio_40"] = np.where(cost > 0, df["payoff_at_40"] / cost, 0.0)

        return df
