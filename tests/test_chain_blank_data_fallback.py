"""Test that OptionChains falls back when IBKR returns all-blank quotes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ibkr_eda.options.chain import OptionChains
from ibkr_eda.options.provider import OptionQuote


def _blank_quote(strike: float = 20.0, right: str = "C") -> OptionQuote:
    """Quote with no pricing at all (typical far-dated IBKR snapshot)."""
    return OptionQuote(
        symbol="VIX", expiry="20260617", strike=strike, right=right,
    )


def _priced_quote(strike: float = 20.0, right: str = "C") -> OptionQuote:
    """Quote with valid pricing (from CBOE fallback)."""
    return OptionQuote(
        symbol="VIX", expiry="20260617", strike=strike, right=right,
        bid=1.50, ask=2.00, mid=1.75, last=1.80,
    )


@pytest.fixture
def mock_client():
    """Mocked IBKRClient with connected IB."""
    client = MagicMock()
    client.ib.isConnected.return_value = True
    return client


@pytest.fixture
def ibkr_provider():
    """Mocked IBKROptionsProvider that returns all-blank quotes."""
    from ibkr_eda.options.ibkr_provider import IBKROptionsProvider

    prov = MagicMock(spec=IBKROptionsProvider)
    prov.get_chain.return_value = [_blank_quote(15), _blank_quote(20), _blank_quote(25)]
    prov.get_chain_async = AsyncMock(
        return_value=[_blank_quote(15), _blank_quote(20), _blank_quote(25)],
    )
    return prov


@pytest.fixture
def ibkr_provider_with_prices():
    """Mocked IBKROptionsProvider that returns quotes with pricing."""
    from ibkr_eda.options.ibkr_provider import IBKROptionsProvider

    prov = MagicMock(spec=IBKROptionsProvider)
    prov.get_chain.return_value = [_priced_quote(15), _priced_quote(20)]
    prov.get_chain_async = AsyncMock(
        return_value=[_priced_quote(15), _priced_quote(20)],
    )
    return prov


@pytest.mark.asyncio
async def test_async_fallback_on_blank_ibkr(ibkr_provider, mock_client):
    """get_raw_async should fall back when IBKR returns all-blank quotes."""
    chains = OptionChains(client=mock_client, provider=ibkr_provider)

    fb_quotes = [_priced_quote(15), _priced_quote(20), _priced_quote(25)]
    with patch(
        "ibkr_eda.options.fallback_provider.FallbackOptionsProvider"
    ) as MockFB:
        mock_fb_instance = MagicMock()
        mock_fb_instance.get_chain_async = AsyncMock(return_value=fb_quotes)
        MockFB.return_value = mock_fb_instance

        result = await chains.get_raw_async("VIX", "20260617")

    assert len(result) == 3
    assert all(q.bid is not None and q.bid > 0 for q in result)
    MockFB.assert_called_once()


@pytest.mark.asyncio
async def test_async_no_fallback_when_ibkr_has_prices(ibkr_provider_with_prices, mock_client):
    """get_raw_async should NOT fall back when IBKR returns priced quotes."""
    chains = OptionChains(client=mock_client, provider=ibkr_provider_with_prices)

    with patch(
        "ibkr_eda.options.fallback_provider.FallbackOptionsProvider"
    ) as MockFB:
        result = await chains.get_raw_async("VIX", "20260617")

    assert len(result) == 2
    assert all(q.bid is not None for q in result)
    MockFB.assert_not_called()


def test_sync_fallback_on_blank_ibkr(ibkr_provider, mock_client):
    """get_raw should fall back when IBKR returns all-blank quotes."""
    chains = OptionChains(client=mock_client, provider=ibkr_provider)

    fb_quotes = [_priced_quote(15), _priced_quote(20), _priced_quote(25)]
    with patch(
        "ibkr_eda.options.fallback_provider.FallbackOptionsProvider"
    ) as MockFB:
        mock_fb_instance = MagicMock()
        mock_fb_instance.get_chain.return_value = fb_quotes
        MockFB.return_value = mock_fb_instance

        result = chains.get_raw("VIX", "20260617")

    assert len(result) == 3
    assert all(q.bid is not None and q.bid > 0 for q in result)
    MockFB.assert_called_once()


def test_sync_no_fallback_when_ibkr_has_prices(ibkr_provider_with_prices, mock_client):
    """get_raw should NOT fall back when IBKR returns priced quotes."""
    chains = OptionChains(client=mock_client, provider=ibkr_provider_with_prices)

    with patch(
        "ibkr_eda.options.fallback_provider.FallbackOptionsProvider"
    ) as MockFB:
        result = chains.get_raw("VIX", "20260617")

    assert len(result) == 2
    MockFB.assert_not_called()
