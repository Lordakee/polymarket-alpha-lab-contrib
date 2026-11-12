#!/usr/bin/env python3
"""Round45A fetch C: full event dumps + geopolitics/certification searches."""
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

for slug, name in [
    ("fed-rate-cut-by-629", "evt_fed_cut_by"),
    ("core-cpi-yoy-october-2026", "evt_cpi_yoy_oct"),
    ("core-cpi-mom-october-2026", "evt_cpi_mom_oct"),
    ("2026-midterms-house-turnout", "evt_house_turnout"),
    ("abdul-el-sayed-runs-behind-jocelyn-benson-by", "evt_elsayed_benson"),
    ("which-dems-will-underperform-kamala", "evt_underperform_kamala"),
]:
    get("/events", {"slug": slug}, name)

for q, name in [
    ("Fed decision December 2026 meeting", "search_fed_dec_meeting"),
    ("rate cut 2026", "search_rate_cut26"),
    ("Senate seats 2026 how many", "search_senate_seats"),
    ("House seats 2026 how many", "search_house_seats"),
    ("recount certification 2026", "search_recount"),
    ("sanctions deadline", "search_sanctions"),
    ("election November 2026", "search_election_nov"),
    ("referendum 2026", "search_referendum"),
    ("Russia Ukraine", "search_russia_ukraine"),
    ("government funding continuing resolution January", "search_funding_cr"),
]:
    get("/public-search", {"q": q, "limit_events": 10, "limit_markets": 6}, name)

print("DONE batch C")
