"""Dashboard V2 configuration defaults."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / ".cache_v2"

# Risk-free rate (annualised) used for Sharpe / Sortino
RISK_FREE_RATE = 0.045

# Monte-Carlo defaults
MC_SIMULATIONS = 10_000
MC_HORIZON_DAYS = 252

# Rolling window defaults (trading days)
ROLLING_WINDOW = 63  # ~3 months

# Benchmarks
BENCHMARK_TICKERS = {"SPY": "SPY", "ACWI": "ACWI"}

# Cache TTL in seconds (24 h)
CACHE_TTL = 86_400
