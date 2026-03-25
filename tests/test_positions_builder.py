"""
Tests for ibkr_eda.portfolio.positions_builder.

Coverage matrix
---------------
Function                  | Happy | Edge | Failure
build_equity_summary      |   ✓   |  ✓   |   ✓
extract_summary_value     |   ✓   |  ✓   |   ✓
Accounts.get_summary_async|   ✓   |  ✓   |   ✓   (suggested test #3)
"""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
import pytest_asyncio  # noqa: F401 — ensures the plugin is importable

from ibkr_eda.portfolio.positions_builder import build_equity_summary, extract_summary_value


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def three_stock_positions() -> pd.DataFrame:
    return pd.DataFrame({
        "ticker": ["AAPL", "MSFT", "GOOG"],
        "quantity": [10, 5, 2],
        "avg_cost": [150.0, 300.0, 2_800.0],
    })


@pytest.fixture()
def three_stock_prices() -> dict[str, float]:
    # AAPL: 10 × 200 = 2_000
    # MSFT:  5 × 400 = 2_000
    # GOOG:  2 × 3000 = 6_000
    # total equity = 10_000
    return {"AAPL": 200.0, "MSFT": 400.0, "GOOG": 3_000.0}


@pytest.fixture()
def account_summary_df() -> pd.DataFrame:
    """Simulates what Accounts.get_summary() returns (amounts as strings)."""
    return pd.DataFrame({
        "metric": ["NetLiquidation", "TotalCashValue", "BuyingPower"],
        "amount": ["100000.0", "25000.0", "50000.0"],
        "currency": ["USD", "USD", "USD"],
    })


# ===========================================================================
# build_equity_summary — happy path
# ===========================================================================

def test_build_equity_summary_market_values(three_stock_positions, three_stock_prices):
    """Validates market_value = quantity × last_price for every row."""
    df, _, _ = build_equity_summary(three_stock_positions, three_stock_prices, total_cash=0.0)

    expected = pd.Series([2_000.0, 2_000.0, 6_000.0], name="market_value")
    pd.testing.assert_series_equal(df["market_value"], expected, check_names=False)


def test_build_equity_summary_weights_sum_to_one(three_stock_positions, three_stock_prices):
    """Validates that weights across all positions sum to 1.0 when cash=0."""
    df, _, _ = build_equity_summary(three_stock_positions, three_stock_prices, total_cash=0.0)
    assert df["weight"].sum() == pytest.approx(1.0)


def test_build_equity_summary_nav_equals_equity_plus_cash(three_stock_positions, three_stock_prices):
    """Validates NAV = total_equity + total_cash when net_liquidation not provided."""
    _, total_equity, nav = build_equity_summary(
        three_stock_positions, three_stock_prices, total_cash=5_000.0
    )
    assert total_equity == pytest.approx(10_000.0)
    assert nav == pytest.approx(15_000.0)


# ===========================================================================
# build_equity_summary — edge cases
# ===========================================================================

@pytest.mark.parametrize("missing_ticker", ["AAPL", "MSFT", "GOOG"])
def test_build_equity_summary_missing_price_produces_nan(
    three_stock_positions, three_stock_prices, missing_ticker
):
    """
    Validates that a ticker absent from the price dict produces NaN
    market_value rather than a wrong numeric result or a KeyError.
    """
    prices = {k: v for k, v in three_stock_prices.items() if k != missing_ticker}
    df, _, _ = build_equity_summary(three_stock_positions, prices, total_cash=10_000.0)

    nan_mask = df["ticker"] == missing_ticker
    assert df.loc[nan_mask, "market_value"].isna().all(), (
        f"Expected NaN market_value for {missing_ticker} with no price"
    )


def test_build_equity_summary_uses_provided_net_liquidation(
    three_stock_positions, three_stock_prices
):
    """
    Validates that a pre-computed net_liquidation (live account) overrides
    the cash-based calculation, so weights reflect true portfolio exposure.
    """
    df, _, nav = build_equity_summary(
        three_stock_positions, three_stock_prices,
        total_cash=0.0, net_liquidation=20_000.0,
    )
    assert nav == pytest.approx(20_000.0)
    # equity = 10_000 → weights should sum to 0.5, not 1.0
    assert df["weight"].sum() == pytest.approx(0.5)


# ===========================================================================
# build_equity_summary — suggested test #1
# All prices missing but cash is present → NAV still resolves, no crash
# ===========================================================================

def test_build_equity_summary_all_prices_missing_with_cash(three_stock_positions):
    """
    Validates that when fetch_current_prices returns nothing but cash > 0,
    NAV = total_cash (equity NaN-sum = 0) and weights are NaN for all rows
    rather than crashing or silently computing wrong values.
    """
    df, total_equity, nav = build_equity_summary(
        three_stock_positions, prices={}, total_cash=30_000.0
    )

    # pandas .sum() skips NaN → total_equity resolves to 0 (no valid prices)
    assert total_equity == pytest.approx(0.0)
    assert nav == pytest.approx(30_000.0)

    # All last_price values are NaN → all market_value and weight are NaN
    assert df["last_price"].isna().all(), "Expected all last_prices to be NaN"
    assert df["weight"].isna().all(), "Expected all weights to be NaN (NaN / nav)"


# ===========================================================================
# build_equity_summary — suggested test #2
# Single position → weight must be exactly 1.0
# ===========================================================================

def test_build_equity_summary_single_position_weight_is_one():
    """
    Validates that a one-stock portfolio with no cash produces weight == 1.0
    exactly, catching any floating-point division quirk in the weight formula.
    """
    positions = pd.DataFrame({"ticker": ["SPY"], "quantity": [100], "avg_cost": [450.0]})
    prices = {"SPY": 500.0}

    df, total_equity, nav = build_equity_summary(positions, prices, total_cash=0.0)

    assert total_equity == pytest.approx(50_000.0)
    assert nav == pytest.approx(50_000.0)
    assert df["weight"].iloc[0] == pytest.approx(1.0)


# ===========================================================================
# build_equity_summary — failure / exception path
# ===========================================================================

def test_build_equity_summary_raises_on_zero_nav(three_stock_positions):
    """
    Validates ZeroDivisionError when all prices are missing AND cash=0,
    preventing silent propagation of inf/NaN weights downstream.
    """
    with pytest.raises(ZeroDivisionError, match="net_liquidation is 0"):
        build_equity_summary(three_stock_positions, prices={}, total_cash=0.0)


def test_build_equity_summary_raises_when_explicit_nav_is_zero(three_stock_positions, three_stock_prices):
    """
    Validates ZeroDivisionError even when prices are available but the caller
    explicitly passes net_liquidation=0 (e.g. a broken live account response).
    """
    with pytest.raises(ZeroDivisionError, match="net_liquidation is 0"):
        build_equity_summary(
            three_stock_positions, three_stock_prices,
            total_cash=0.0, net_liquidation=0.0,
        )


# ===========================================================================
# extract_summary_value — happy path
# ===========================================================================

@pytest.mark.parametrize("metric,expected", [
    ("NetLiquidation", 100_000.0),
    ("TotalCashValue", 25_000.0),
    ("BuyingPower", 50_000.0),
])
def test_extract_summary_value_known_metrics(account_summary_df, metric, expected):
    """
    Validates correct float extraction for all standard IBKR metrics,
    including that string-typed amounts (as returned by the API) are cast.
    """
    assert extract_summary_value(account_summary_df, metric) == pytest.approx(expected)


# ===========================================================================
# extract_summary_value — edge cases
# ===========================================================================

def test_extract_summary_value_missing_metric_returns_zero(account_summary_df):
    """
    Validates that a metric absent from the summary returns 0.0 rather than
    raising KeyError or returning NaN, guarding against silent NAV=0 bugs.
    """
    assert extract_summary_value(account_summary_df, "GrossBuyingPower") == 0.0


def test_extract_summary_value_empty_dataframe_returns_zero():
    """Validates graceful handling of an empty summary (e.g. disconnected session)."""
    assert extract_summary_value(pd.DataFrame(columns=["metric", "amount"]), "NetLiquidation") == 0.0


# ===========================================================================
# extract_summary_value — failure / exception path
# ===========================================================================

@pytest.mark.parametrize("bad_value", ["N/A", "", "n/a", "undefined", None])
def test_extract_summary_value_non_numeric_returns_zero(bad_value):
    """
    Validates graceful fallback for non-castable IBKR amounts (e.g. 'N/A'
    for accounts where a metric is not applicable) so callers don't get
    a ValueError crashing the notebook cell.
    """
    df = pd.DataFrame({"metric": ["NetLiquidation"], "amount": [bad_value], "currency": ["USD"]})
    assert extract_summary_value(df, "NetLiquidation") == 0.0


# ===========================================================================
# Accounts.get_summary_async — suggested test #3
# Integration test with a mocked ib_async.IB instance
# ===========================================================================

@pytest.mark.asyncio
async def test_get_summary_async_maps_fields_correctly():
    """
    Validates that Accounts.get_summary_async() correctly awaits
    accountSummaryAsync, maps tag/value/currency fields to the DataFrame
    schema, and returns one row per AccountValue object.
    """
    from ibkr_eda.portfolio.accounts import Accounts

    # Build minimal AccountValue-like stubs
    def make_av(tag, value, currency):
        av = MagicMock()
        av.tag = tag
        av.value = value
        av.currency = currency
        return av

    fake_account_values = [
        make_av("NetLiquidation", "100000.0", "USD"),
        make_av("TotalCashValue", "25000.0", "USD"),
    ]

    mock_ib = MagicMock()
    mock_ib.accountSummaryAsync = AsyncMock(return_value=fake_account_values)

    mock_client = MagicMock()
    mock_client.account_id = "DU123456"
    mock_client.ib = mock_ib

    accounts = Accounts(mock_client)
    result = await accounts.get_summary_async()

    # Schema check
    assert list(result.columns) == ["metric", "amount", "currency"]
    assert len(result) == 2

    # Values check
    assert result.loc[result["metric"] == "NetLiquidation", "amount"].iloc[0] == "100000.0"
    assert result.loc[result["metric"] == "TotalCashValue", "amount"].iloc[0] == "25000.0"

    # accountSummaryAsync was called with the correct account id
    mock_ib.accountSummaryAsync.assert_awaited_once_with("DU123456")


@pytest.mark.asyncio
async def test_get_summary_async_returns_empty_dataframe_when_no_data():
    """
    Validates that get_summary_async() returns an empty DataFrame (not raises)
    when accountSummaryAsync returns an empty list, matching the sync method's
    behaviour for disconnected/paper accounts.
    """
    from ibkr_eda.portfolio.accounts import Accounts

    mock_ib = MagicMock()
    mock_ib.accountSummaryAsync = AsyncMock(return_value=[])

    mock_client = MagicMock()
    mock_client.account_id = "DU123456"
    mock_client.ib = mock_ib

    accounts = Accounts(mock_client)
    result = await accounts.get_summary_async()

    assert isinstance(result, pd.DataFrame)
    assert result.empty
    # Schema must be intact so callers can do summary["metric"] without KeyError
    assert list(result.columns) == ["metric", "amount", "currency"]
