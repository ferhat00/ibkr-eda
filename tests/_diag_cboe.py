"""Diagnose CBOE VIX data availability per expiry."""
import json
import urllib.request
from collections import defaultdict

url = "https://cdn.cboe.com/api/global/delayed_quotes/options/_VIX.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ibkr-eda)"})
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode())

options = data.get("data", {}).get("options", [])
current_price = data.get("data", {}).get("current_price")
print(f"VIX current_price: {current_price}")
print(f"Total option records: {len(options)}")

from ibkr_eda.options.fallback_provider import _parse_occ_symbol

exp_stats = defaultdict(lambda: {
    "total": 0, "calls": 0, "has_bid": 0, "has_ask": 0,
    "has_last": 0, "has_prev_close": 0, "has_iv": 0,
})

for opt in options:
    parsed = _parse_occ_symbol(opt.get("option", ""))
    if parsed is None:
        continue
    _, expiry, right, strike = parsed
    s = exp_stats[expiry]
    s["total"] += 1
    if right == "C":
        s["calls"] += 1
    if opt.get("bid") is not None and float(opt.get("bid", 0)) > 0:
        s["has_bid"] += 1
    if opt.get("ask") is not None and float(opt.get("ask", 0)) > 0:
        s["has_ask"] += 1
    ltp = opt.get("last_trade_price")
    if ltp is not None and float(ltp) > 0:
        s["has_last"] += 1
    pdc = opt.get("prev_day_close")
    if pdc is not None and float(pdc) > 0:
        s["has_prev_close"] += 1
    iv = opt.get("iv")
    if iv is not None and float(iv) > 0:
        s["has_iv"] += 1

print(f"\nExpirations found: {len(exp_stats)}")
header = f"{'Expiry':<12} {'Total':>5} {'Calls':>5} {'Bid>0':>6} {'Ask>0':>6} {'Last>0':>7} {'PrevCl>0':>9} {'IV>0':>5}"
print(header)
print("-" * len(header))
for exp in sorted(exp_stats.keys()):
    s = exp_stats[exp]
    print(f"{exp:<12} {s['total']:>5} {s['calls']:>5} {s['has_bid']:>6} {s['has_ask']:>6} {s['has_last']:>7} {s['has_prev_close']:>9} {s['has_iv']:>5}")

# Show sample keys
if options:
    print(f"\nSample CBOE option keys: {sorted(options[0].keys())}")

# Show a sample from a far-dated expiry (last 3 options)
print("\nSample far-dated options:")
for opt in options[-3:]:
    print(json.dumps(opt, indent=2))

# Also check yfinance coverage
print("\n--- yfinance VIX expirations ---")
try:
    import yfinance as yf
    t = yf.Ticker("^VIX")
    yf_exps = t.options
    print(f"yfinance expirations ({len(yf_exps)}): {yf_exps[:10]}")
    # Try to get chain for a far-dated expiry
    if len(yf_exps) > 3:
        far_exp = yf_exps[3]
        chain = t.option_chain(far_exp)
        calls = chain.calls
        has_last = (calls["lastPrice"] > 0).sum()
        has_bid = (calls["bid"] > 0).sum()
        print(f"yfinance chain for {far_exp}: {len(calls)} calls, {has_bid} with bid>0, {has_last} with lastPrice>0")
except Exception as e:
    print(f"yfinance error: {e}")
