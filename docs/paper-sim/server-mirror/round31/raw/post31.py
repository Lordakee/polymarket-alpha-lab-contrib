"""Round-31 post-processing: fix canon false-positive (AZ->Lazio), relabel
Getafe-Brighton as UECL, merge fragmented matches/prices_only groups, print
final fixture inventory + Championship prices. Writes corrected
soccer_scan.json in place (backup kept)."""
import json
import re
from collections import defaultdict

P = "/home/ubuntu/paper-sim/round31/raw/soccer_scan.json"
d = json.load(open(P))
json.dump(d, open(P + ".bak", "w"), indent=1)

CANON_FIX = [
    {"match_contains": "AZ vs. Juventus",
     "reason": ("canon false-positive corrected: 'AZ' (AZ Alkmaar, Eredivisie) "
                "substring-matched Big-5 title 'Lazio' and was modeled as a "
                "Lazio-Juventus Serie A DOMESTIC derby. AZ Alkmaar is outside "
                "the Understat Big-5 universe -> fixture is NO-DATA "
                "not-modelable; all its board rows and match entries are "
                "void and removed in this post-pass.")},
]

# 1) remove invalid fixtures from board + matches; annotate fixtures list
removed_board = 0
for fix in CANON_FIX:
    before = len(d["board"])
    d["board"] = [r for r in d["board"] if fix["match_contains"] not in r["match"]]
    removed_board = before - len(d["board"])
    before = len(d["matches"])
    d["matches"] = [m for m in d["matches"]
                    if fix["match_contains"] not in m["match"]]
    for f in d["fixtures"]:
        if fix["match_contains"] in f["title"]:
            f["modelable"] = False
            f["modelability_class"] = "no-data (canon false-positive corrected post-scan)"
            f["model_note"] = fix["reason"]
            f["understat_home"] = None
            f["understat_away"] = None
            f["home_league"] = None
            f["away_league"] = None
d["board_rows"] = len(d["board"])
d["canon_corrections"] = CANON_FIX
d["removed_board_rows"] = removed_board

# 2) relabel Getafe-Brighton comp (tag europa-conference-league -> UECL)
for f in d["fixtures"]:
    if "europa-conference-league" in (f.get("tags") or []):
        f["comp"] = "UECL"
for r in d["board"]:
    if r.get("comp") == "CROSS(other)" and "Getafe" in r["match"]:
        r["comp"] = "UECL"
for m in d["matches"]:
    if m.get("comp") == "CROSS(other)" and "Getafe" in m["match"]:
        m["comp"] = "UECL"

# 3) merge matches fragments by (fixture_key, kickoff_utc)
mm = {}
for m in d["matches"]:
    k = (m["fixture_key"], m["kickoff_utc"])
    if k not in mm:
        mm[k] = m
    else:
        ids = set(mm[k]["gamma_event_ids"]) | set(m["gamma_event_ids"])
        mm[k]["gamma_event_ids"] = sorted(ids)
d["matches"] = [mm[k] for k in sorted(mm, key=lambda x: mm[x]["kickoff_utc"])]

# 4) merge prices_only fragments by (base match, kickoff, comp)
def base_title(t):
    return re.split(r"\s+-\s+", t, maxsplit=1)[0]

pp = {}
for p in d["prices_only"]:
    bt = base_title(p["match"])
    k = (bt, p["kickoff_utc"], p["comp"])
    if k not in pp:
        pp[k] = {"match": bt, "comp": p["comp"], "kickoff_utc": p["kickoff_utc"],
                 "section": p["section"], "modelability": p["modelability"],
                 "rows": []}
    seen_ids = {(r["id"], r["side"]) for r in pp[k]["rows"]}
    for r in p["rows"]:
        if (r["id"], r["side"]) not in seen_ids:
            pp[k]["rows"].append(r)
            seen_ids.add((r["id"], r["side"]))
d["prices_only"] = [pp[k] for k in sorted(pp, key=lambda x: pp[x]["kickoff_utc"])]

json.dump(d, open(P, "w"), indent=1)

# ---- final inventory (fixture level) ----
inv = {}
for f in d["fixtures"]:
    bt = base_title(f["title"])
    k = (f["kickoff_utc"], bt)
    if k not in inv or f["modelable"]:
        inv[k] = f
print("FINAL fixture inventory: %d unique fixtures" % len(inv))
for k in sorted(inv, key=lambda x: x[0]):
    f = inv[k]
    print("%-6s %-10s %-42s %-9s %s" % (
        f["kickoff_utc"][5:16], f["comp"], k[1][:42],
        f["modelability_class"][:9],
        "PM-event" if f["n_markets"] else ""))
print()
print("matches (modelable, merged):", len(d["matches"]),
      "| prices-only fixtures (merged):", len(d["prices_only"]),
      "| board rows:", d["board_rows"],
      "| removed (AZ void):", removed_board)
print()
# Championship prices summary
print("CHAMPIONSHIP (eng.2) PRICES ONLY:")
for p in d["prices_only"]:
    if p["comp"] == "ENG2":
        print("--", p["match"], p["kickoff_utc"])
        main = [r for r in p["rows"] if r["kind"] in ("ml", "total", "btts")
                or (r["kind"] == "team_total" and r["line"] in (0.5, 1.5))]
        for r in sorted(main, key=lambda r: (r["kind"], str(r["line"]), r["side"]))[:16]:
            print("   %-11s %-6s %-5s bid=%s ask=%s askVWAP250=%s liq=$%s" % (
                r["kind"], r["side"], r["line"], r["bid"], r["ask"],
                r["ask_vwap250"], int(r["liq_gamma"] or 0)))
# numeric passers after fix
pr = [r for r in d["board"] if r["passed_numeric"]]
print()
print("numeric passers after corrections:", len(pr))
for r in pr:
    print("  ", r["match"], r["kind"], r["side"], r["line"],
          ";".join(r["entry_flags"])[:80])
