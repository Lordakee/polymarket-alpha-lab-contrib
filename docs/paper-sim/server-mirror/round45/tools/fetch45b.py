#!/usr/bin/env python3
"""Round45A fetch B: full FR advance event + related French events."""
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

get("/events", {"slug": "next-french-presidential-election-who-will-advance-to-the-2nd-round"}, "fr_advance_event")
get("/events", {"slug": "2027-french-presidential-election-national-rally-candidate"}, "fr_rn_candidate")
get("/events", {"slug": "2027-french-presidential-election-attal-vs-philippe"}, "fr_attal_philippe")
get("/events", {"slug": "2027-french-presidential-election-who-will-be-on-the-ballot"}, "fr_ballot")
get("/public-search", {"q": "French election Mellonium", "limit_events": 8, "limit_markets": 8}, "search_mellonium")
print("DONE batch B")
