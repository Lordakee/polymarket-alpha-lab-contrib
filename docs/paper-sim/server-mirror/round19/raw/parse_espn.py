import json, sys

def load(f):
    try:
        return json.load(open(f))
    except Exception as e:
        return {"_err": str(e)}

def comp_str(c):
    t = c.get("team", {})
    ab = t.get("abbreviation", "?")
    s = c.get("score", "")
    lo = c.get("linescores") or []
    ls = "/".join(str(x.get("value", "-")) for x in lo)
    w = "*" if c.get("winner") else ""
    base = f"{ab} {s}{w}"
    if ls:
        base += f" [{ls}]"
    return base

def leaders(comps):
    out = []
    for c in comps.get("competitors", []):
        for ld in (c.get("leaders") or []):
            nm = ld.get("name", "")
            if nm not in ("passing", "rushing", "receiving", "batting", "pitching"):
                continue
            for a in (ld.get("leaders") or [])[:1]:
                ath = a.get("athlete", {}).get("displayName", "?")
                stat = a.get("displayValue", "")
                out.append(f"{c.get('team',{}).get('abbreviation','?')} {nm}: {ath} {stat}")
    return out

jobs = [
    ("espn_nfl_20261025.json", "NFL SUN OCT25"),
    ("espn_nfl_20261026.json", "NFL MON OCT26"),
    ("espn_nfl_20261027.json", "NFL OCT27"),
    ("espn_mlb_20261023.json", "MLB OCT23"),
    ("espn_mlb_20261024.json", "MLB OCT24"),
    ("espn_mlb_20261026.json", "MLB OCT26"),
    ("espn_mlb_20261027.json", "MLB OCT27"),
    ("espn_nba_20261023.json", "NBA OCT23"),
    ("espn_nba_20261024.json", "NBA OCT24"),
    ("espn_nba_20261025.json", "NBA OCT25"),
    ("espn_nba_20261026.json", "NBA OCT26 MON"),
    ("espn_nba_20261027.json", "NBA OCT27 TUE"),
]

for f, label in jobs:
    d = load(f)
    evs = d.get("events", [])
    print(f"=== {label} ({len(evs)} events) ===")
    for e in evs:
        comps = e.get("competitions", [])
        if not comps:
            continue
        cp = comps[0]
        cs = cp.get("competitors", [])
        st = e.get("status", {}).get("type", {}).get("description", "?")
        det = e.get("status", {}).get("type", {}).get("detail", "")
        od = e.get("odds", [])
        odstr = ""
        if od:
            o = od[0]
            odstr = f" | odds: {o.get('details','')} O/U {o.get('overUnder','')}"
        print(f"{e.get('name','?')} | {st} | {det}{odstr}")
        print("   " + " | ".join(comp_str(c) + (" H" if c.get("homeAway") == "home" else " A") for c in cs))
        for l in leaders(cp)[:6]:
            print("   LDR " + l)
    print()
