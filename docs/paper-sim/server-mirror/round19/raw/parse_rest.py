import json, urllib.request, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

# NFL week 7 non-Sunday games (Thu/Fri/Sat)
for d in ("20261022", "20261023", "20261024"):
    try:
        d2 = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=" + d)
        for e in d2.get("events", []):
            print("NFL THUSAT:", d, e.get("shortName"), e.get("status", {}).get("type", {}).get("shortDetail", ""),
                  " | ".join(c.get("team", {}).get("abbreviation", "") + " " + str(c.get("score", "")) + ("*" if c.get("winner") else "") for c in e["competitions"][0]["competitors"]))
    except Exception as ex:
        print("ERR", d, ex)
    time.sleep(1.2)

# NFL week 8 full board via week param
for wk in ("8",):
    try:
        d2 = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?seasonType=2&weeks=" + wk)
        json.dump(d2, open("espn_nfl_wk8.json", "w"))
        evs = d2.get("events", [])
        print("NFL WK8 count:", len(evs))
        for e in evs:
            odds = e.get("odds", [])
            od = ""
            if odds:
                o = odds[0]
                od = " | odds " + str(o.get("details", "")) + " O/U " + str(o.get("overUnder", ""))
            print("NFL WK8:", e.get("shortName"), e.get("date"), od)
    except Exception as ex:
        print("ERR wk8", ex)
    time.sleep(1.2)

# POR record + recent schedule
try:
    d2 = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/22/schedule")
    t = d2.get("team", {})
    print("POR record:", t.get("recordSummary"), "| streak:", t.get("form", ""), t.get("streak"))
    for e in d2.get("events", []):
        print("POR SCHED:", e.get("date"), e.get("name"), e.get("status", {}).get("type", {}).get("shortDetail", ""))
except Exception as ex:
    print("ERR por", ex)
