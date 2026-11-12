#!/usr/bin/env python3
"""WP-P2a Phase A part 2: map clubs to Understat leagues, assemble final results JSON.

Reads the raw sweep (espn_sweep_events.json), maps every ESPN club name to an
Understat league key (EPL, La_liga, Serie_A, Bundesliga, Ligue_1) or nuisance,
writes ~/paper-sim/round31/raw/ucl_uel_results_3seasons.json (+ .sha256 sidecar)
with provenance, and evaluates gate G-A.

Usage:
  python3 assemble_results.py suggest     # print distinct team names + auto-suggested mapping
  python3 assemble_results.py build       # build final JSON + sha256 + G-A gate
"""
import hashlib
import json
import re
import sys
import unicodedata

RAW = "/home/ubuntu/paper-sim/round31/raw/espn_sweep_events.json"
UNDERSTAT = "/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json"
OUT = "/home/ubuntu/paper-sim/round31/raw/ucl_uel_results_3seasons.json"
OUT_SHA = OUT + ".sha256"

BIG5 = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]

# ESPN displayName -> {"league": <understat league key or "nuisance">, "understat_name": <name in xg file or null>}
# League assignment = which Big-5 league the club plays its domestic football in
# (2023-24 .. 2025-26 window). understat_name links to the club's entry in the
# Understat 2025/26 snapshot for alpha/delta multipliers (null = nuisance or fallback).
LEAGUE_MAP = {
    # --- EPL ---
    "Manchester City": ("EPL", "Manchester City"),
    "Arsenal": ("EPL", "Arsenal"),
    "Liverpool": ("EPL", "Liverpool"),
    "Manchester United": ("EPL", "Manchester United"),
    "Newcastle United": ("EPL", "Newcastle United"),
    "Newcastle": ("EPL", "Newcastle United"),
    "Aston Villa": ("EPL", "Aston Villa"),
    "Tottenham Hotspur": ("EPL", "Tottenham"),
    "West Ham United": ("EPL", "West Ham"),
    "Brighton and Hove Albion": ("EPL", "Brighton"),
    "Brighton & Hove Albion": ("EPL", "Brighton"),
    "Chelsea": ("EPL", "Chelsea"),
    "Crystal Palace": ("EPL", "Crystal Palace"),
    "Nottingham Forest": ("EPL", "Nottingham Forest"),
    # --- La_liga ---
    "Real Madrid": ("La_liga", "Real Madrid"),
    "Barcelona": ("La_liga", "Barcelona"),
    "Atletico Madrid": ("La_liga", "Atletico Madrid"),
    "Atlético Madrid": ("La_liga", "Atletico Madrid"),
    "Athletic Club": ("La_liga", "Athletic Club"),
    "Athletic Bilbao": ("La_liga", "Athletic Club"),
    "Real Sociedad": ("La_liga", "Real Sociedad"),
    "Real Betis": ("La_liga", "Real Betis"),
    "Villarreal": ("La_liga", "Villarreal"),
    "Girona": ("La_liga", "Girona"),
    "Sevilla": ("La_liga", "Sevilla"),
    "Valencia": ("La_liga", "Valencia"),
    "Celta Vigo": ("La_liga", "Celta Vigo"),
    "Rayo Vallecano": ("La_liga", "Rayo Vallecano"),
    "Getafe": ("La_liga", "Getafe"),
    "Osasuna": ("La_liga", "Osasuna"),
    "Las Palmas": ("La_liga", "Las Palmas"),
    # --- Serie_A ---
    "Inter Milan": ("Serie_A", "Inter"),
    "Inter": ("Serie_A", "Inter"),
    "Internazionale": ("Serie_A", "Inter"),
    "AC Milan": ("Serie_A", "AC Milan"),
    "Milan": ("Serie_A", "AC Milan"),
    "Juventus": ("Serie_A", "Juventus"),
    "Napoli": ("Serie_A", "Napoli"),
    "Atalanta": ("Serie_A", "Atalanta"),
    "Roma": ("Serie_A", "Roma"),
    "AS Roma": ("Serie_A", "Roma"),
    "Lazio": ("Serie_A", "Lazio"),
    "Fiorentina": ("Serie_A", "Fiorentina"),
    "Bologna": ("Serie_A", "Bologna"),
    "Torino": ("Serie_A", "Torino"),
    "Genoa": ("Serie_A", "Genoa"),
    "Monza": ("Serie_A", "Monza"),
    "Udinese": ("Serie_A", "Udinese"),
    "Como": ("Serie_A", "Como"),
    "Como 1907": ("Serie_A", "Como"),
    "Cagliari": ("Serie_A", "Cagliari"),
    "Lecce": ("Serie_A", "Lecce"),
    "Hellas Verona": ("Serie_A", "Verona"),
    "Verona": ("Serie_A", "Verona"),
    "Empoli": ("Serie_A", "Empoli"),
    "Parma": ("Serie_A", "Parma Calcio 1913"),
    "Sassuolo": ("Serie_A", "Sassuolo"),
    # --- Bundesliga ---
    "Bayern München": ("Bundesliga", "Bayern Munich"),
    "Bayern Munich": ("Bundesliga", "Bayern Munich"),
    "Borussia Dortmund": ("Bundesliga", "Borussia Dortmund"),
    "RB Leipzig": ("Bundesliga", "RasenBallsport Leipzig"),
    "Bayer Leverkusen": ("Bundesliga", "Bayer Leverkusen"),
    "Eintracht Frankfurt": ("Bundesliga", "Eintracht Frankfurt"),
    "VfB Stuttgart": ("Bundesliga", "VfB Stuttgart"),
    "Stuttgart": ("Bundesliga", "VfB Stuttgart"),
    "Borussia Mönchengladbach": ("Bundesliga", "Borussia M.Gladbach"),
    "Borussia Monchengladbach": ("Bundesliga", "Borussia M.Gladbach"),
    "SC Freiburg": ("Bundesliga", "Freiburg"),
    "Freiburg": ("Bundesliga", "Freiburg"),
    "TSG Hoffenheim": ("Bundesliga", "Hoffenheim"),
    "Hoffenheim": ("Bundesliga", "Hoffenheim"),
    "VfL Wolfsburg": ("Bundesliga", "Wolfsburg"),
    "Wolfsburg": ("Bundesliga", "Wolfsburg"),
    "Union Berlin": ("Bundesliga", "Union Berlin"),
    "1. FC Union Berlin": ("Bundesliga", "Union Berlin"),
    "Heidenheim": ("Bundesliga", "Heidenheim"),
    "1. FC Heidenheim": ("Bundesliga", "Heidenheim"),
    "FC St. Pauli": ("Bundesliga", "St. Pauli"),
    "St. Pauli": ("Bundesliga", "St. Pauli"),
    "Mainz": ("Bundesliga", "Mainz 05"),
    "1. FSV Mainz 05": ("Bundesliga", "Mainz 05"),
    "Werder Bremen": ("Bundesliga", "Werder Bremen"),
    "FC Augsburg": ("Bundesliga", "Augsburg"),
    "Augsburg": ("Bundesliga", "Augsburg"),
    "1. FC Köln": ("Bundesliga", "FC Cologne"),
    "FC Koln": ("Bundesliga", "FC Cologne"),
    # --- Ligue_1 ---
    "Paris Saint-Germain": ("Ligue_1", "Paris Saint Germain"),
    "Paris Saint Germain": ("Ligue_1", "Paris Saint Germain"),
    "PSG": ("Ligue_1", "Paris Saint Germain"),
    "AS Monaco": ("Ligue_1", "Monaco"),
    "Monaco": ("Ligue_1", "Monaco"),
    "Marseille": ("Ligue_1", "Marseille"),
    "Olympique Marseille": ("Ligue_1", "Marseille"),
    "Lille": ("Ligue_1", "Lille"),
    "LOSC Lille": ("Ligue_1", "Lille"),
    "Lyon": ("Ligue_1", "Lyon"),
    "Olympique Lyonnais": ("Ligue_1", "Lyon"),
    "Nice": ("Ligue_1", "Nice"),
    "OGC Nice": ("Ligue_1", "Nice"),
    "Lens": ("Ligue_1", "Lens"),
    "RC Lens": ("Ligue_1", "Lens"),
    "Brest": ("Ligue_1", "Brest"),
    "Stade Brestois": ("Ligue_1", "Brest"),
    "Stade Brestois 29": ("Ligue_1", "Brest"),
    "Stade Rennais": ("Ligue_1", "Rennes"),
    "Rennes": ("Ligue_1", "Rennes"),
    "Toulouse": ("Ligue_1", "Toulouse"),
    "Stade de Reims": ("Ligue_1", "Reims"),
    "Reims": ("Ligue_1", "Reims"),
    "Nantes": ("Ligue_1", "Nantes"),
    "Strasbourg": ("Ligue_1", "Strasbourg"),
    "RC Strasbourg": ("Ligue_1", "Strasbourg"),
    "Montpellier": ("Ligue_1", "Montpellier"),
    "Metz": ("Ligue_1", "Metz"),
    "Le Havre": ("Ligue_1", "Le Havre"),
    "Auxerre": ("Ligue_1", "Auxerre"),
    "Saint-Étienne": ("Ligue_1", "Saint-Etienne"),
    "AS Saint-Étienne": ("Ligue_1", "Saint-Etienne"),
    "Angers": ("Ligue_1", "Angers"),
    "Angers SCO": ("Ligue_1", "Angers"),
}
# Every other ESPN name -> nuisance (no alpha/delta from Understat).

# Expected completed match counts for gate G-A (documented official formats):
#   2023-24 full season:  UCL 96 GS + 29 KO = 125; UEL 96 GS + 45 KO = 141
#   2024-25 league phase: 36 teams x 8 rounds / 2 = 144 per competition
#   2025-26 league phase: 144 per competition (league phase complete by 2026-01-29)
EXPECTED = {
    ("2023-24", "UCL"): 125, ("2023-24", "UEL"): 141,
    ("2024-25", "UCL"): 144, ("2024-25", "UEL"): 144,
    ("2025-26", "UCL"): 144, ("2025-26", "UEL"): 144,
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]", "", s)


def understat_names():
    d = json.load(open(UNDERSTAT))
    names = {}
    for lg in BIG5:
        key = lg + "_2025"
        for t in d[key]["teams"].values():
            names.setdefault(norm(t["title"]), (lg, t["title"]))
    return names


def suggest():
    raw = json.load(open(RAW))
    counts = {}
    for e in raw["events"]:
        for side in ("home", "away"):
            n = e[side]["displayName"]
            counts[n] = counts.get(n, 0) + 1
    us = understat_names()
    print("distinct clubs:", len(counts))
    for n, c in sorted(counts.items(), key=lambda t: -t[1]):
        if n in LEAGUE_MAP:
            lg, un = LEAGUE_MAP[n]
            tag = "MAP " + lg
        elif norm(n) in us:
            lg, un = us[norm(n)]
            tag = "AUTO->" + lg + " " + un
        else:
            tag = "??"
        print(f"{c:4d}  {n!r:45s} {tag}")


def build():
    raw = json.load(open(RAW))
    us = understat_names()
    league_map = {}
    unmapped = {}
    matches = []
    for e in sorted(raw["events"], key=lambda x: (x["date"], x["event_id"])):
        hn, an = e["home"]["displayName"], e["away"]["displayName"]
        for n in (hn, an):
            if n in league_map:
                continue
            if n in LEAGUE_MAP:
                lg, un = LEAGUE_MAP[n]
            elif norm(n) in us:
                lg, un = us[norm(n)]
            else:
                lg, un = "nuisance", None
            league_map[n] = {"league": lg, "understat_name": un}
            if lg == "nuisance":
                unmapped[n] = unmapped.get(n, 0) + 1
        matches.append({
            "event_id": e["event_id"], "date": e["date"], "comp": e["comp"],
            "season_bucket": e["season_bucket"],
            "espn_season_slug": e.get("espn_season_slug"),
            "home_name": hn, "away_name": an,
            "home_league": league_map[hn]["league"], "away_league": league_map[an]["league"],
            "score_home": int(e["score_home"]), "score_away": int(e["score_away"]),
            "status": e["status"],
        })

    # per season/comp counts + G-A
    got = {}
    for m in matches:
        k = (m["season_bucket"], m["comp"])
        got[k] = got.get(k, 0) + 1
    sc = raw["status_counts"]
    gate = {}
    for k, exp in EXPECTED.items():
        ft = got.get(k, 0)
        # completed matches observed under non-FULL_TIME finish statuses
        # (extra time / penalty shootouts) count as recovered for G-A but
        # stay excluded from the fit dataset (STATUS_FULL_TIME filter).
        aet = sc.get(f"{k[1]}|{k[0]}|STATUS_FINAL_AET", 0)
        pen = sc.get(f"{k[1]}|{k[0]}|STATUS_FINAL_PEN", 0)
        rec = ft + aet + pen
        gate[f"{k[0]}|{k[1]}"] = {
            "fit_dataset_ft": ft, "also_aet": aet, "also_pen": pen,
            "recovered_completed": rec, "expected": exp, "ratio": round(rec / exp, 4),
            "passed_95pct": bool(rec / exp >= 0.95),
        }
    gate_passed = all(v["passed_95pct"] for v in gate.values())

    prov = {
        "source": "ESPN public site API scoreboard endpoint (day-by-day sweep; range requests rejected HTTP 400)",
        "endpoint_template": raw["endpoint_template"],
        "fetch_started_utc": raw["fetched_at_utc"],
        "windows": raw["windows"],
        "competitions": raw["comps"],
        "n_requests": raw.get("n_day_comp_cells", raw.get("n_requests")),
        "n_errors": raw["n_errors"],
        "status_filter": "STATUS_FULL_TIME only",
        "espn_status_counts_during_sweep": raw["status_counts"],
        "request_log": ("day-by-day GETs; the exact URL list is deterministically reconstructible from "
                        "endpoint_template + windows (one request per day per competition)"),
        "notes": [
            "2023-24 window covers the full competition incl. knockout rounds and final (through 2024-06-30).",
            "2024-25 and 2025-26 windows cover the league phase only (through Jan 31), per WP-P2a spec.",
            "Knockout matches decided after extra time carry the score including extra-time goals (ESPN scoreboard convention); penalty-shootout wins are not distinguishable in this endpoint.",
            "Club -> league mapping: curated alias table + normalised auto-match against Understat 2025/26 team names; everything else tagged nuisance.",
        ],
    }
    out = {
        "provenance": prov,
        "league_map": league_map,
        "nuisance_clubs": dict(sorted(unmapped.items(), key=lambda t: -t[1])),
        "counts": {f"{k[0]}|{k[1]}": v for k, v in sorted(got.items())},
        "gate_A": {"per_season": gate, "threshold": 0.95, "passed": bool(gate_passed)},
        "n_matches": len(matches),
        "matches": matches,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    h = hashlib.sha256(open(OUT, "rb").read()).hexdigest()
    with open(OUT_SHA, "w") as f:
        f.write(h + "  " + OUT.split("/")[-1] + "\n")
    print(json.dumps({"counts": out["counts"], "gate_A": gate, "gate_A_passed": gate_passed,
                      "n_clubs_mapped_big5": sum(1 for v in league_map.values() if v["league"] != "nuisance"),
                      "n_clubs_nuisance": len(unmapped)}, indent=1))
    print("SHA256", h)
    print("WROTE", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "suggest":
        suggest()
    else:
        build()
