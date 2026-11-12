import json
from datetime import datetime, timezone

hist = json.load(open("/home/ubuntu/paper-sim/round45/raw/fr_advance_history.json"))
ENTRY_TS = 1762721587  # approx 2026-10-10 14:13 UTC (decision #4 ts)
print("leg | Oct-10 p | min since | max since | now | move since entry")
for q, pts in hist.items():
    if not pts: continue
    oct10 = None
    for p in pts:
        if p["t"] <= ENTRY_TS: oct10 = p["p"]  # last at/before entry
    now = pts[-1]["p"]
    vals = [p["p"] for p in pts if p["t"] >= ENTRY_TS - 86400]
    mn = min(vals) if vals else None; mx = max(vals) if vals else None
    # p is YES price of the token (YES token queried)
    name = q.replace("Will ", "").replace(" advance to the second round of the next French presidential election?", "")
    print("%-22s | oct10=%-7s | min=%-7s max=%-7s | now=%-7s | chg=%+0.3f" % (name[:22], oct10, mn, mx, now, (now - oct10) if oct10 is not None else float("nan")))
