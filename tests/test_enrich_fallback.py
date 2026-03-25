"""Quick test for VIXData._enrich() fallback logic."""
import pandas as pd
import numpy as np
from ibkr_eda.hedging.vix_data import VIXData


def test_enrich_per_row_fallbacks():
    """Mid should be filled per-row from bid/ask, last, or intrinsic value."""
    df = pd.DataFrame({
        "strike": [15.0, 20.0, 25.0, 30.0, 35.0],
        "right": ["C"] * 5,
        "bid": [None, None, None, 1.2, 0.5],
        "ask": [None, None, None, 1.8, 0.9],
        "mid": [None, None, 2.0, None, None],
        "last": [None, 3.5, None, None, None],
        "underlying_price": [25.0] * 5,
        "expiry": ["20260616"] * 5,
    })

    result = VIXData._enrich(df, 100_000)
    mids = result["mid"].tolist()
    print("Mid values after enrichment:")
    for s, m in zip(result["strike"], mids):
        print(f"  Strike {s:.0f}: mid={m}")

    # Strike 15: ITM intrinsic = 25-15 = 10
    assert mids[0] == 10.0, f"Expected 10.0, got {mids[0]}"
    # Strike 20: last = 3.5
    assert mids[1] == 3.5, f"Expected 3.5, got {mids[1]}"
    # Strike 25: existing mid = 2.0
    assert mids[2] == 2.0, f"Expected 2.0, got {mids[2]}"
    # Strike 30: (1.2+1.8)/2 = 1.5
    assert mids[3] == 1.5, f"Expected 1.5, got {mids[3]}"
    # Strike 35: (0.5+0.9)/2 = 0.7
    assert abs(mids[4] - 0.7) < 0.01, f"Expected 0.7, got {mids[4]}"

    # Derived columns should also be populated
    assert result["cost_per_contract"].notna().all()
    assert result["breakeven_vix"].notna().all()

    print("All enrichment tests passed!")


if __name__ == "__main__":
    test_enrich_per_row_fallbacks()
