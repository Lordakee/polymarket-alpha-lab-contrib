import json, urllib.request, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

# find DAL@PHI event id from scoreboard
d = json.load(open("espn_nfl_20261026.json"))
ev = d["events"][0]
eid = ev["id"]
print("MNF event:", ev.get("name"), eid)

s = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=" + eid)
pc = s.get("pickcenter", [])
for p in pc:
    prov = p.get("provider", {}).get("name", "?")
    ml = p.get("moneyline", {})
    a = (ml.get("away") or {}).get("close", {}).get("odds", "")
    h = (ml.get("home") or {}).get("close", {}).get("odds", "")
    if prov in ("ESPN BET", "Caesars", "DraftKings", "FanDuel", "BetMGM"):
        print("BOOK", prov, "away(DAL)", a, "home(PHI)", h, "spr", p.get("spread"), "ou", p.get("overUnder"))
for team in s.get("injuries", [])[:2]:
    ab = team.get("team", {}).get("abbreviation", "?")
    for i in (team.get("injuries") or [])[:6]:
        print("INJ", ab, i.get("athlete", {}).get("displayName", "?"), i.get("status", "?"))
time.sleep(1.3)

# PM side: search gamma nfl jsons for dal-phi market
for f in ("gamma_nfl_recent.json", "gamma_nfl_events.json"):
    try:
        dd = json.load(open(f))
    except Exception:
        continue
    for e in dd:
        sl = e.get("slug", "")
        if "dal-phi" in sl and "prop" not in sl and "touchdown" not in sl:
            print("PM EV", e.get("title"), sl)
            for m in e.get("markets", [])[:3]:
                try:
                    px = json.loads(m.get("outcomePrices", "[]"))
                except Exception:
                    px = []
                print("   ", m.get("question", "?")[:60], m.get("outcomes", ""), px, "liq", m.get("liquidityNum", ""))
