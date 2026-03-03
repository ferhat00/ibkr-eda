"""Historical trade data via IBKR Flex Web Service API.

Unlike the TWS API (limited to ~7 days), Flex queries can retrieve years of
execution history without a live IB Gateway connection.

Prerequisites
-------------
1. Create an Activity Flex Query in Account Management:
   Reports → Flex Queries → Create → Activity Flex Query
   Sections: Trades (check "Executions" detail level)
   Output: XML, Delivery: Web Service
   Note the **Query ID**.

2. Generate an access token:
   Reports → Settings → FlexWeb Service → Generate Token
   Note the **Token**.

3. Add to your .env file::

       IBKR_FLEX_TOKEN=your_token_here
       IBKR_FLEX_QUERY_ID=your_query_id_here

4. Install the optional dependency::

       pip install ibflex
"""

from __future__ import annotations

import datetime
import logging
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pandas as pd

from ibkr_eda.exceptions import IBKRError

if TYPE_CHECKING:
    from ibkr_eda.config import IBKRConfig

logger = logging.getLogger(__name__)


class FlexTrades:
    """Fetch full execution history via the IBKR Flex Web Service.

    Parameters
    ----------
    config : IBKRConfig
        Must have ``flex_token`` and ``flex_query_id`` set (via env vars
        ``IBKR_FLEX_TOKEN`` / ``IBKR_FLEX_QUERY_ID`` or directly).
    """

    def __init__(self, config: IBKRConfig):
        self.config = config

    def _require_ibflex(self):
        try:
            import ibflex.client  # noqa: F401
            import ibflex.parser  # noqa: F401
        except ImportError as exc:
            raise IBKRError(
                "ibflex is not installed. Run: pip install ibflex"
            ) from exc

    def _require_credentials(self):
        if not self.config.flex_token or not self.config.flex_query_id:
            raise IBKRError(
                "Flex credentials missing. Set IBKR_FLEX_TOKEN and "
                "IBKR_FLEX_QUERY_ID in your .env file."
            )

    def get(
        self,
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Download and return Flex execution history as a DataFrame.

        The returned DataFrame has the same columns as ``IBKR.executions.get()``
        so it can be used as a drop-in replacement for longer history windows.

        Note: the ``side`` column contains ``"BUY"`` / ``"SELL"`` (Flex standard)
        rather than the TWS values ``"BOT"`` / ``"SLD"``.

        Parameters
        ----------
        account_id : str, optional
            Filter to a specific account.
        start_date : str, optional
            Earliest trade date to include (``"YYYY-MM-DD"``).
        end_date : str, optional
            Latest trade date to include (``"YYYY-MM-DD"``).
        """
        self._require_ibflex()
        self._require_credentials()

        import ibflex.client as flex_client
        import ibflex.parser as flex_parser

        logger.info(
            "Downloading Flex statement (query_id=%s)...", self.config.flex_query_id
        )
        raw_xml = flex_client.download(
            self.config.flex_token, self.config.flex_query_id
        )
        raw_xml = _strip_unknown_flex_attrs(raw_xml)

        # ibflex is strict about enum values and currency codes; any value
        # added by IBKR after the library was last updated causes a
        # FlexParserError.  Patch parse_element_attr to return None for those
        # fields instead of crashing.
        _orig_parse_attr = flex_parser.parse_element_attr

        def _lenient_parse_attr(Class, name, value):
            try:
                return _orig_parse_attr(Class, name, value)
            except flex_parser.FlexParserError:
                logger.debug(
                    "ibflex: ignoring conversion error for %s.%s=%r",
                    Class.__name__, name, value,
                )
                return (name, None)

        flex_parser.parse_element_attr = _lenient_parse_attr
        try:
            response = flex_parser.parse(raw_xml)
        finally:
            flex_parser.parse_element_attr = _orig_parse_attr

        rows = []
        for stmt in response.FlexStatements:
            # Activity Flex queries populate stmt.Trades; Trade Confirmation
            # queries populate stmt.TradeConfirms. Support both.
            records = list(stmt.Trades) + list(stmt.TradeConfirms)
            for t in records:
                row = _trade_to_row(t)
                if row is not None:
                    rows.append(row)

        if not rows:
            logger.warning("Flex statement returned no trade records.")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["trade_time"] = pd.to_datetime(df["trade_time"], utc=True)
        df = df.sort_values("trade_time").reset_index(drop=True)

        if account_id:
            df = df[df["account_id"] == account_id]

        if start_date or end_date:
            dates = df["trade_time"].dt.normalize()
            if start_date:
                df = df[dates >= pd.Timestamp(start_date, tz="UTC")]
            if end_date:
                dates = df["trade_time"].dt.normalize()
                df = df[dates <= pd.Timestamp(end_date, tz="UTC")]

        logger.info("Flex query returned %d execution(s).", len(df))
        return df.reset_index(drop=True)


def _strip_unknown_flex_attrs(raw_xml: bytes) -> bytes:
    """Remove XML attributes that ibflex's types don't know about.

    ibflex raises a KeyError (re-raised as FlexParserError) for unknown
    attributes because it passes all attrs as kwargs to the dataclass
    constructor.  Stripping them at the XML level is the only clean fix.

    Conversion errors for *known* attributes (bad enum values, unknown
    currency codes, etc.) are handled separately by monkey-patching
    parse_element_attr in FlexTrades.get().
    """
    import dataclasses
    import inspect

    from ibflex import Types

    # Build {tag: set_of_known_attr_names} from ibflex dataclasses.
    known: dict[str, set[str]] = {}
    for _name, cls in inspect.getmembers(Types, inspect.isclass):
        if dataclasses.is_dataclass(cls):
            known[_name] = set(cls.__annotations__)

    root = ET.fromstring(raw_xml)
    for elem in root.iter():
        allowed = known.get(elem.tag)
        if allowed is None:
            continue
        for attr in [k for k in elem.attrib if k not in allowed]:
            logger.debug("ibflex: dropping unknown %s.%s", elem.tag, attr)
            del elem.attrib[attr]

    return ET.tostring(root, encoding="unicode").encode()


def _trade_to_row(t) -> dict | None:
    """Map a single ibflex Trade or TradeConfirm object to a dict row."""
    # Build a UTC-aware trade_time from dateTime if available, else tradeDate+tradeTime
    trade_time: datetime.datetime | None = None
    if getattr(t, "dateTime", None) is not None:
        dt = t.dateTime
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        trade_time = dt
    elif getattr(t, "tradeDate", None) is not None:
        d = t.tradeDate
        tm = getattr(t, "tradeTime", None) or datetime.time(0, 0)
        trade_time = datetime.datetime.combine(d, tm, tzinfo=datetime.timezone.utc)

    if trade_time is None:
        return None  # skip records without a timestamp

    # Normalise enums to their string values; guard against None
    side = t.buySell.value if t.buySell is not None else None
    sec_type = t.assetCategory.value if t.assetCategory is not None else None

    # ibflex returns commissions as negative Decimals; store as float (positive)
    commission = t.ibCommission
    if commission is not None:
        commission = abs(float(commission))

    realized_pnl = t.fifoPnlRealized
    if realized_pnl is not None:
        realized_pnl = float(realized_pnl)

    return {
        "execution_id": getattr(t, "execID", None) or getattr(t, "tradeID", None),
        "contract_id": t.conid,
        "symbol": t.symbol,
        "sec_type": sec_type,
        "currency": t.currency,
        "side": side,
        "quantity": float(t.quantity) if t.quantity is not None else None,
        "price": float(t.tradePrice) if t.tradePrice is not None else None,
        "order_ref": getattr(t, "orderReference", None),
        "account_id": t.accountId,
        "exchange": t.exchange,
        "commission": commission,
        "realized_pnl": realized_pnl,
        "trade_time": trade_time,
    }
