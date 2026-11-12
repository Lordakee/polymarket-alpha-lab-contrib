import json, urllib.request, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

nfl = json.load(open("espn_nfl_20261025.json"))
nba = json.load(open("espn_nba_20261023.json"))

nfl_ev = [e["id"] for e in nfl["events"] if "Bengals" in e["name"]]
nba_ev = [e["id"] for e in nba["events"] if "Trail Blazers" in e["name"]]
por_id = None
for e in nba["events"]:
    if "Trail Blazers" in e["name"]:
        for c in e["competitions"][0]["competitors"]:
            if "Trail Blazers" in c["team"]["displayName"]:
                por_id = c["team"]["id"]
print("NFL CIN@BAL event:", nfl_ev, "| NBA POR@SAC event:", nba_ev, "| POR team id:", por_id)

# 1) NFL CIN@BAL summary - Lamar check
if nfl_ev:
    s = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=" + nfl_ev[0])
    names = ("Lamar Jackson", "Joe Burrow", "Tyler Huntley", "Josh Johnson", " Malik Willis", "Malik Willis", "Zach Wilson")
    for tm in s.get("boxscore", {}).get("players", []):
        ab = tm.get("team", {}).get("abbreviation", "?")
        for stat in tm.get("statistics", []):
            for ath in stat.get("athletes", []):
                an = ath.get("athlete", {}).get("displayName", "")
                if an in names:
                    print("NFLBOX", ab, an, "dnp=", ath.get("didNotPlay"), "stats=", ath.get("stats"))
    for a in (s.get("news", {}) or {}).get("articles", [])[:3]:
        print("NFLNEWS:", a.get("headline"))
    gi = s.get("gameInfo", {})
    print("gameInfo availability:", json.dumps(gi.get("attendance", ""))[:80])
time.sleep(1.2)

# 2) NBA POR@SAC summary - Ja/Dame logs
if nba_ev:
    s = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=" + nba_ev[0])
    targets = ("Ja Morant", "Damian Lillard", "Scoot Henderson", "Shaedon Sharpe")
    hdr = None
    for tm in s.get("boxscore", {}).get("players", []):
        ab = tm.get("team", {}).get("abbreviation", "?")
        for stat in tm.get("statistics", []):
            if hdr is None and stat.get("labels"):
                hdr = stat["labels"]
                print("NBALBL", hdr)
            for ath in stat.get("athletes", []):
                an = ath.get("athlete", {}).get("displayName", "")
                if an in targets:
                    print("NBABOX", ab, an, "DNP=", ath.get("didNotPlay"), ath.get("status"), "stats=", ath.get("stats"))
    for a in (s.get("news", {}) or {}).get("articles", [])[:3]:
        print("NBANEWS:", a.get("headline"))
time.sleep(1.2)

# 3) NBA Wed Oct 28 scoreboard
d = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261028")
json.dump(d, open("espn_nba_20261028.json", "w"))
for e in d.get("events", []):
    odds = e.get("odds", [])
    od = ""
    if odds:
        od = " | odds " + str(odds[0].get("details", "")) + " O/U " + str(odds[0].get("overUnder", ""))
    print("NBA WED:", e.get("shortName"), e.get("status", {}).get("type", {}).get("detail", ""), od)
print("NBA WED count:", len(d.get("events", [])))
time.sleep(1.2)

# 4) MLB Oct 28 (potential G5)
d = get("https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=20261028")
json.dump(d, open("espn_mlb_20261028.json", "w"))
for e in d.get("events", []):
    print("MLB OCT28:", e.get("shortName"), e.get("status", {}).get("type", {}).get("detail", ""))
print("MLB OCT28 count:", len(d.get("events", [])))
time.sleep(1.2)

# 5) NFL full week 7 (Thu-Sun range catch) + week 8 early
d = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261022-20261024")
for e in d.get("events", []):
    print("NFL THUSAT:", e.get("shortName"), e.get("status", {}).get("type", {}).get("detail", ""),
          " | ".join(c.get("team", {}).get("abbreviation", "") + " " + str(c.get("score", "")) + ("*" if c.get("winner") else "") for c in e["competitions"][0]["competitors"]))
time.sleep(1.2)
d = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261029-20261102")
json.dump(d, open("espn_nfl_wk8.json", "w"))
n8 = 0
for e in d.get("events", []):
    n8 += 1
    odds = e.get("odds", [])
    od = ""
    if odds:
        od = " | odds " + str(odds[0].get("details", "")) + " O/U " + str(odds[0].get("overUnder", ""))
    print("NFL WK8:", e.get("shortName"), e.get("date"), e.get("status", {}).get("type", {}).get("detail", ""), od)
print("NFL WK8 count:", n8)
time.sleep(1.2)

# 6) POR season record via schedule
if por_id:
    d = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/" + por_id + "/schedule")
    rec = d.get("team", {}).get("recordSummary", "?")
    print("POR recordSummary:", rec, "| streak:", d.get("team", {}).get("form", ""), d.get("team", {}).get("streak", ""))
    for e in d.get("events", [])[:10]:
        print("POR SCHED:", e.get("date"), e.get("name"), e.get("status", {}).get("type", {}).get("shortDetail", ""))
