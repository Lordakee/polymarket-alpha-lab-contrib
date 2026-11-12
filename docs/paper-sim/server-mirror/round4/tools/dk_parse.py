import json

E = json.load(open("/home/ubuntu/paper-sim/round4/raw/espn.json"))

def am_to_p(am):
    am = float(am)
    if am > 0: return 1.0 + am / 100.0
    return 1.0 + 100.0 / (-am)

def devig(p1, p2):
    s = p1 + p2
    return p1 / s, p2 / s

def show_games(keys, want_totals=True):
    for k in keys:
        if k not in E: continue
        print("==== %s" % k)
        for ev in E[k].get("events", []):
            comp = ev["competitions"][0]
            names = " vs ".join(c["team"]["abbreviation"] for c in comp["competitors"])
            for o in comp.get("odds", []):
                prov = (o.get("provider") or {}).get("name", "?")
                if prov != "DraftKings" and prov != "draftkings":
                    continue
                det = o.get("details") or ""
                ou = o.get("overUnder") or ""
                ov = o.get("overOdds"); un = o.get("underOdds")
                ho = o.get("homeTeamOdds") or {}; ao = o.get("awayTeamOdds") or {}
                ml_h = ho.get("moneyLine"); ml_a = ao.get("moneyLine")
                spr = ho.get("spreadOdds"); aspr = ao.get("spreadOdds"); hline = ho.get("spread"); aline = ao.get("spread")
                line2 = []
                if ov is not None and un is not None:
                    po, pu = devig(am_to_p(ov), am_to_p(un))
                    line2.append("O/U %s: O %s(%d) U %s(%d) -> devig O %.3f" % (ou, ov, po * 100, un, pu * 100, po))
                if ml_h and ml_a:
                    ph, pa = devig(am_to_p(ml_h), am_to_p(ml_a))
                    line2.append("ML %s/%s -> devig H %.3f A %.3f" % (ml_h, ml_a, ph, pa))
                if hline is not None and spr:
                    ph2, pa2 = devig(am_to_p(spr), am_to_p(aspr))
                    line2.append("SPR %s %s / %s %s -> devig Hcover %.3f" % (hline, spr, aline, aspr, ph2))
                print("  %-28s %-14s %s" % (names, det, " | ".join(line2)))

print("########## SOCCER (DK) ##########")
show_games(["ucl_1014", "epl_1017", "epl_1018", "epl_1019", "lal_1017", "lal_1018", "sea_1017", "bun_1017"])
print()
print("########## NFL WEEK 6 (DK) ##########")
show_games(["nfl_1015", "nfl_1016", "nfl_1018", "nfl_1019"])
print()
print("########## NHL (DK) ##########")
show_games(["nhl_1014", "nhl_1015"])
print()
print("########## MLB (DK) ##########")
show_games(["mlb_1014"])
