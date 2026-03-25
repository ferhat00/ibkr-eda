"""Diagnostic: compare CBOE OCC expiry dates to check for off-by-one."""
import json
import re
import urllib.request
from datetime import datetime

url = "https://cdn.cboe.com/api/global/delayed_quotes/options/_VIX.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())

occ_re = re.compile(r"^([A-Z^]+)(\d{6})([CP])(\d{8})$")
expiries = set()
for opt in data.get("data", {}).get("options", []):
    m = occ_re.match(opt.get("option", "").replace(" ", "").upper())
    if m:
        yymmdd = m.group(2)
        century = "19" if int(yymmdd[:2]) >= 50 else "20"
        expiries.add(f"{century}{yymmdd}")

print("CBOE VIX expiries (from OCC symbols):")
for e in sorted(expiries)[:15]:
    d = datetime.strptime(e, "%Y%m%d")
    print(f"  {e}  {d.strftime('%A, %B %d, %Y')}")

# Now check what yfinance reports
try:
    import yfinance as yf
    t = yf.Ticker("^VIX")
    print("\nyfinance VIX expiries:")
    for exp_str in t.options[:15]:
        d = datetime.strptime(exp_str, "%Y-%m-%d")
        ib_fmt = exp_str.replace("-", "")
        print(f"  {ib_fmt}  {d.strftime('%A, %B %d, %Y')}")
except Exception as exc:
    print(f"\nyfinance error: {exc}")
