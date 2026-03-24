"""Fallback options data provider using free public sources (no TWS needed)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from datetime import date, datetime, timezone

import numpy as np

from ibkr_eda.exceptions import IBKROptionsError
from ibkr_eda.options.provider import OptionQuote, VolSurfaceData
from ibkr_eda.options.utils import expiry_to_ib, filter_strikes, mid_price

logger = logging.getLogger(__name__)

_CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"

# CBOE delayed-quotes API uses an underscore prefix for index symbols.
_CBOE_INDEX_SYMBOLS = {"VIX", "SPX", "NDX", "RUT", "DJX", "OEX", "XSP", "MRUT", "MXSP", "MXEA", "MXEF"}
_TRADIER_URL = "https://sandbox.tradier.com/v1/markets/options/chains"
_TRADIER_EXP_URL = "https://sandbox.tradier.com/v1/markets/options/expirations"


# Accepted values for the ``source`` parameter.
_VALID_SOURCES = {"yfinance", "cboe", "tradier"}


class FallbackOptionsProvider:
    """Options data from CBOE delayed JSON, yfinance, or Tradier sandbox.

    Data sources are tried in order: CBOE → yfinance → Tradier (unless
    *source* is specified, in which case only that backend is used).
    Results are cached with a configurable TTL.

    Parameters
    ----------
    tradier_token:
        Tradier sandbox/live bearer token.  Required when
        ``source='tradier'``.
    cache_ttl:
        Cache time-to-live in seconds (default 300).
    source:
        Pin a specific data backend: ``'yfinance'``, ``'cboe'``, or
        ``'tradier'``.  ``None`` (default) tries all three in order.
    """

    def __init__(
        self,
        tradier_token: str | None = None,
        cache_ttl: int = 300,
        source: str | None = None,
    ):
        if source is not None and source not in _VALID_SOURCES:
            raise ValueError(
                f"Invalid source {source!r}. Choose from: {sorted(_VALID_SOURCES)}"
            )
        if source == "tradier" and not tradier_token:
            raise IBKROptionsError(
                "source='tradier' requires a tradier_token. "
                "Register free at https://developer.tradier.com/user/sign_up "
                "to get a sandbox token."
            )
        self._tradier_token = tradier_token
        self._cache_ttl = cache_ttl
        self._source = source
        self._cache: dict[str, tuple[float, object]] = {}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get_cached(self, key: str) -> object | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self._cache_ttl:
            del self._cache[key]
            return None
        return value

    def _set_cached(self, key: str, value: object) -> None:
        self._cache[key] = (time.time(), value)

    # ------------------------------------------------------------------
    # CBOE source
    # ------------------------------------------------------------------

    @staticmethod
    def _cboe_symbol(symbol: str) -> str:
        """Map a ticker to the CBOE delayed-quotes symbol (prefix ``_`` for indices)."""
        sym = symbol.upper()
        # Also accept caret-prefixed index tickers (e.g. ^VIX)
        bare = sym.lstrip("^")
        if bare in _CBOE_INDEX_SYMBOLS:
            return f"_{bare}"
        return sym

    def _fetch_cboe_json(self, symbol: str) -> dict:
        """Download CBOE delayed quotes JSON for *symbol*."""
        url = _CBOE_URL.format(symbol=self._cboe_symbol(symbol))
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ibkr-eda)",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            logger.debug("CBOE fetch failed for %s: %s", symbol, exc)
            raise

    def _cboe_to_quotes(
        self, data: dict, symbol: str, expiry: str | None = None,
    ) -> list[OptionQuote]:
        """Parse CBOE JSON into OptionQuote list."""
        quotes: list[OptionQuote] = []
        und_price = None
        current_price = data.get("data", {}).get("current_price")
        if current_price:
            und_price = float(current_price)

        options = data.get("data", {}).get("options", [])
        for opt in options:
            option_str = opt.get("option", "")
            # CBOE option symbol format varies; extract expiry from the option string
            opt_expiry = opt.get("expiration", "")
            if opt_expiry:
                # Normalize to YYYYMMDD
                opt_expiry = opt_expiry.replace("-", "")

            if expiry and opt_expiry != expiry_to_ib(expiry):
                continue

            right = "C" if opt.get("option_type", "").upper().startswith("C") else "P"
            strike = float(opt.get("strike", 0))
            bid = opt.get("bid")
            ask = opt.get("ask")
            bid = float(bid) if bid is not None else None
            ask = float(ask) if ask is not None else None

            quotes.append(OptionQuote(
                symbol=symbol.upper(),
                expiry=opt_expiry,
                strike=strike,
                right=right,
                last=float(opt["last_sale_price"]) if opt.get("last_sale_price") else None,
                bid=bid,
                ask=ask,
                mid=mid_price(bid, ask),
                volume=int(opt["volume"]) if opt.get("volume") else None,
                open_interest=int(opt["open_interest"]) if opt.get("open_interest") else None,
                implied_vol=float(opt["iv"]) if opt.get("iv") else None,
                delta=float(opt["delta"]) if opt.get("delta") else None,
                gamma=float(opt["gamma"]) if opt.get("gamma") else None,
                theta=float(opt["theta"]) if opt.get("theta") else None,
                vega=float(opt["vega"]) if opt.get("vega") else None,
                rho=float(opt["rho"]) if opt.get("rho") else None,
                underlying_price=und_price,
                timestamp=datetime.now(timezone.utc),
            ))
        return quotes

    # ------------------------------------------------------------------
    # yfinance source
    # ------------------------------------------------------------------

    @staticmethod
    def _yfinance_symbol(symbol: str) -> str:
        """Map a ticker to yfinance format (``^`` prefix for indices)."""
        sym = symbol.upper().lstrip("^")
        if sym in _CBOE_INDEX_SYMBOLS:
            return f"^{sym}"
        return sym

    @staticmethod
    def _fetch_yfinance_expirations(symbol: str) -> list[str]:
        """Return expiry dates from yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            raise IBKROptionsError(
                "yfinance is not installed. Run: pip install yfinance"
            )
        ticker = yf.Ticker(FallbackOptionsProvider._yfinance_symbol(symbol))
        dates = ticker.options  # tuple of "YYYY-MM-DD" strings
        return [d.replace("-", "") for d in dates]

    @staticmethod
    def _fetch_yfinance_chain(symbol: str, expiry: str) -> list[OptionQuote]:
        """Fetch option chain from yfinance."""
        try:
            import yfinance as yf
        except ImportError:
            raise IBKROptionsError(
                "yfinance is not installed. Run: pip install yfinance"
            )
        ticker = yf.Ticker(FallbackOptionsProvider._yfinance_symbol(symbol))
        # yfinance expects "YYYY-MM-DD"
        exp_date = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"
        try:
            chain = ticker.option_chain(exp_date)
        except Exception as exc:
            logger.debug("yfinance chain failed for %s %s: %s", symbol, exp_date, exc)
            raise

        und_price = None
        info = ticker.fast_info
        if hasattr(info, "last_price") and info.last_price:
            und_price = float(info.last_price)

        quotes: list[OptionQuote] = []
        exp_ib = expiry_to_ib(expiry)
        now = datetime.now(timezone.utc)

        for right, df in [("C", chain.calls), ("P", chain.puts)]:
            for _, row in df.iterrows():
                bid = row.get("bid")
                ask = row.get("ask")
                bid = float(bid) if bid is not None else None
                ask = float(ask) if ask is not None else None
                quotes.append(OptionQuote(
                    symbol=symbol.upper(),
                    expiry=exp_ib,
                    strike=float(row["strike"]),
                    right=right,
                    last=float(row["lastPrice"]) if row.get("lastPrice") else None,
                    bid=bid,
                    ask=ask,
                    mid=mid_price(bid, ask),
                    volume=int(row["volume"]) if row.get("volume") and row["volume"] == row["volume"] else None,
                    open_interest=int(row["openInterest"]) if row.get("openInterest") and row["openInterest"] == row["openInterest"] else None,
                    implied_vol=float(row["impliedVolatility"]) if row.get("impliedVolatility") else None,
                    delta=None,
                    gamma=None,
                    theta=None,
                    vega=None,
                    rho=None,
                    underlying_price=und_price,
                    timestamp=now,
                ))
        return quotes

    # ------------------------------------------------------------------
    # Tradier source
    # ------------------------------------------------------------------

    def _fetch_tradier_expirations(self, symbol: str) -> list[str]:
        """Fetch expiry dates from Tradier sandbox."""
        if not self._tradier_token:
            raise IBKROptionsError("Tradier token not configured")
        url = f"{_TRADIER_EXP_URL}?symbol={symbol.upper()}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._tradier_token}",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        dates = data.get("expirations", {}).get("date", [])
        return [d.replace("-", "") for d in dates]

    def _fetch_tradier_chain(self, symbol: str, expiry: str) -> list[OptionQuote]:
        """Fetch option chain from Tradier sandbox."""
        if not self._tradier_token:
            raise IBKROptionsError("Tradier token not configured")
        exp_date = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"
        url = f"{_TRADIER_URL}?symbol={symbol.upper()}&expiration={exp_date}&greeks=true"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self._tradier_token}",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        options = data.get("options", {}).get("option", [])
        if not options:
            return []

        exp_ib = expiry_to_ib(expiry)
        now = datetime.now(timezone.utc)
        quotes: list[OptionQuote] = []
        for opt in options:
            greeks = opt.get("greeks", {}) or {}
            bid = opt.get("bid")
            ask = opt.get("ask")
            bid = float(bid) if bid is not None else None
            ask = float(ask) if ask is not None else None
            quotes.append(OptionQuote(
                symbol=symbol.upper(),
                expiry=exp_ib,
                strike=float(opt["strike"]),
                right="C" if opt.get("option_type") == "call" else "P",
                last=float(opt["last"]) if opt.get("last") else None,
                bid=bid,
                ask=ask,
                mid=mid_price(bid, ask),
                volume=int(opt["volume"]) if opt.get("volume") else None,
                open_interest=int(opt["open_interest"]) if opt.get("open_interest") else None,
                implied_vol=float(greeks["mid_iv"]) if greeks.get("mid_iv") else None,
                delta=float(greeks["delta"]) if greeks.get("delta") else None,
                gamma=float(greeks["gamma"]) if greeks.get("gamma") else None,
                theta=float(greeks["theta"]) if greeks.get("theta") else None,
                vega=float(greeks["vega"]) if greeks.get("vega") else None,
                rho=float(greeks["rho"]) if greeks.get("rho") else None,
                underlying_price=None,
                timestamp=now,
            ))
        return quotes

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_future_expiries(expiries: list[str]) -> list[str]:
        """Remove expirations that have already passed (including today)."""
        today_s = date.today().strftime("%Y%m%d")
        return [e for e in expiries if e > today_s]

    def get_expirations(self, symbol: str, exchange: str = "SMART") -> list[str]:
        cache_key = f"exp:{symbol}:{self._source}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        result: list[str] = []
        errors: list[str] = []

        if self._source == "cboe" or self._source is None:
            try:
                data = self._fetch_cboe_json(symbol)
                options = data.get("data", {}).get("options", [])
                expiries: set[str] = set()
                for opt in options:
                    exp = opt.get("expiration", "")
                    if exp:
                        expiries.add(exp.replace("-", ""))
                result = sorted(expiries)
                if result:
                    result = self._filter_future_expiries(result)
                    self._set_cached(cache_key, result)
                    return result
            except Exception as exc:
                errors.append(f"CBOE: {exc}")
                if self._source == "cboe":
                    raise IBKROptionsError(
                        f"CBOE source failed for {symbol} expirations: {exc}"
                    ) from exc

        if self._source == "yfinance" or self._source is None:
            try:
                result = self._fetch_yfinance_expirations(symbol)
                if result:
                    result = self._filter_future_expiries(result)
                    self._set_cached(cache_key, result)
                    return result
            except Exception as exc:
                errors.append(f"yfinance: {exc}")
                if self._source == "yfinance":
                    raise IBKROptionsError(
                        f"yfinance source failed for {symbol} expirations: {exc}"
                    ) from exc

        if self._source == "tradier" or (self._source is None and self._tradier_token):
            try:
                result = self._fetch_tradier_expirations(symbol)
                if result:
                    result = self._filter_future_expiries(result)
                    self._set_cached(cache_key, result)
                    return result
            except Exception as exc:
                errors.append(f"Tradier: {exc}")
                if self._source == "tradier":
                    raise IBKROptionsError(
                        f"Tradier source failed for {symbol} expirations: {exc}"
                    ) from exc

        raise IBKROptionsError(
            f"All fallback sources failed for {symbol} expirations: "
            + "; ".join(errors)
        )

    async def get_expirations_async(
        self, symbol: str, exchange: str = "SMART",
    ) -> list[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.get_expirations, symbol, exchange,
        )

    def get_chain(
        self,
        symbol: str,
        expiry: str,
        exchange: str = "SMART",
        strike_range: tuple[float, float] | None = None,
        max_strikes: int = 40,
    ) -> list[OptionQuote]:
        exp_ib = expiry_to_ib(expiry)
        cache_key = f"chain:{symbol}:{exp_ib}:{self._source}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        errors: list[str] = []

        if self._source == "cboe" or self._source is None:
            try:
                data = self._fetch_cboe_json(symbol)
                quotes = self._cboe_to_quotes(data, symbol, exp_ib)
                if quotes:
                    self._set_cached(cache_key, quotes)
                    return self._apply_strike_filter(quotes, strike_range, max_strikes)
            except Exception as exc:
                errors.append(f"CBOE: {exc}")
                if self._source == "cboe":
                    raise IBKROptionsError(
                        f"CBOE source failed for {symbol} {expiry} chain: {exc}"
                    ) from exc

        if self._source == "yfinance" or self._source is None:
            try:
                quotes = self._fetch_yfinance_chain(symbol, exp_ib)
                if quotes:
                    self._set_cached(cache_key, quotes)
                    return self._apply_strike_filter(quotes, strike_range, max_strikes)
            except Exception as exc:
                errors.append(f"yfinance: {exc}")
                if self._source == "yfinance":
                    raise IBKROptionsError(
                        f"yfinance source failed for {symbol} {expiry} chain: {exc}"
                    ) from exc

        if self._source == "tradier" or (self._source is None and self._tradier_token):
            try:
                quotes = self._fetch_tradier_chain(symbol, exp_ib)
                if quotes:
                    self._set_cached(cache_key, quotes)
                    return self._apply_strike_filter(quotes, strike_range, max_strikes)
            except Exception as exc:
                errors.append(f"Tradier: {exc}")
                if self._source == "tradier":
                    raise IBKROptionsError(
                        f"Tradier source failed for {symbol} {expiry} chain: {exc}"
                    ) from exc

        raise IBKROptionsError(
            f"All fallback sources failed for {symbol} {expiry} chain: "
            + "; ".join(errors)
        )

    async def get_chain_async(
        self,
        symbol: str,
        expiry: str,
        exchange: str = "SMART",
        strike_range: tuple[float, float] | None = None,
        max_strikes: int = 40,
    ) -> list[OptionQuote]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.get_chain, symbol, expiry, exchange, strike_range, max_strikes,
        )

    def get_greeks(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        chain = self.get_chain(symbol, expiry, exchange)
        right = right.upper()
        for q in chain:
            if q.strike == strike and q.right == right:
                return q
        raise IBKROptionsError(
            f"No quote found for {symbol} {expiry} {strike} {right}"
        )

    async def get_greeks_async(
        self,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> OptionQuote:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.get_greeks, symbol, expiry, strike, right, exchange,
        )

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
            chain = self.get_chain(symbol, exp, exchange, max_strikes=num_strikes)
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
            symbol=symbol.upper(),
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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.get_iv_surface, symbol, exchange, num_expiries, num_strikes,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_strike_filter(
        quotes: list[OptionQuote],
        strike_range: tuple[float, float] | None,
        max_strikes: int,
    ) -> list[OptionQuote]:
        """Filter quotes by strike range or around ATM."""
        if strike_range:
            lo, hi = strike_range
            return [q for q in quotes if lo <= q.strike <= hi]
        # Filter around ATM
        und_price = next(
            (q.underlying_price for q in quotes if q.underlying_price), None,
        )
        if und_price and und_price > 0:
            all_strikes = sorted({q.strike for q in quotes})
            keep = set(filter_strikes(
                all_strikes, und_price,
                num_otm=max_strikes // 2, num_itm=max_strikes // 2,
            ))
            return [q for q in quotes if q.strike in keep]
        return quotes
