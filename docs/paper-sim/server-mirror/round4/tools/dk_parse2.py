import json

E = json.load(open("/home/ubuntu/paper-sim/round4/raw/espn.json"))

def am_to_p(am):
    am = float(am)
    if am > 0: return 1.0 + am / 100.0
    return 1.0 + 100.0 / (-am)

def devig(p1, p2):
    s = p1 + p2
    return p1 / s, p2 / s

def close_of(node):
    # node like {"open": {...}, "close": {...}} or {"close": {...}}
    c = node.get("close") or node.get("open") or {}
    return c.get("odds"), (c.get("line") or "").replace("o", "").replace("u", "")

def show(keys):
    for k in keys:
        if k not in E: continue
        print("==== %s" % k)
        for ev in E[k].get("events", []):
            comp = ev["competitions"][0]
            names = " vs ".join(c["team"]["abbreviation"] for c in comp["competitors"])
            for o in comp.get("odds", []):
                prov = (o.get("provider") or {}).get("name", "?")
                if "draft" not in prov.lower(): continue
                tot = o.get("total") or {}
                ml = o.get("moneyline") or {}
                ps = o.get("pointSpread") or {}
                parts = []
                try:
                    ov_odds, ov_line = close_of(tot["over"])
                    un_odds, un_line = close_of(tot["under"])
                    if ov_odds and un_odds:
                        po, pu = devig(am_to_p(ov_odds), am_to_p(un_odds))
                        parts.append("O/U %s: O %s/U %s -> devig P(over) %.3f" % (ov_line, ov_odds, un_odds, po))
                except Exception:
                    pass
                try:
                    h = ml["home"]; a = ml["away"]
                    ho, _ = close_of(h); ao, _ = close_of(a)
                    if ho and ao:
                        ph, pa = devig(am_to_p(ho), am_to_p(ao))
                        parts.append("ML %s/%s devH %.3f devA %.3f" % (ho, ao, ph, pa))
                except Exception:
                    pass
                try:
                    hs = ps["home"]; as_ = ps["away"]
                    ho2, hl = close_of(hs); ao2, al = close_of(as_)
                    if ho2 and ao2:
                        phc, pac = devig(am_to_p(ho2), am_to_p(ao2))
                        parts.append("SPR %s %s | %s %s -> Hcover %.3f" % (hl, ho2, al, ao2, phc))
                except Exception:
                    pass
                print("  %-26s %s" % (names, " | ".join(parts)))

print("########## SOCCER DK (close) ##########")
show(["ucl_1014", "epl_1017", "epl_1018", "epl_1019", "lal_1017", "lal_1018", "sea_1017", "bun_1017"])
print()
print("########## NFL DK (close) ##########")
show(["nfl_1015", "nfl_1016", "nfl_1018", "nfl_1019"])
print()
print("########## NHL DK (close) ##########")
show(["nhl_1014", "nhl_1015"])
print()
print("########## MLB DK (close) ##########")
show(["mlb_1014"])
