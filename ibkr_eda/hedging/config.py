"""Constants and configuration for VIX portfolio insurance analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# VIX contract specifications
# ---------------------------------------------------------------------------

VIX_MULTIPLIER = 100  # VIX options: $100 per index point

# ---------------------------------------------------------------------------
# VIX response model — pre-fitted power-law constants
# VIX_peak ≈ current_vix + A × |spx_drawdown|^B
# Fitted to historical stress events (2008–2024).
# ---------------------------------------------------------------------------

VIX_RESPONSE_A = 155.0
VIX_RESPONSE_B = 0.55

# ---------------------------------------------------------------------------
# Historical stress events
# (name, spx_drawdown, vix_peak, vix_start, start_date, end_date)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StressEvent:
    name: str
    spx_drawdown: float  # negative, e.g. -0.34
    vix_peak: float
    vix_start: float
    start_date: str  # YYYY-MM-DD
    end_date: str


STRESS_EVENTS: list[StressEvent] = [
    StressEvent("GFC 2008",           -0.568, 80.86, 22.0, "2007-10-09", "2009-03-09"),
    StressEvent("Flash Crash 2010",   -0.160, 45.79, 17.0, "2010-04-23", "2010-07-02"),
    StressEvent("Euro Crisis 2011",   -0.217, 48.00, 15.0, "2011-04-29", "2011-10-03"),
    StressEvent("China Deval 2015",   -0.124, 40.74, 12.5, "2015-08-10", "2015-08-25"),
    StressEvent("Volmageddon 2018",   -0.101, 37.32, 11.0, "2018-01-26", "2018-02-08"),
    StressEvent("COVID Mar 2020",     -0.339, 82.69, 14.0, "2020-02-19", "2020-03-23"),
    StressEvent("Fed Hike 2022",      -0.254, 36.45, 17.0, "2022-01-03", "2022-10-12"),
]

# ---------------------------------------------------------------------------
# Hedge profiles
# ---------------------------------------------------------------------------

HEDGE_PROFILES: dict[str, dict] = {
    "conservative": {
        "description": "Full coverage, near-the-money, higher premium",
        "target_drawdown": 0.20,   # protect against -20% drawdown
        "otm_range": (0.0, 0.10),  # ATM to 10% OTM
        "min_dte": 20,
        "max_dte": 90,
        "max_cost_bps": 75,        # max premium as bps of NAV
    },
    "moderate": {
        "description": "Balanced coverage, slightly OTM, mid premium",
        "target_drawdown": 0.30,
        "otm_range": (0.05, 0.20),
        "min_dte": 30,
        "max_dte": 120,
        "max_cost_bps": 50,
    },
    "aggressive": {
        "description": "Tail-risk only, deep OTM, cheap convexity",
        "target_drawdown": 0.40,
        "otm_range": (0.15, 0.40),
        "min_dte": 45,
        "max_dte": 180,
        "max_cost_bps": 25,
    },
}

# ---------------------------------------------------------------------------
# Demo portfolio (used when TWS is unavailable)
# ---------------------------------------------------------------------------

DEMO_PORTFOLIO: dict[str, dict] = {
    "AAPL":  {"shares": 150, "avg_cost": 178.50, "exchange": "NASDAQ"},
    "MSFT":  {"shares": 100, "avg_cost": 380.20, "exchange": "NASDAQ"},
    "GOOGL": {"shares":  80, "avg_cost": 141.30, "exchange": "NASDAQ"},
    "AMZN":  {"shares":  60, "avg_cost": 178.80, "exchange": "NASDAQ"},
    "NVDA":  {"shares": 200, "avg_cost":  85.40, "exchange": "NASDAQ"},
    "JPM":   {"shares": 120, "avg_cost": 195.60, "exchange": "NYSE"},
    "JNJ":   {"shares":  90, "avg_cost": 155.70, "exchange": "NYSE"},
    "V":     {"shares":  70, "avg_cost": 280.30, "exchange": "NYSE"},
    "PG":    {"shares": 100, "avg_cost": 160.40, "exchange": "NYSE"},
    "XOM":   {"shares": 110, "avg_cost": 105.80, "exchange": "NYSE"},
}

# ---------------------------------------------------------------------------
# Chart styling (matches dashboard_v2)
# ---------------------------------------------------------------------------

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="black"),
    title_font=dict(color="black"),
)

COLORS = {
    "primary": "#0077bb",
    "success": "#009955",
    "danger": "#cc3333",
    "warning": "#cc8800",
    "accent": "#7733cc",
    "gray": "#555555",
}
