"""Fallback options data provider using free public sources (no TWS needed)."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import time
import urllib.request
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from ibkr_eda.exceptions import IBKROptionsError
from ibkr_eda.options.provider import OptionQuote, VolSurfaceData
from ibkr_eda.options.utils import expiry_to_ib, filter_strikes, mid_price

# OCC-style option symbol: underlying (letters/^) + YYMMDD + C/P + 8-digit strike*1000
_OCC_RE = re.compile(r'^([A-Z^]+)(\d{6})([CP])(\d{8})$')


def _parse_occ_symbol(option_str: str) -> tuple[str, str, str, float] | None:
    """Parse an OCC option symbol into (underlying, YYYYMMDD, right, strike).

    CBOE encodes all contract details in the symbol, e.g. ``VIX260617C00010000``
    means VIX, expiry June 17 2026, call, strike $10.00.
    """
    m = _OCC_RE.match(option_str.replace(" ", "").upper())
    if not m:
        return None
    underlying, yymmdd, right, strike_str = m.groups()
    yy = int(yymmdd[:2])
    century = "19" if yy >= 50 else "20"
    yyyymmdd = f"{century}{yymmdd}"
    strike = int(strike_str) / 1000.0
    return underlying, yyyymmdd, right, strike

logger = logging.getLogger(__name__)

_CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"

# CBOE delayed-quotes API uses an underscore prefix for index symbols.
_CBOE_INDEX_SYMBOLS = {"VIX", "SPX", "NDX", "RUT", "DJX", "OEX", "XSP", "MRUT", "MXSP", "MXEA", "MXEF"}
_TRADIER_URL = "https://sandbox.tradier.com/v1/markets/options/chains"
_TRADIER_EXP_URL = "https://sandbox.tradier.com/v1/markets/options/expirations"

# Barchart uses a "$" prefix for index/futures symbols and a separate base URL.
_BARCHART_BASE = "https://www.barchart.com"
_BARCHART_API_CHAIN = "https://www.barchart.com/proxies/core-api/v1/options/chain"
_BARCHART_API_EXP = "https://www.barchart.com/proxies/core-api/v1/options/expirations"
# Index-like symbols that Barchart prefixes with "$".
_BARCHART_INDEX_SYMBOLS = _CBOE_INDEX_SYMBOLS | {"ES", "NQ", "CL", "GC", "SI"}

# Accepted values for the ``source`` parameter.
_VALID_SOURCES = {"yfinance", "cboe", "tradier", "barchart"}


class FallbackOptionsProvider:
    """Options data from CBOE delayed JSON, yfinance, Tradier sandbox, or Barchart.

    Data sources are tried in order: CBOE → yfinance → Tradier (if token) →
    Barchart (unless *source* is specified, in which case only that backend is
    used).  Results are cached with a configurable TTL.

    Parameters
    ----------
    tradier_token:
        Tradier sandbox/live bearer token.  Required when
        ``source='tradier'``.
    cache_ttl:
        Cache time-to-live in seconds (default 300).
    source:
        Pin a specific data backend: ``'yfinance'``, ``'cboe'``,
        ``'tradier'``, or ``'barchart'``.  ``None`` (default) tries all
        four in order.
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
            logger.warning("CBOE fetch failed for %s: %s", symbol, exc)
            raise

    def _cboe_to_quotes(
        self, data: dict, symbol: str, expiry: str | None = None,
    ) -> list[OptionQuote]:
        """Parse CBOE JSON into OptionQuote list.

        CBOE's delayed-quotes JSON encodes expiry, right, and strike inside
        the OCC option symbol (e.g. ``VIX260617C00010000``).  There are no
        separate ``expiration``, ``strike``, or ``option_type`` fields.

        For VIX options, IBKR uses the **last trading day** (usually Tuesday)
        while CBOE OCC symbols use the **settlement date** (usually Wednesday).
        When no exact expiry match is found, this method fuzzy-matches by
        looking for the closest CBOE expiry within ±2 calendar days.
        """
        quotes: list[OptionQuote] = []
        und_price = None
        current_price = data.get("data", {}).get("current_price")
        if current_price:
            und_price = float(current_price)

        target_expiry = expiry_to_ib(expiry) if expiry else None

        # Pre-scan available CBOE expiries for fuzzy date matching
        options = data.get("data", {}).get("options", [])
        if target_expiry:
            cboe_expiries: set[str] = set()
            for opt in options:
                parsed = _parse_occ_symbol(opt.get("option", ""))
                if parsed is not None:
                    cboe_expiries.add(parsed[1])
            # If exact match not in CBOE, find nearest within ±2 days
            if target_expiry not in cboe_expiries:
                target_date = datetime.strptime(target_expiry, "%Y%m%d").date()
                best = None
                best_delta = 999
                for ce in cboe_expiries:
                    ce_date = datetime.strptime(ce, "%Y%m%d").date()
                    delta = abs((ce_date - target_date).days)
                    if delta <= 2 and delta < best_delta:
                        best = ce
                        best_delta = delta
                if best:
                    logger.info(
                        "CBOE expiry fuzzy match: requested %s → using %s (±%d day)",
                        target_expiry, best, best_delta,
                    )
                    target_expiry = best

        for opt in options:
            option_str = opt.get("option", "")
            parsed = _parse_occ_symbol(option_str)
            if parsed is None:
                continue
            _, opt_expiry, right, strike = parsed

            if target_expiry and opt_expiry != target_expiry:
                continue

            bid = opt.get("bid")
            ask = opt.get("ask")
            bid = float(bid) if bid is not None else None
            ask = float(ask) if ask is not None else None

            last_raw = opt.get("last_trade_price")
            last = float(last_raw) if last_raw is not None and float(last_raw) > 0 else None
            if last is None:
                prev_raw = opt.get("prev_day_close")
                if prev_raw is not None and float(prev_raw) > 0:
                    last = float(prev_raw)
            if last is None:
                # Try additional CBOE fields as price fallbacks
                for fallback_key in ("close", "theo", "settlement_value", "theoretical_value"):
                    fb_raw = opt.get(fallback_key)
                    if fb_raw is not None and float(fb_raw) > 0:
                        last = float(fb_raw)
                        break

            iv_raw = opt.get("iv")
            iv = float(iv_raw) if iv_raw is not None and float(iv_raw) > 0 else None

            quotes.append(OptionQuote(
                symbol=symbol.upper(),
                expiry=opt_expiry,
                strike=strike,
                right=right,
                last=last,
                bid=bid,
                ask=ask,
                mid=mid_price(bid, ask) or last,
                volume=int(opt["volume"]) if opt.get("volume") else None,
                open_interest=int(opt["open_interest"]) if opt.get("open_interest") else None,
                implied_vol=iv,
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
        except Exception:
            # Fuzzy date match: yfinance uses settlement dates which may
            # differ by ±1-2 days from IBKR last-trading-day dates (e.g. VIX).
            available = ticker.options  # tuple of "YYYY-MM-DD" strings
            target_date = datetime.strptime(expiry[:8], "%Y%m%d").date()
            matched = None
            best_delta = 999
            for avail in available:
                avail_date = datetime.strptime(avail, "%Y-%m-%d").date()
                delta = abs((avail_date - target_date).days)
                if delta <= 2 and delta < best_delta:
                    matched = avail
                    best_delta = delta
            if matched is None:
                raise
            logger.info(
                "yfinance expiry fuzzy match: requested %s → using %s (±%d day)",
                exp_date, matched, best_delta,
            )
            exp_date = matched
            chain = ticker.option_chain(exp_date)

        und_price = None
        try:
            info = ticker.fast_info
            for attr in ("last_price", "previous_close", "regularMarketPrice"):
                val = getattr(info, attr, None)
                if val and float(val) > 0:
                    und_price = float(val)
                    break
        except Exception:
            pass

        quotes: list[OptionQuote] = []
        exp_ib = expiry_to_ib(expiry)
        now = datetime.now(timezone.utc)

        for right, df in [("C", chain.calls), ("P", chain.puts)]:
            for _, row in df.iterrows():
                bid_raw = row.get("bid")
                ask_raw = row.get("ask")
                bid = float(bid_raw) if pd.notna(bid_raw) else None
                ask = float(ask_raw) if pd.notna(ask_raw) else None
                last_raw = row.get("lastPrice")
                last = float(last_raw) if pd.notna(last_raw) and float(last_raw) > 0 else None
                iv_raw = row.get("impliedVolatility")
                iv = float(iv_raw) if pd.notna(iv_raw) and float(iv_raw) > 0 else None
                quotes.append(OptionQuote(
                    symbol=symbol.upper(),
                    expiry=exp_ib,
                    strike=float(row["strike"]),
                    right=right,
                    last=last,
                    bid=bid,
                    ask=ask,
                    mid=mid_price(bid, ask) or last,
                    volume=int(row["volume"]) if pd.notna(row.get("volume")) and row["volume"] > 0 else None,
                    open_interest=int(row["openInterest"]) if pd.notna(row.get("openInterest")) and row["openInterest"] > 0 else None,
                    implied_vol=iv,
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
    # Barchart source
    # ------------------------------------------------------------------

    @staticmethod
    def _barchart_symbol(symbol: str) -> str:
        """Map a ticker to Barchart format (``$`` prefix for indices)."""
        sym = symbol.upper().lstrip("^")
        if sym in _BARCHART_INDEX_SYMBOLS:
            return f"${sym}"
        return sym

    @staticmethod
    def _barchart_expiry_param(expiry_yyyymmdd: str, weekly: bool = False) -> str:
        """Convert YYYYMMDD to Barchart expiration query param (YYYY-MM-DD or YYYY-MM-DD-w)."""
        d = f"{expiry_yyyymmdd[:4]}-{expiry_yyyymmdd[4:6]}-{expiry_yyyymmdd[6:8]}"
        return f"{d}-w" if weekly else d

    def _get_barchart_session(self, symbol: str):
        """Return a ``requests.Session`` primed with Barchart cookies + XSRF token.

        We visit the options overview page once to collect the XSRF-TOKEN cookie
        that Barchart's XHR API requires for all subsequent requests.
        """
        try:
            import requests
        except ImportError:
            raise IBKROptionsError("requests is not installed. Run: pip install requests")

        session = requests.Session()
        bc_sym = self._barchart_symbol(symbol)
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        # Prime session cookies (including XSRF-TOKEN)
        page_url = f"{_BARCHART_BASE}/stocks/quotes/{bc_sym}/options"
        try:
            session.get(page_url, timeout=15)
        except Exception as exc:
            logger.debug("Barchart session prime failed: %s", exc)
        xsrf = session.cookies.get("XSRF-TOKEN")
        if xsrf:
            session.headers["X-XSRF-TOKEN"] = xsrf
        session.headers["Referer"] = page_url
        return session

    def _fetch_barchart_expirations(self, symbol: str) -> list[str]:
        """Fetch available expiry dates from Barchart using BeautifulSoup + API."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise IBKROptionsError(
                "beautifulsoup4 is not installed. Run: pip install beautifulsoup4"
            )

        bc_sym = self._barchart_symbol(symbol)
        session = self._get_barchart_session(symbol)

        # --- Strategy 1: JSON API for expirations ---
        try:
            api_resp = session.get(
                _BARCHART_API_EXP,
                params={"symbol": bc_sym, "raw": "1"},
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if api_resp.status_code == 200:
                data = api_resp.json()
                exps = data.get("data", [])
                dates = [
                    e["expirationDate"].replace("-", "")
                    for e in exps
                    if "expirationDate" in e
                ]
                if dates:
                    return sorted(set(dates))
        except Exception as exc:
            logger.debug("Barchart expirations API failed: %s", exc)

        # --- Strategy 2: Parse HTML page for <select>/<option> expiry values ---
        page_url = f"{_BARCHART_BASE}/stocks/quotes/{bc_sym}/options"
        resp = session.get(page_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        dates: list[str] = []
        _exp_re = re.compile(r"^\d{4}-\d{2}-\d{2}(-w)?$")

        for sel in soup.find_all("select"):
            for opt in sel.find_all("option"):
                val = opt.get("value", "").strip()
                if _exp_re.match(val):
                    dates.append(val[:10].replace("-", ""))

        if dates:
            return sorted(set(dates))

        # --- Strategy 3: Embedded __NEXT_DATA__ JSON ---
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script and script.string:
            try:
                nd = json.loads(script.string)
                # Walk the props tree looking for expirationDate keys
                raw = json.dumps(nd)
                found = re.findall(r'"expirationDate"\s*:\s*"(\d{4}-\d{2}-\d{2})"', raw)
                if found:
                    return sorted({d.replace("-", "") for d in found})
            except Exception:
                pass

        raise IBKROptionsError(f"Barchart: could not find expirations for {symbol}")

    def _fetch_barchart_chain(self, symbol: str, expiry: str) -> list[OptionQuote]:
        """Fetch option chain from Barchart using BeautifulSoup + JSON API.

        Tries the Barchart core-api JSON endpoint first (most reliable), then
        falls back to parsing the HTML table with BeautifulSoup.

        The expiry URL parameter accepts both ``YYYY-MM-DD`` (monthly) and
        ``YYYY-MM-DD-w`` (weekly) formats; we try weekly first, then monthly.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise IBKROptionsError(
                "beautifulsoup4 is not installed. Run: pip install beautifulsoup4"
            )

        bc_sym = self._barchart_symbol(symbol)
        exp_ib = expiry_to_ib(expiry)
        now = datetime.now(timezone.utc)
        session = self._get_barchart_session(symbol)

        # Try weekly param first, then plain date (matches user's example URL)
        exp_params = [
            self._barchart_expiry_param(exp_ib, weekly=True),
            self._barchart_expiry_param(exp_ib, weekly=False),
        ]

        # --- Strategy 1: Core JSON API ---
        for exp_param in exp_params:
            try:
                api_resp = session.get(
                    _BARCHART_API_CHAIN,
                    params={
                        "symbol": bc_sym,
                        "expiration": exp_param,
                        "startStrike": "",
                        "endStrike": "",
                        "right": "call,put",
                        "moneyness": "all",
                        "page": "1",
                        "limit": "2000",
                        "raw": "1",
                    },
                    headers={"Accept": "application/json"},
                    timeout=15,
                )
                if api_resp.status_code != 200:
                    continue
                data = api_resp.json()
                rows = data.get("data", [])
                if not rows:
                    continue
                quotes = self._barchart_api_rows_to_quotes(rows, symbol, exp_ib, now)
                if quotes:
                    return quotes
            except Exception as exc:
                logger.debug("Barchart API chain failed (%s): %s", exp_param, exc)

        # --- Strategy 2: Parse HTML table with BeautifulSoup ---
        for exp_param in exp_params:
            page_url = (
                f"{_BARCHART_BASE}/stocks/quotes/{bc_sym}/options"
                f"?expiration={exp_param}"
            )
            try:
                resp = session.get(page_url, timeout=15)
                resp.raise_for_status()
                quotes = self._barchart_html_to_quotes(
                    resp.text, symbol, exp_ib, now
                )
                if quotes:
                    return quotes
            except Exception as exc:
                logger.debug("Barchart HTML chain failed (%s): %s", exp_param, exc)

        return []

    @staticmethod
    def _barchart_api_rows_to_quotes(
        rows: list[dict],
        symbol: str,
        exp_ib: str,
        now: datetime,
    ) -> list[OptionQuote]:
        """Convert Barchart core-API rows into OptionQuote objects."""
        quotes: list[OptionQuote] = []
        for row in rows:
            # Barchart returns separate call/put rows; optionType field: "call" or "put"
            right_raw = row.get("optionType", row.get("type", "")).lower()
            right = "C" if "call" in right_raw else ("P" if "put" in right_raw else None)
            if right is None:
                continue

            def _f(key: str) -> float | None:
                v = row.get(key)
                try:
                    f = float(v)
                    return f if f != 0 else None
                except (TypeError, ValueError):
                    return None

            strike = _f("strikePrice") or _f("strike")
            if strike is None:
                continue

            bid = _f("bid") or _f("bidPrice")
            ask = _f("ask") or _f("askPrice")
            last = _f("lastPrice") or _f("last")
            iv = _f("volatility") or _f("impliedVolatility")
            if iv and iv > 5:  # Barchart sometimes returns IV as percentage (e.g. 85.2)
                iv = iv / 100.0

            und = _f("baseLastPrice") or _f("underlyingPrice")
            volume = None
            v_raw = row.get("volume")
            try:
                volume = int(float(v_raw)) if v_raw else None
            except (TypeError, ValueError):
                pass
            oi = None
            oi_raw = row.get("openInterest")
            try:
                oi = int(float(oi_raw)) if oi_raw else None
            except (TypeError, ValueError):
                pass

            quotes.append(OptionQuote(
                symbol=symbol.upper(),
                expiry=exp_ib,
                strike=strike,
                right=right,
                last=last,
                bid=bid,
                ask=ask,
                mid=mid_price(bid, ask) or last,
                volume=volume,
                open_interest=oi,
                implied_vol=iv,
                delta=_f("delta"),
                gamma=_f("gamma"),
                theta=_f("theta"),
                vega=_f("vega"),
                rho=_f("rho"),
                underlying_price=und,
                timestamp=now,
            ))
        return quotes

    @staticmethod
    def _barchart_html_to_quotes(
        html: str,
        symbol: str,
        exp_ib: str,
        now: datetime,
    ) -> list[OptionQuote]:
        """Parse a Barchart options HTML page into OptionQuote objects using BeautifulSoup.

        Barchart renders calls and puts side-by-side in a single table where each
        row has columns: [call-side...] | Strike | [put-side...].  We detect the
        header layout and extract bid/ask for each side.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        quotes: list[OptionQuote] = []

        # --- Try embedded __NEXT_DATA__ JSON first ---
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script and script.string:
            try:
                nd = json.loads(script.string)
                raw_text = json.dumps(nd)
                # Look for rows with strikePrice + bid/ask
                import re as _re
                # Find all objects that look like option rows
                row_pattern = _re.compile(
                    r'\{[^{}]*"strikePrice"\s*:\s*"?([\d.]+)"?[^{}]*\}'
                )
                for m in row_pattern.finditer(raw_text):
                    try:
                        obj = json.loads(m.group(0))
                        right_raw = obj.get("optionType", obj.get("type", "")).lower()
                        right = "C" if "call" in right_raw else ("P" if "put" in right_raw else None)
                        if right is None:
                            continue
                        def _fv(k):
                            v = obj.get(k)
                            try:
                                f = float(v)
                                return f if f != 0 else None
                            except Exception:
                                return None
                        strike = _fv("strikePrice")
                        if not strike:
                            continue
                        bid = _fv("bid")
                        ask = _fv("ask")
                        quotes.append(OptionQuote(
                            symbol=symbol.upper(), expiry=exp_ib, strike=strike,
                            right=right, last=_fv("lastPrice"),
                            bid=bid, ask=ask, mid=mid_price(bid, ask) or _fv("lastPrice"),
                            volume=None, open_interest=None,
                            implied_vol=_fv("volatility"),
                            delta=None, gamma=None, theta=None, vega=None, rho=None,
                            underlying_price=_fv("baseLastPrice"),
                            timestamp=now,
                        ))
                    except Exception:
                        continue
                if quotes:
                    return quotes
            except Exception:
                pass

        # --- Fallback: find <table> elements and parse rows ---
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if not headers or "strike" not in " ".join(headers):
                continue

            # Locate column indices
            def _col(name: str) -> int | None:
                for i, h in enumerate(headers):
                    if name in h:
                        return i
                return None

            strike_col = _col("strike")
            bid_col = _col("bid")
            ask_col = _col("ask")
            last_col = _col("last")
            if strike_col is None:
                continue

            for tr in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cells) <= strike_col:
                    continue

                def _cell_f(idx: int | None) -> float | None:
                    if idx is None or idx >= len(cells):
                        return None
                    try:
                        v = float(cells[idx].replace(",", ""))
                        return v if v != 0 else None
                    except ValueError:
                        return None

                strike = _cell_f(strike_col)
                if not strike:
                    continue
                bid = _cell_f(bid_col)
                ask = _cell_f(ask_col)
                last = _cell_f(last_col)
                # Single-sided table: assume calls (most Barchart tables show calls by default)
                quotes.append(OptionQuote(
                    symbol=symbol.upper(), expiry=exp_ib, strike=strike,
                    right="C", last=last, bid=bid, ask=ask,
                    mid=mid_price(bid, ask) or last,
                    volume=None, open_interest=None, implied_vol=None,
                    delta=None, gamma=None, theta=None, vega=None, rho=None,
                    underlying_price=None, timestamp=now,
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
                    parsed = _parse_occ_symbol(opt.get("option", ""))
                    if parsed is not None:
                        expiries.add(parsed[1])  # YYYYMMDD from symbol
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

        if self._source == "barchart" or self._source is None:
            try:
                result = self._fetch_barchart_expirations(symbol)
                if result:
                    result = self._filter_future_expiries(result)
                    self._set_cached(cache_key, result)
                    return result
            except Exception as exc:
                errors.append(f"Barchart: {exc}")
                if self._source == "barchart":
                    raise IBKROptionsError(
                        f"Barchart source failed for {symbol} expirations: {exc}"
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
            return self._apply_strike_filter(cached, strike_range, max_strikes)  # type: ignore[arg-type]

        errors: list[str] = []
        # Track all quote sets from sources that returned data but lacked
        # bid/ask (market closed).  Used to return the best available data
        # instead of raising an error when no source has live quotes.
        _fallback_quote_sets: list[list[OptionQuote]] = []

        if self._source == "cboe" or self._source is None:
            try:
                data = self._fetch_cboe_json(symbol)
                quotes = self._cboe_to_quotes(data, symbol, exp_ib)
                if quotes:
                    # Fall through to next source if no bid/ask available (market closed)
                    if self._source is None and not self._has_bid_ask(quotes):
                        errors.append("CBOE: no bid/ask prices available")
                        _fallback_quote_sets.append(quotes)
                    else:
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
                    # Fall through if no bid/ask available
                    if self._source is None and not self._has_bid_ask(quotes):
                        errors.append("yfinance: no bid/ask prices available")
                        _fallback_quote_sets.append(quotes)
                    else:
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
                    # If Tradier returned quotes but none have bid/ask, fall through to Barchart
                    if self._source is None and not self._has_bid_ask(quotes):
                        errors.append("Tradier: no bid/ask prices available")
                        _fallback_quote_sets.append(quotes)
                    else:
                        self._set_cached(cache_key, quotes)
                        return self._apply_strike_filter(quotes, strike_range, max_strikes)
            except Exception as exc:
                errors.append(f"Tradier: {exc}")
                if self._source == "tradier":
                    raise IBKROptionsError(
                        f"Tradier source failed for {symbol} {expiry} chain: {exc}"
                    ) from exc

        if self._source == "barchart" or self._source is None:
            try:
                quotes = self._fetch_barchart_chain(symbol, exp_ib)
                if quotes:
                    if self._source is None and not self._has_bid_ask(quotes):
                        _fallback_quote_sets.append(quotes)
                    else:
                        self._set_cached(cache_key, quotes)
                        return self._apply_strike_filter(quotes, strike_range, max_strikes)
            except Exception as exc:
                errors.append(f"Barchart: {exc}")
                if self._source == "barchart":
                    raise IBKROptionsError(
                        f"Barchart source failed for {symbol} {expiry} chain: {exc}"
                    ) from exc

        # All sources lacked bid/ask or failed — return the best available
        # data by merging across sources for maximum coverage.
        if _fallback_quote_sets:
            merged = self._merge_quotes(_fallback_quote_sets)
            self._set_cached(cache_key, merged)
            return self._apply_strike_filter(merged, strike_range, max_strikes)

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
    def _has_bid_ask(quotes: list[OptionQuote]) -> bool:
        """Return True if at least one quote has a non-zero bid *and* ask."""
        return any(
            q.bid is not None and q.bid > 0 and q.ask is not None and q.ask > 0
            for q in quotes
        )

    @staticmethod
    def _count_priced(quotes: list[OptionQuote]) -> int:
        """Count quotes that have any usable price (mid, last, bid, or ask)."""
        return sum(
            1 for q in quotes
            if any(v is not None and v > 0 for v in [q.mid, q.last, q.bid, q.ask])
        )

    @staticmethod
    def _merge_quotes(
        quote_sets: list[list[OptionQuote]],
    ) -> list[OptionQuote]:
        """Merge quotes from multiple sources, keeping the best-priced per strike+right.

        When market is closed, different sources may have pricing for different
        strikes (CBOE has prev_day_close, yfinance has lastPrice, etc.).
        Merging gives the best coverage.
        """
        def _price_score(q: OptionQuote) -> int:
            s = 0
            if q.bid is not None and q.bid > 0:
                s += 3
            if q.ask is not None and q.ask > 0:
                s += 3
            if q.mid is not None and q.mid > 0:
                s += 2
            if q.last is not None and q.last > 0:
                s += 1
            if q.implied_vol is not None and q.implied_vol > 0:
                s += 1
            return s

        best: dict[tuple[float, str], OptionQuote] = {}
        for quotes in quote_sets:
            for q in quotes:
                key = (q.strike, q.right)
                existing = best.get(key)
                if existing is None or _price_score(q) > _price_score(existing):
                    best[key] = q
        return sorted(best.values(), key=lambda q: (q.right, q.strike))

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
