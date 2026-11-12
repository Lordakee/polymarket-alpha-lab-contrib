import json, urllib.request, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

games = []
for f in ("espn_nba_20261026.json", "espn_nba_20261027.json"):
    d = json.load(open(f))
    for e in d.get("events", []):
        games.append((f[-13:-5], e["id"], e.get("shortName", "?")))

print("games:", len(games))
for day, eid, nm in games:
    try:
        s = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=" + eid)
    except Exception as ex:
        print(day, nm, "ERR", ex)
        time.sleep(1.2)
        continue
    pc = s.get("pickcenter", [])
    line = ""
    for p in pc:
        prov = p.get("provider", {}).get("name", "?")
        ml = p.get("moneyline", {})
        ou = p.get("overUnder")
        spr = p.get("spread")
        if prov in ("ESPN BET", "Caesars", "DraftKings", "FanDuel"):
            line = f"{prov} ML a/h: {ml.get('away', '')}/{ml.get('home', '')} spr={spr} ou={ou}"
            break
    if not line and pc:
        p = pc[0]
        ml = p.get("moneyline", {})
        line = f"{p.get('provider',{}).get('name','?')} ML a/h: {ml.get('away','')}/{ml.get('home','')} ou={p.get('overUnder')}"
    rostr = s.get("rosters", [])
    inj = s.get("injuries", [])
    inj_str = ""
    if inj:
        parts = []
        for team in inj[:2]:
            ab = team.get("team", {}).get("abbreviation", "?")
            for i in (team.get("injuries") or [])[:5]:
                nm2 = i.get("athlete", {}).get("displayName", "?")
                parts.append(f"{ab}:{nm2}:{i.get('status','?')}")
        inj_str = " INJ[" + "; ".join(parts) + "]"
    print(day, nm, "|", line, inj_str)
    time.sleep(1.2)
