# ibkr-eda

Exploratory data analysis toolkit for Interactive Brokers — featuring a professional trade dashboard, an options data layer, a VIX portfolio-insurance toolkit, and a Python package for accessing IBKR data via TWS and the Flex Web Service.

## Features

- **Trade Dashboard** — interactive Flask web app for portfolio-level trade analysis with filters, charts, and performance metrics
- **Options Module** — option chains, Greeks, and IV surfaces with automatic IBKR TWS / free-data fallback (yfinance, CBOE, Tradier, Barchart)
- **VIX Hedging** — scenario-based drawdown analysis, VIX call enrichment, and optimal hedge selection across three risk profiles
- **Flex Web Service** — fetch years of execution history without a live IB Gateway connection
- **TWS API** — live executions, open orders, positions, P&L, market data, and contract search via `ib_async`

---

## Requirements

- Python 3.11+
- Interactive Brokers account

---

## Installation

```bash
git clone https://github.com/your-username/ibkr-eda.git
cd ibkr-eda

# Core package only
pip install -e .

# With dashboard support
pip install -e ".[dashboard]"

# With Flex Web Service support
pip install -e ".[flex]"

# With free options data (yfinance fallback)
pip install -e ".[options]"

# With VIX hedge notebook (plotly + ipywidgets + yfinance)
pip install -e ".[hedge]"

# Advanced dashboard (Dash, Plotly, pyfolio, riskfolio)
pip install -e ".[dashboard-v2]"

# Everything
pip install -e ".[dashboard,flex,options,hedge,dev]"
```

---

## Configuration

Create a `.env` file in the project root:

```env
# TWS / IB Gateway (required for live data)
IBKR_TWS_HOST=127.0.0.1
IBKR_TWS_PORT=4002          # 4002 = paper, 4001 = live
IBKR_TWS_CLIENT_ID=1
IBKR_ACCOUNT_ID=U1234567    # optional; auto-detected if omitted

# Flex Web Service (required for dashboard live fetch and long history)
IBKR_FLEX_TOKEN=your_token_here
IBKR_FLEX_QUERY_ID=your_query_id_here

# Options fallback providers (all optional)
TRADIER_TOKEN=your_tradier_sandbox_token  # free at developer.tradier.com

# Options behavior (all optional)
OPTIONS_CACHE_TTL=300                      # seconds to cache options chains/Greeks

# IBKR market data type (TWS "marketDataType"; optional)
IBKR_MARKET_DATA_TYPE=REALTIME             # allowed: REALTIME, FROZEN, DELAYED, DELAYED_FROZEN
```

### Setting up Flex Web Service credentials

1. Log in to [IBKR Account Management](https://www.interactivebrokers.com/sso/Login)
2. Go to **Reports → Flex Queries → Create → Activity Flex Query**
   - Section: **Trades**, detail level: **Executions**, output: **XML**, delivery: **Web Service**
   - Note the **Query ID**
3. Go to **Reports → Settings → FlexWeb Service → Generate Token**
   - Note the **Token**
4. Add both values to your `.env` file

---

## Trade Dashboard

The dashboard provides an interactive portfolio analysis interface running locally in your browser.

### Start the dashboard

```bash
# Load from the local CSV (auto-detected from data/)
python -m ibkr_eda.dashboard

# Fetch live data from IBKR Flex Web Service (requires credentials in .env)
python -m ibkr_eda.dashboard --source live

# Custom options
python -m ibkr_eda.dashboard --port 8080 --debug
python -m ibkr_eda.dashboard --csv data/trades_U1234567.csv
```

Then open **http://127.0.0.1:5050** in your browser.

If you installed with `pip install -e ".[dashboard]"`, you can also use the shorthand:

```bash
ibkr-dashboard
ibkr-dashboard --source live
```

There is also an advanced Dash-based dashboard (v2). Start it with:

```bash
python -m ibkr_eda.dashboard_v2
# or
ibkr-dashboard-v2
```

Then open **http://127.0.0.1:8050** in your browser.

### Dashboard sections

| Section | Description |
|---|---|
| **Summary cards** | Total P&L, Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown, Total Trades |
| **Cumulative P&L & Drawdown** | Equity curve with high-water mark and drawdown panel |
| **P&L Distribution** | Histogram of per-trade realized P&L, winners vs losers |
| **P&L by Symbol** | Horizontal bar chart — toggle between P&L and trade count |
| **Time Patterns** | Activity and P&L broken down by hour of day, day of week, and month |
| **Market Breakdown** | Country, currency, and security type split (donut charts) |
| **Commission Analysis** | Distribution histogram and top 15 symbols by commission paid |
| **Trade History** | Sortable, paginated table with all executions |

### Filters

The sidebar provides dynamic filters applied across all charts simultaneously:

- **Date range** — start and end date pickers
- **Asset class** — Equities, FX/Cash, etc.
- **Market / Country** — US, UK, HK, DE, FX, and more (derived from exchange)
- **Currency** — USD, HKD, GBP, etc.
- **Exchange** — individual venue selection (advanced)
- **Symbol** — substring search with autocomplete
- **Side** — BUY / SELL

### Data sources

The dashboard sidebar has a toggle to switch between:

- **Local CSV** — reads `data/trades_*.csv` (auto-detected). Fast, works offline.
- **Live Flex** — fetches fresh data directly from IBKR. Requires Flex credentials in `.env`.

Click **Reload Data** after switching sources.

### Saving trade data locally

Run the fetch notebook to download and persist trade history:

```bash
jupyter notebook notebooks/01_trade_eda.ipynb
```

The notebook fetches via Flex, merges with any existing CSV, deduplicates on `execution_id`, and saves to `data/trades_<account_id>.csv`.

---

## Options

The `ibkr_eda.options` module provides option chains, Greeks, and IV surfaces. It automatically uses your live IBKR TWS connection when available and transparently falls back to free public data sources (CBOE delayed quotes → yfinance → Tradier sandbox → Barchart) when TWS is unavailable or disconnects.

```python
from ibkr_eda import IBKR

ib = IBKR()  # or IBKR(auto_connect=False) for offline use

# Option chain (OptionChainData with separate calls/puts DataFrames)
chain = ib.options.get("AAPL", expiry="2025-06-20")
calls_df = chain.calls
puts_df = chain.puts

# All expirations
expiries = ib.options.get_expirations("AAPL")

# Greeks for a single contract
greeks_df = ib.greeks.get("AAPL", expiry="2025-06-20", strike=200.0, right="C")

# Implied volatility surface (strikes × expiries)
iv_df = ib.vol_surface.get("SPY")

# ATM term structure
term_df = ib.vol_surface.get_term_structure("SPY")
```

### Using the fallback provider directly (no TWS)

```python
from ibkr_eda.options.chain import OptionChains
from ibkr_eda.options.fallback_provider import FallbackOptionsProvider

# Use a specific source
chains = OptionChains(provider=FallbackOptionsProvider(source="cboe"))
df = chains.get("VIX", expiry="2025-06-18")

# Auto-cascade through all free sources
chains = OptionChains(provider=FallbackOptionsProvider())  # tries yfinance → cboe → tradier → barchart
```

---

## VIX Hedging

The `ibkr_eda.hedging` module provides a scenario-based VIX portfolio-insurance workflow. It fetches and enriches VIX call options, models S&P 500 drawdown scenarios and the resulting VIX spike, then recommends optimal hedges across three risk profiles.

### Notebooks

| Notebook | Description |
|---|---|
| `notebooks/02_options_explorer.ipynb` | Interactive options chain and Greeks explorer |
| `notebooks/03_vix_hedge.ipynb` | Full VIX hedge analysis: fetch calls, model scenarios, select hedges |

### Programmatic usage

```python
from ibkr_eda.hedging import VIXData, ScenarioEngine, HedgeAdvisor

# 1. Fetch and enrich VIX call options (no TWS required)
vix = VIXData()                        # uses free fallback data sources
calls_df = vix.get_calls()             # DataFrame with bid, ask, greeks, moneyness, payoff ratios
term_structure = vix.get_term_structure(portfolio_value=500_000)  # VIX futures / term structure snapshot (portfolio_value required)

# 2. Build scenario engine
engine = ScenarioEngine(
    portfolio_value=500_000,
    portfolio_beta=1.0,
    current_vix=18.0,
)
scenarios = engine.stress_table()      # DataFrame: spx_drawdown → portfolio_loss, vix_estimate, hedge_payoff

# 3. Select optimal hedge
advisor = HedgeAdvisor(calls_df, engine, current_vix=18.0)
rec = advisor.recommend(profile="moderate")   # or "conservative" / "aggressive"
print(rec)  # strike, expiry, contracts_needed, cost_bps, payoff_ratio_40, …

# Get all three profiles at once
all_recs = advisor.recommend_all()    # dict[str, pd.Series | None]
```

### Hedge profiles

| Profile | Target drawdown | OTM range | Max DTE | Max cost |
|---|---|---|---|---|
| `conservative` | 20% | ATM – 10% OTM | 20–90 d | 75 bps |
| `moderate` | 30% | 5% – 20% OTM | 30–120 d | 50 bps |
| `aggressive` | 40% | 15% – 40% OTM | 45–180 d | 25 bps |

---

## Python Package

### Flex Web Service (no live connection required)

```python
from ibkr_eda.config import IBKRConfig
from ibkr_eda.trades.flex import FlexTrades

config = IBKRConfig.from_env()
flex = FlexTrades(config)

df = flex.get(account_id="U1234567", start_date="2025-01-01")
print(df.head())
```

### TWS API (requires IB Gateway or TWS running)

```python
from ibkr_eda import IBKR

ib = IBKR()                              # connects synchronously

# Positions
positions = ib.positions.get()

# Recent executions (~7 days)
executions = ib.executions.get()

# Account P&L
pnl = ib.pnl.get()

# Market data
snap = ib.snapshot.get(conids=[265598])  # AAPL

# Historical bars
history = ib.history.get(conid=265598, period="1m", bar="1d")

# Options (auto-selects IBKR or free fallback)
chain = ib.options.get("AAPL", expiry="2025-06-20")
calls_df = chain.calls
puts_df  = chain.puts
greeks_df = ib.greeks.get("AAPL", expiry="2025-06-20", strike=200.0, right="C")
iv_df     = ib.vol_surface.get("SPY")
```

### Async usage (Jupyter / Python 3.14+)

```python
from ibkr_eda import IBKR

ib = await IBKR.create_async()
positions = await ib.positions.get_async()
```

---

## Data Schema

The `FlexTrades.get()` DataFrame and the CSV files share this schema:

| Column | Type | Description |
|---|---|---|
| `execution_id` | int | Unique IBKR execution ID |
| `contract_id` | int | IBKR contract ID (conid) |
| `symbol` | str | Ticker symbol |
| `sec_type` | str | `STK`, `CASH`, `OPT`, `FUT`, etc. |
| `currency` | str | Settlement currency |
| `side` | str | `BUY` or `SELL` |
| `quantity` | float | Shares/units (negative for sells) |
| `price` | float | Execution price |
| `order_ref` | str | Optional client order reference |
| `account_id` | str | IBKR account number |
| `exchange` | str | Executing venue |
| `commission` | float | Commission paid (positive) |
| `realized_pnl` | float | FIFO realized P&L for this fill |
| `trade_time` | datetime | UTC execution timestamp |

---

## Project Structure

```
ibkr-eda/
├── data/                        # Local trade CSVs (gitignored)
├── notebooks/
│   ├── 00_connection_test.ipynb # TWS connectivity smoke-test
│   ├── 01_trade_eda.ipynb       # Full EDA: fetch, persist, and analyse
│   ├── 02_options_explorer.ipynb# Option chain & Greeks explorer
│   └── 03_vix_hedge.ipynb       # VIX portfolio-insurance workflow
└── ibkr_eda/
    ├── dashboard/               # Flask trade dashboard (v1)
    │   ├── app.py               # Flask app factory + API routes
    │   ├── data_loader.py       # CSV/Flex loading, derived columns
    │   ├── metrics.py           # Performance metric computations
    │   ├── templates/           # Jinja2 HTML templates
    │   └── static/              # JavaScript (dashboard.js)
    ├── dashboard_v2/            # Advanced Dash dashboard (v2)
    ├── options/                 # Options data module
    │   ├── chain.py             # OptionChains — chains with IBKR/fallback routing
    │   ├── greeks.py            # Greeks — single/multi-contract Greeks
    │   ├── surface.py           # VolSurface — IV surface builder
    │   ├── ibkr_provider.py     # IBKR TWS options provider
    │   ├── fallback_provider.py # Free fallback: yfinance/CBOE/Tradier/Barchart
    │   ├── provider.py          # Abstract provider protocol + data types
    │   └── utils.py             # OCC parsing, strike filtering, DTE helpers
    ├── hedging/                 # VIX portfolio-insurance module
    │   ├── vix_data.py          # VIXData — fetch and enrich VIX calls
    │   ├── scenarios.py         # ScenarioEngine — drawdown × VIX models
    │   ├── recommendations.py   # HedgeAdvisor — profile-based hedge selection
    │   └── config.py            # Constants, stress events, hedge profiles
    ├── trades/
    │   ├── flex.py              # FlexTrades — Flex Web Service
    │   ├── executions.py        # Recent executions via TWS
    │   └── orders.py            # Open orders via TWS
    ├── portfolio/
    │   ├── accounts.py          # Account list and summary
    │   ├── positions.py         # Current holdings
    │   └── pnl.py               # Daily / unrealized / realized P&L
    ├── market_data/
    │   ├── history.py           # OHLCV bars
    │   └── snapshot.py          # Real-time quotes
    ├── contracts/
    │   ├── search.py            # Symbol search
    │   └── details.py           # Contract metadata
    ├── config.py                # IBKRConfig (reads from .env)
    └── exceptions.py            # Exception hierarchy
```
