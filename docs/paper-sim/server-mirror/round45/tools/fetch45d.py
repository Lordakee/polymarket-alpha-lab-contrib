#!/usr/bin/env python3
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
            json.dump({"url": url, "data": data}, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
            return data
        except Exception as e:
            print("RETRY", name, i, repr(e)); time.sleep(2 + i)
    print("FAIL", name); return None

get("/events", {"slug": "fed-decision-in-december-20260729232808632"}, "evt_fed_dec_decision")
get("/public-search", {"q": "seat flip Senate House races called", "limit_events": 10, "limit_markets": 6}, "search_races_called")
get("/public-search", {"q": "Kamala margin 2024", "limit_events": 6, "limit_markets": 4}, "search_kamala_margin")
get("/public-search", {"q": "Georgia Senate runoff", "limit_events": 6, "limit_markets": 4}, "search_runoff_ga")
print("DONE batch D")
