"""Calendar return heatmaps and day-of-week analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monthly_returns(returns: pd.Series) -> pd.DataFrame:
    """Pivot monthly returns into Year × Month matrix.

    Returns DataFrame with years as index, months (1-12) as columns.
    """
    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    monthly = r.groupby([r.index.year, r.index.month]).apply(
        lambda x: (1 + x).prod() - 1
    )
    monthly.index.names = ["Year", "Month"]
    pivoted = monthly.unstack(level="Month")
    pivoted.columns = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][:len(pivoted.columns)]

    # Add YTD column
    pivoted["YTD"] = pivoted.apply(lambda row: (1 + row.dropna()).prod() - 1, axis=1)
    return pivoted


def weekly_returns_by_day(returns: pd.Series) -> pd.DataFrame:
    """Group returns by day of week for box plot analysis.

    Returns DataFrame with columns: day_name, return.
    """
    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    df = pd.DataFrame({"return": r.values, "day_name": r.index.day_name()})
    # Order days correctly
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    df["day_name"] = pd.Categorical(df["day_name"], categories=day_order, ordered=True)
    return df.dropna()
