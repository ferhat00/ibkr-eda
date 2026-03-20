"""IBKR TWS options data provider via ib_async."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import numpy as np

from ibkr_eda.client import IBKRClient
from ibkr_eda.exceptions import IBKROptionsError
from ibkr_eda.options.provider import OptionQuote, VolSurfaceData
from ibkr_eda.options.utils import (
    build_option_contract,
    build_underlying_contract,
    expiry_to_ib,
    filter_strikes,
    mid_price,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 45  # max concurrent reqMktData subscriptions (TWS limit ~50)
_DATA_WAIT = 2    # seconds to wait for snapshot data


class IBKROptionsProvider:
    """Options data from a live TWS / IB Gateway connection."""

    def __init__(self, client: IBKRClient, max_concurrent: int = _BATCH_SIZE):
        self._client = client
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    # ------------------------------------------------------------------
    # Expirations
    # ------------------------------------------------------------------

    def _get_opt_params(self, symbol: str) -> list:
        """Fetch option definition params for *symbol*."""
        contract = build_underlying_contract(symbol)
        self._client.ib.qualifyContracts(contract)
        params = self._client.ib.reqSecDefOptParams(
            underlyingSymbol=contract.symbol,
            futFopExchange="",
            underlyingSecType=contract.secType,
            underlyingConId=contract.conId,
        )
        if not params:
            raise IBKROptionsError(
                f"No option parameters returned for {symbol}"
            )
        return params

    async def _get_opt_params_async(self, symbol: str) -> list:
        """Async variant of _get_opt_params."""
        contract = build_underlying_contract(symbol)
        await asyncio.ensure_future(
            self._client.ib.qualifyContractsAsync(contract)
        )
        params = await asyncio.ensure_future(
            self._client.ib.reqSecDefOptParamsAsync(
                underlyingSymbol=contract.symbol,
                futFopExchange="",
                underlyingSecType=contract.secType,
                underlyingConId=contract.conId,
            )
        )
        if not params:
            raise IBKROptionsError(
                f"No option parameters returned for {symbol}"
            )
        return params

    def get_expirations(self, symbol: str, exchange: str = "SMART") -> list[str]:
        params = self._get_opt_params(symbol)
        expiries: set[str] = set()
        for p in params:
            expiries.update(p.expirations)
        return sorted(expiries)

    async def get_expirations_async(
        self, symbol: str, exchange: str = "SMART",
    ) -> list[str]:
        params = await self._get_opt_params_async(symbol)
        expiries: set[str] = set()
        for p in params:
            expiries.update(p.expirations)
        return sorted(expiries)

    # ------------------------------------------------------------------
    # Chain
    # ------------------------------------------------------------------

    def _get_strikes_for_expiry(self, symbol: str, expiry: str) -> list[float]:
        """Return available strikes for a given expiry."""
        params = self._get_opt_params(symbol)
        exp = expiry_to_ib(expiry)
        strikes: set[float] = set()
        for p in params:
            if exp in p.expirations:
                strikes.update(p.strikes)
        return sorted(strikes)

    async def _get_strikes_for_expiry_async(
        self, symbol: str, expiry: str,
    ) -> list[float]:
        params = await self._get_opt_params_async(symbol)
        exp = expiry_to_ib(expiry)
        strikes: set[float] = set()
        for p in params:
            if exp in p.expirations:
                strikes.update(p.strikes)
        return sorted(strikes)

    def get_chain(
        self,
        symbol: str,
        expiry: str,
        exchange: str = "SMART",
        strike_range: tuple[float, float] | None = None,
        max_strikes: int = 20,
    ) -> list[OptionQuote]:
        """Fetch full option chain for *symbol* + *expiry*.

        Parameters
        ----------
        strike_range : tuple, optional
            ``(low, high)`` to filter strikes.
        max_strikes : int
            Max strikes around ATM when *strike_range* is ``None``.
        """
        strikes = self._get_strikes_for_expiry(symbol, expiry)
        if not strikes:
            raise IBKROptionsError(f"No strikes found for {symbol} {expiry}")

        if strike_range:
            strikes = [s for s in strikes if strike_range[0] <= s <= strike_range[1]]
        else:
            # Need underlying price for ATM filtering
            und = build_underlying_contract(symbol)
            self._client.ib.qualifyContracts(und)
            ticker = self._client.ib.reqMktData(und, snapshot=True)
            self._client.ib.sleep(1)
            self._client.ib.cancelMktData(und)
            und_price = ticker.marketPrice()
            if und_price and und_price > 0:
                strikes = filter_strikes(
                    strikes, und_price,
                    num_otm=max_strikes // 2, num_itm=max_strikes // 2,
                )

        # Build contracts for both calls and puts
        contracts = []
        for strike in strikes:
            for right in ("C", "P"):
                contracts.append(
                    build_option_contract(symbol, expiry, strike, right, exchange)
                )

        # Qualify in batch
        qualified = self._client.ib.qualifyContracts(*contracts)
        valid = [c for c in qualified if c.conId > 0]
        if not valid:
            raise IBKROptionsError(
                f"No option contracts qualified for {symbol} {expiry}"
            )
        logger.info("Qualified %d option contracts for %s %s", len(valid), symbol, expiry)

        # Fetch market data in batches
        quotes: list[OptionQuote] = []
        for i in range(0, len(valid), self._max_concurrent):
            batch = valid[i : i + self._max_concurrent]
            tickers = []
            for c in batch:
                t = self._client.ib.reqMktData(c, genericTickList="106", snapshot=True)
                tickers.append(t)
            self._client.ib.sleep(_DATA_WAIT)
            for t in tickers:
                self._client.ib.cancelMktData(t.contract)
                quotes.append(self._ticker_to_quote(t, symbol, expiry))

        return quotes

    async def get_chain_async(
        self,
        symbol: str,
        expiry: str,
        exchange: str = "SMART",
        strike_range: tuple[float, float] | None = None,
        max_strikes: int = 20,
    ) -> list[OptionQuote]:
        strikes = await self._get_strikes_for_expiry_async(symbol, expiry)
        if not strikes:
            raise IBKROptionsError(f"No strikes found for {symbol} {expiry}")

        if strike_range:
            strikes = [s for s in strikes if strike_range[0] <= s <= strike_range[1]]
        else:
            und = build_underlying_contract(symbol)
            await asyncio.ensure_future(
                self._client.ib.qualifyContractsAsync(und)
            )
            ticker = self._client.ib.reqMktData(und, snapshot=True)
            await asyncio.sleep(1)
            self._client.ib.cancelMktData(und)
            und_price = ticker.marketPrice()
            if und_price and und_price > 0:
                strikes = filter_strikes(
                    strikes, und_price,
                    num_otm=max_strikes // 2, num_itm=max_strikes // 2,
                )

        contracts = []
        for strike in strikes:
            for right in ("C", "P"):
                contracts.append(
                    build_option_contract(symbol, expiry, strike, right, exchange)
                )

        qualified = await asyncio.ensure_future(
            self._client.ib.qualifyContractsAsync(*contracts)
        )
        valid = [c for c in qualified if c.conId > 0]
        if not valid:
            raise IBKROptionsError(
                f"No option contracts qualified for {symbol} {expiry}"
            )
        logger.info("Qualified %d option contracts for %s %s", len(valid), symbol, expiry)

        # Fetch with semaphore-guarded concurrency
        async def _fetch_one(contract):
            async with self._semaphore:
                t = self._client.ib.reqMktData(
                    contract, genericTickList="106", snapshot=True,
                )
                await asyncio.sleep(_DATA_WAIT)
                self._client.ib.cancelMktData(contract)
                return self._ticker_to_quote(t, symbol, expiry)

        quotes = await asyncio.gather(*[_fetch_one(c) for c in valid])
        return list(quotes)

    # ------------------------------------------------------------------
    # Greeks (single contract)
    # ------------------------------------------------------------------

    def get_greeks(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        contract = build_option_contract(symbol, expiry, strike, right, exchange)
        self._client.ib.qualifyContracts(contract)
        if contract.conId == 0:
            raise IBKROptionsError(
                f"Cannot qualify {symbol} {expiry} {strike} {right}"
            )
        ticker = self._client.ib.reqMktData(
            contract, genericTickList="106", snapshot=True,
        )
        self._client.ib.sleep(_DATA_WAIT)
        self._client.ib.cancelMktData(contract)
        return self._ticker_to_quote(ticker, symbol, expiry)

    async def get_greeks_async(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        contract = build_option_contract(symbol, expiry, strike, right, exchange)
        await asyncio.ensure_future(
            self._client.ib.qualifyContractsAsync(contract)
        )
        if contract.conId == 0:
            raise IBKROptionsError(
                f"Cannot qualify {symbol} {expiry} {strike} {right}"
            )
        ticker = self._client.ib.reqMktData(
            contract, genericTickList="106", snapshot=True,
        )
        await asyncio.sleep(_DATA_WAIT)
        self._client.ib.cancelMktData(contract)
        return self._ticker_to_quote(ticker, symbol, expiry)

    # ------------------------------------------------------------------
    # IV Surface
    # ------------------------------------------------------------------

    def get_iv_surface(
        self,
        symbol: str,
        exchange: str = "SMART",
        num_expiries: int = 6,
        num_strikes: int = 20,
    ) -> VolSurfaceData:
        all_expiries = self.get_expirations(symbol, exchange)
        expiries = all_expiries[:num_expiries]

        all_strikes: set[float] = set()
        chains: dict[str, list[OptionQuote]] = {}
        for exp in expiries:
            chain = self.get_chain(
                symbol, exp, exchange, max_strikes=num_strikes,
            )
            chains[exp] = chain
            all_strikes.update(q.strike for q in chain)

        strikes_arr = np.array(sorted(all_strikes))
        strike_idx = {s: i for i, s in enumerate(strikes_arr)}
        call_iv = np.full((len(expiries), len(strikes_arr)), np.nan)
        put_iv = np.full((len(expiries), len(strikes_arr)), np.nan)
        und_price = 0.0

        for ei, exp in enumerate(expiries):
            for q in chains[exp]:
                si = strike_idx.get(q.strike)
                if si is None:
                    continue
                if q.implied_vol is not None:
                    if q.right == "C":
                        call_iv[ei, si] = q.implied_vol
                    else:
                        put_iv[ei, si] = q.implied_vol
                if q.underlying_price and q.underlying_price > 0:
                    und_price = q.underlying_price

        return VolSurfaceData(
            symbol=symbol,
            underlying_price=und_price,
            strikes=strikes_arr,
            expiries=expiries,
            call_iv=call_iv,
            put_iv=put_iv,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_iv_surface_async(
        self,
        symbol: str,
        exchange: str = "SMART",
        num_expiries: int = 6,
        num_strikes: int = 20,
    ) -> VolSurfaceData:
        all_expiries = await self.get_expirations_async(symbol, exchange)
        expiries = all_expiries[:num_expiries]

        chains: dict[str, list[OptionQuote]] = {}
        for exp in expiries:
            chain = await self.get_chain_async(
                symbol, exp, exchange, max_strikes=num_strikes,
            )
            chains[exp] = chain

        all_strikes: set[float] = set()
        for chain in chains.values():
            all_strikes.update(q.strike for q in chain)

        strikes_arr = np.array(sorted(all_strikes))
        strike_idx = {s: i for i, s in enumerate(strikes_arr)}
        call_iv = np.full((len(expiries), len(strikes_arr)), np.nan)
        put_iv = np.full((len(expiries), len(strikes_arr)), np.nan)
        und_price = 0.0

        for ei, exp in enumerate(expiries):
            for q in chains[exp]:
                si = strike_idx.get(q.strike)
                if si is None:
                    continue
                if q.implied_vol is not None:
                    if q.right == "C":
                        call_iv[ei, si] = q.implied_vol
                    else:
                        put_iv[ei, si] = q.implied_vol
                if q.underlying_price and q.underlying_price > 0:
                    und_price = q.underlying_price

        return VolSurfaceData(
            symbol=symbol,
            underlying_price=und_price,
            strikes=strikes_arr,
            expiries=expiries,
            call_iv=call_iv,
            put_iv=put_iv,
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _ticker_to_quote(ticker, symbol: str, expiry: str) -> OptionQuote:
        """Convert an ib_async Ticker with Greeks into an OptionQuote."""
        c = ticker.contract
        mg = ticker.modelGreeks or ticker.lastGreeks
        return OptionQuote(
            symbol=symbol,
            expiry=expiry_to_ib(expiry),
            strike=c.strike,
            right=c.right,
            last=ticker.last if ticker.last == ticker.last else None,
            bid=ticker.bid if ticker.bid == ticker.bid else None,
            ask=ticker.ask if ticker.ask == ticker.ask else None,
            mid=mid_price(ticker.bid, ticker.ask),
            volume=int(ticker.volume) if ticker.volume == ticker.volume else None,
            open_interest=None,
            implied_vol=mg.impliedVol if mg else None,
            delta=mg.delta if mg else None,
            gamma=mg.gamma if mg else None,
            theta=mg.theta if mg else None,
            vega=mg.vega if mg else None,
            rho=None,
            underlying_price=mg.undPrice if mg else None,
            timestamp=datetime.now(timezone.utc),
        )
