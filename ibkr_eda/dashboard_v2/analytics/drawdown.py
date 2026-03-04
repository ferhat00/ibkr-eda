"""Drawdown analysis: underwater chart and top drawdown periods."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_underwater(returns: pd.Series) -> pd.Series:
    """Compute drawdown series from daily returns (all values <= 0)."""
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    return (cum - running_max) / running_max


def compute_top_drawdowns(returns: pd.Series, top_n: int = 5) -> pd.DataFrame:
    """Find the top N drawdown periods.

    Returns DataFrame with columns: start, trough, end, depth,
    duration_days, recovery_days.
    """
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    dd = (cum - running_max) / running_max

    periods = []
    in_drawdown = False
    start = None
    trough_val = 0
    trough_date = None

    for i, (dt, val) in enumerate(dd.items()):
        if val < 0:
            if not in_drawdown:
                in_drawdown = True
                start = dt
                trough_val = val
                trough_date = dt
            elif val < trough_val:
                trough_val = val
                trough_date = dt
        else:
            if in_drawdown:
                periods.append({
                    "start": start,
                    "trough": trough_date,
                    "end": dt,
                    "depth": trough_val,
                    "duration_days": (dt - start).days,
                    "recovery_days": (dt - trough_date).days,
                })
                in_drawdown = False

    # Handle drawdown still in progress at end of series
    if in_drawdown:
        periods.append({
            "start": start,
            "trough": trough_date,
            "end": dd.index[-1],
            "depth": trough_val,
            "duration_days": (dd.index[-1] - start).days,
            "recovery_days": np.nan,
        })

    if not periods:
        return pd.DataFrame(
            columns=["start", "trough", "end", "depth", "duration_days", "recovery_days"]
        )

    df = pd.DataFrame(periods).sort_values("depth").head(top_n).reset_index(drop=True)
    return df
