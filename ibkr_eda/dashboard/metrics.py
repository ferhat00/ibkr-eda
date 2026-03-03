"""Performance metric computations for the trade dashboard.

All functions are pure — they take a filtered DataFrame and return dicts
ready for JSON serialisation. No side effects, no globals.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _safe(v: float) -> float | None:
    """Convert NaN/inf to None for JSON serialisation."""
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return float(v)


def compute_summary(df: pd.DataFrame) -> dict:
    """Compute headline performance metrics."""
    if df.empty:
        return {
            "total_trades": 0, "buys": 0, "sells": 0,
            "total_pnl": 0, "total_commission": 0,
            "win_rate": None, "profit_factor": None,
            "avg_winner": None, "avg_loser": None,
            "reward_risk": None, "largest_win": None, "largest_loss": None,
            "max_drawdown": None, "sharpe": None, "avg_pnl_per_trade": None,
        }

    is_buy = df["side"].str.upper().isin(["BUY", "BOT"])
    buys = int(is_buy.sum())
    sells = int((~is_buy).sum())

    pnl = df["realized_pnl"].dropna()
    pnl_nonzero = pnl[pnl != 0]
    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]

    gross_profit = float(winners.sum()) if len(winners) else 0.0
    gross_loss = float(losers.sum()) if len(losers) else 0.0

    win_rate = (len(winners) / len(pnl_nonzero) * 100) if len(pnl_nonzero) else None
    profit_factor = (gross_profit / abs(gross_loss)) if gross_loss != 0 else None
    avg_winner = float(winners.mean()) if len(winners) else None
    avg_loser = float(losers.mean()) if len(losers) else None
    reward_risk = (abs(avg_winner) / abs(avg_loser)) if avg_loser else None

    cum_pnl = pnl.cumsum()
    running_max = cum_pnl.cummax()
    drawdown = cum_pnl - running_max
    max_drawdown = float(drawdown.min()) if len(drawdown) else None

    pnl_std = float(pnl.std()) if len(pnl) > 1 else 0
    pnl_mean = float(pnl.mean()) if len(pnl) else 0
    sharpe = (pnl_mean / pnl_std * np.sqrt(252)) if pnl_std > 0 else None

    return {
        "total_trades": len(df),
        "buys": buys,
        "sells": sells,
        "total_pnl": _safe(float(pnl.sum())),
        "total_commission": _safe(float(df["commission"].sum())),
        "win_rate": _safe(win_rate),
        "profit_factor": _safe(profit_factor),
        "avg_winner": _safe(avg_winner),
        "avg_loser": _safe(avg_loser),
        "reward_risk": _safe(reward_risk),
        "largest_win": _safe(float(pnl.max())) if len(pnl) else None,
        "largest_loss": _safe(float(pnl.min())) if len(pnl) else None,
        "max_drawdown": _safe(max_drawdown),
        "sharpe": _safe(sharpe),
        "avg_pnl_per_trade": _safe(pnl_mean),
    }


def compute_cumulative_pnl(df: pd.DataFrame) -> dict:
    """Compute cumulative P&L, running max, and drawdown series."""
    if df.empty:
        return {"timestamps": [], "cum_pnl": [], "drawdown": [], "running_max": []}

    df_sorted = df.dropna(subset=["realized_pnl"]).sort_values("trade_time")
    cum = df_sorted["realized_pnl"].cumsum()
    running_max = cum.cummax()
    dd = cum - running_max

    timestamps = df_sorted["trade_time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist()
    return {
        "timestamps": timestamps,
        "cum_pnl": cum.tolist(),
        "drawdown": dd.tolist(),
        "running_max": running_max.tolist(),
    }


def compute_pnl_distribution(df: pd.DataFrame) -> dict:
    """Return raw realized P&L values for client-side histogram."""
    values = df["realized_pnl"].dropna()
    return {"values": values.tolist()}


def compute_symbol_breakdown(df: pd.DataFrame, top_n: int = 25) -> dict:
    """Trade count and P&L by symbol."""
    if df.empty:
        return {"by_count": {"symbols": [], "counts": []},
                "by_pnl": {"symbols": [], "pnl": []}}

    counts = df.groupby("symbol").size().sort_values(ascending=False).head(top_n)
    pnl = df.groupby("symbol")["realized_pnl"].sum().sort_values()

    return {
        "by_count": {
            "symbols": counts.index.tolist(),
            "counts": counts.values.tolist(),
        },
        "by_pnl": {
            "symbols": pnl.index.tolist(),
            "pnl": [_safe(v) for v in pnl.values],
        },
    }


def compute_time_patterns(df: pd.DataFrame) -> dict:
    """Trade activity and P&L by hour, weekday, and month."""
    if df.empty:
        return {
            "by_hour": {"hours": [], "counts": [], "pnl": []},
            "by_weekday": {"days": [], "counts": [], "pnl": []},
            "by_month": {"months": [], "counts": [], "pnl": []},
        }

    # By hour
    hour_counts = df.groupby("hour").size()
    hour_pnl = df.groupby("hour")["realized_pnl"].sum()
    all_hours = list(range(24))
    hour_counts = hour_counts.reindex(all_hours, fill_value=0)
    hour_pnl = hour_pnl.reindex(all_hours, fill_value=0)

    # By weekday
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts = df.groupby("weekday").size().reindex(day_order).dropna().astype(int)
    day_pnl = df.groupby("weekday")["realized_pnl"].sum().reindex(day_order).dropna()

    # By month
    month_counts = df.groupby("month_str").size().sort_index()
    month_pnl = df.groupby("month_str")["realized_pnl"].sum().sort_index()

    return {
        "by_hour": {
            "hours": all_hours,
            "counts": hour_counts.values.tolist(),
            "pnl": [_safe(v) for v in hour_pnl.values],
        },
        "by_weekday": {
            "days": day_counts.index.tolist(),
            "counts": day_counts.values.tolist(),
            "pnl": [_safe(v) for v in day_pnl.values],
        },
        "by_month": {
            "months": month_counts.index.tolist(),
            "counts": month_counts.values.tolist(),
            "pnl": [_safe(v) for v in month_pnl.values],
        },
    }


def compute_commission_analysis(df: pd.DataFrame) -> dict:
    """Commission distribution and top symbols by commission."""
    if df.empty:
        return {"values": [], "total": 0,
                "by_symbol": {"symbols": [], "total_comm": [], "avg_comm": [], "trade_counts": []}}

    comm = df["commission"].dropna()
    comm_positive = comm[comm > 0]

    by_sym = df.groupby("symbol").agg(
        total_comm=("commission", "sum"),
        avg_comm=("commission", "mean"),
        trade_counts=("commission", "count"),
    ).sort_values("total_comm", ascending=False).head(15)

    return {
        "values": comm_positive.tolist(),
        "total": _safe(float(comm.sum())),
        "by_symbol": {
            "symbols": by_sym.index.tolist(),
            "total_comm": [_safe(v) for v in by_sym["total_comm"].values],
            "avg_comm": [_safe(v) for v in by_sym["avg_comm"].values],
            "trade_counts": by_sym["trade_counts"].values.tolist(),
        },
    }


def compute_market_breakdown(df: pd.DataFrame) -> dict:
    """Breakdown by exchange, currency, country, and security type."""
    if df.empty:
        empty = {"labels": [], "counts": [], "pnl": []}
        return {"by_exchange": empty, "by_currency": empty,
                "by_country": empty, "by_sec_type": empty}

    def _breakdown(col: str) -> dict:
        counts = df.groupby(col).size().sort_values(ascending=False)
        pnl = df.groupby(col)["realized_pnl"].sum()
        pnl = pnl.reindex(counts.index, fill_value=0)
        return {
            "labels": counts.index.tolist(),
            "counts": counts.values.tolist(),
            "pnl": [_safe(v) for v in pnl.values],
        }

    return {
        "by_exchange": _breakdown("exchange"),
        "by_currency": _breakdown("currency"),
        "by_country": _breakdown("country"),
        "by_sec_type": _breakdown("sec_type"),
    }


def compute_trade_table(
    df: pd.DataFrame,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "trade_time",
    sort_dir: str = "desc",
) -> dict:
    """Return paginated, sorted trade data for the table view."""
    columns = [
        "trade_time", "symbol", "sec_type", "side", "quantity",
        "price", "notional", "commission", "realized_pnl",
        "exchange", "country", "currency",
    ]

    if df.empty:
        return {"total_rows": 0, "page": page, "page_size": page_size,
                "columns": columns, "rows": []}

    if sort_by not in columns:
        sort_by = "trade_time"

    ascending = sort_dir.lower() == "asc"
    sorted_df = df.sort_values(sort_by, ascending=ascending)

    start = (page - 1) * page_size
    end = start + page_size
    page_df = sorted_df.iloc[start:end]

    rows = []
    for _, row in page_df.iterrows():
        r = []
        for c in columns:
            val = row[c]
            if c == "trade_time":
                val = val.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(val, float):
                val = _safe(val)
            else:
                val = str(val) if pd.notna(val) else ""
            r.append(val)
        rows.append(r)

    return {
        "total_rows": len(df),
        "page": page,
        "page_size": page_size,
        "columns": columns,
        "rows": rows,
    }
