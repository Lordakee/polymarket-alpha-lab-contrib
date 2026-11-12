#!/usr/bin/env python3
"""Round45A fetch: Gamma events/markets for politics+macro scan. Paper-only, read-only."""
import json, urllib.request, urllib.parse, os, time

OUT = os.path.expanduser("~/paper-sim/round45/raw")
BASE = "https://gamma-api.polymarket.com"

def get(path, params, name, retries=3):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-sim-round45/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
            with open(os.path.join(OUT, name + ".json"), "w") as f:
                json.dump({"url": url, "data": data}, f, indent=1)
            return data
        except Exception as e:
            print("RETRY", name, i, repr(e)); time.sleep(2+i)
    print("FAIL", name); return None

# 1) French 2027: main events
for slug in ["next-french-presidential-election",
             "2027-french-presidential-election-who-will-be-on-the-ballot"]:
    get("/events", {"slug": slug}, "fr_event_" + slug[:30])

# 2) public-search: French second round / advance
get("/public-search", {"q": "French election second round advance", "limit_events": 15, "limit_markets": 10}, "search_fr_advance")

# 3) midterms / certification
get("/public-search", {"q": "midterm", "limit_events": 15, "limit_markets": 10}, "search_midterm")
get("/public-search", {"q": "Senate seat count certification", "limit_events": 10, "limit_markets": 10}, "search_senate_cert")

# 4) Fed / FOMC / CPI
get("/public-search", {"q": "Fed rate cut December", "limit_events": 15, "limit_markets": 10}, "search_fed_dec")
get("/public-search", {"q": "CPI", "limit_events": 10, "limit_markets": 10}, "search_cpi")

# 5) shutdown / funding
get("/public-search", {"q": "government shutdown", "limit_events": 10, "limit_markets": 10}, "search_shutdown")

print("DONE batch A")
