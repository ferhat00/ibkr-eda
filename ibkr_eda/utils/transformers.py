"""Helpers for transforming IBKR API JSON responses into pandas DataFrames."""

from __future__ import annotations

import pandas as pd


# ── Column rename maps ───────────────────────────────────────────────

_POSITION_COLUMNS = {
    "conid": "contract_id",
    "contractDesc": "description",
    "assetClass": "asset_class",
    "mktValue": "market_value",
    "unrealizedPnl": "unrealized_pnl",
    "realizedPnl": "realized_pnl",
    "avgCost": "avg_cost",
    "avgPrice": "avg_price",
    "position": "quantity",
    "currency": "currency",
    "ticker": "ticker",
    "listingExchange": "exchange",
}

_TRADE_COLUMNS = {
    "conid": "contract_id",
    "conidEx": "contract_id_ex",
    "execution_id": "execution_id",
    "symbol": "symbol",
    "side": "side",
    "size": "quantity",
    "price": "price",
    "order_ref": "order_ref",
    "account": "account_id",
    "exchange": "exchange",
    "net_amount": "net_amount",
    "commission": "commission",
    "realized_pnl": "realized_pnl",
    "trade_time_r": "trade_time_epoch",
    "trade_time": "trade_time",
}


# ── Transformer functions ────────────────────────────────────────────

def positions_to_df(raw: list[dict]) -> pd.DataFrame:
    """Convert raw positions JSON to a clean DataFrame."""
    df = pd.json_normalize(raw)
    df.rename(
        columns={k: v for k, v in _POSITION_COLUMNS.items() if k in df.columns},
        inplace=True,
    )
    return df


def trades_to_df(raw: list[dict]) -> pd.DataFrame:
    """Convert raw trades/executions JSON to a clean DataFrame."""
    df = pd.json_normalize(raw)
    df.rename(
        columns={k: v for k, v in _TRADE_COLUMNS.items() if k in df.columns},
        inplace=True,
    )
    return df


def history_to_df(raw: dict) -> pd.DataFrame:
    """Convert raw historical market data JSON to a DataFrame with timestamps."""
    data = raw.get("data", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "t" in df.columns:
        df["timestamp"] = pd.to_datetime(df["t"], unit="ms")
        df.rename(
            columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"},
            inplace=True,
        )
        df.drop(columns=["t"], inplace=True, errors="ignore")
    return df


def orders_to_df(raw: list[dict]) -> pd.DataFrame:
    """Convert raw orders JSON to a DataFrame."""
    if not raw:
        return pd.DataFrame()
    return pd.json_normalize(raw)
