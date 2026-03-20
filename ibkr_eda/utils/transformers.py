"""Helpers for transforming ib_async objects into pandas DataFrames."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd


def positions_to_df(positions: list) -> pd.DataFrame:
    """Convert ib_async Position objects to a DataFrame."""
    if not positions:
        return pd.DataFrame()
    rows = []
    for p in positions:
        rows.append({
            "contract_id": p.contract.conId,
            "description": p.contract.localSymbol or p.contract.symbol,
            "asset_class": p.contract.secType,
            "quantity": p.position,
            "avg_cost": p.avgCost,
            "currency": p.contract.currency,
            "ticker": p.contract.symbol,
            "exchange": p.contract.primaryExchange or p.contract.exchange,
            "account_id": p.account,
        })
    return pd.DataFrame(rows)


def trades_to_df(fills: list) -> pd.DataFrame:
    """Convert ib_async Fill objects to a DataFrame."""
    if not fills:
        return pd.DataFrame()
    rows = []
    for f in fills:
        rows.append({
            "contract_id": f.contract.conId,
            "execution_id": f.execution.execId,
            "symbol": f.contract.symbol,
            "sec_type": f.contract.secType,
            "currency": f.contract.currency,
            "side": f.execution.side,
            "quantity": f.execution.shares,
            "price": f.execution.price,
            "order_ref": f.execution.orderRef,
            "account_id": f.execution.acctNumber,
            "exchange": f.execution.exchange,
            "commission": f.commissionReport.commission if f.commissionReport else None,
            "realized_pnl": f.commissionReport.realizedPNL if f.commissionReport else None,
            "trade_time": str(f.execution.time),
        })
    return pd.DataFrame(rows)


def history_to_df(bars: list) -> pd.DataFrame:
    """Convert ib_async BarData objects to a DataFrame."""
    if not bars:
        return pd.DataFrame()
    rows = []
    for b in bars:
        rows.append({
            "timestamp": b.date,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        })
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def option_quotes_to_df(quotes: list) -> pd.DataFrame:
    """Convert OptionQuote dataclass instances to a DataFrame.

    Args:
        quotes: List of ``OptionQuote`` objects.

    Returns:
        DataFrame with columns: symbol, expiry, strike, right, last, bid, ask,
        mid, volume, open_interest, implied_vol, delta, gamma, theta, vega,
        rho, underlying_price, timestamp.
    """
    if not quotes:
        return pd.DataFrame()
    return pd.DataFrame([asdict(q) for q in quotes])


def orders_to_df(trades: list) -> pd.DataFrame:
    """Convert ib_async Trade objects to a DataFrame."""
    if not trades:
        return pd.DataFrame()
    rows = []
    for t in trades:
        rows.append({
            "orderId": t.order.orderId,
            "conid": t.contract.conId,
            "symbol": t.contract.symbol,
            "action": t.order.action,
            "totalQuantity": t.order.totalQuantity,
            "orderType": t.order.orderType,
            "lmtPrice": t.order.lmtPrice,
            "status": t.orderStatus.status,
            "filled": t.orderStatus.filled,
            "remaining": t.orderStatus.remaining,
            "avgFillPrice": t.orderStatus.avgFillPrice,
        })
    return pd.DataFrame(rows)
