#!/usr/bin/env python3
"""Build round44/weekend_early_candidates.json (r38 schema + early-entry
fields) from round44/raw/weekend_early_scan.json.

DECISION: PROPOSE ENTER 0 of <=$400. The dispatch window (Nov 13-15) is a
FIFA international-break weekend: zero in-scope league fixtures, zero
Polymarket listings, gates not evaluable. r38 schema fields preserved;
new_candidates empty; watch plan + recheck conditions recorded.
PAPER ONLY - no orders, no DB writes."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round44/raw/weekend_early_scan.json"
OUT = "/home/ubuntu/paper-sim/round44/weekend_early_candidates.json"

d = json.load(open(SCAN))
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

out = {
    "round": 44,
    "scan": "soccer-weekend-early",
    "sub_scan": "weekend_early_44C",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": d["window_utc"],
    "early_entry": True,
    "decision": (
        "NO ENTRY - the dispatch window has no in-scope league slate. "
        "2026-11-14/15 is a FIFA international-break weekend: Gamma lists "
        "zero events for EPL/Championship/Bundesliga/LaLiga/SerieA/Ligue1/"
        "Eredivisie beyond Mon 2026-11-09 (per-tag sweeps complete, zero "
        "undated stubs); the Nov 13-15 Gamma window holds only UEFA "
        "Nations League (22 events), friendlies (3) and non-European/"
        "lower-division leagues; ESPN 20261113-15 scoreboards are empty; "
        "FotMob shows all 7 leagues complete through Sun Nov-8 with no "
        "scheduled matches after. Zero fixtures -> zero markets -> frozen "
        "gates not evaluable -> 0 candidates. Early budget untouched: "
        "$0 of <=$400 proposed."),
    "decision_rationale": (
        "ROUND-44C asked for T-5/6d early prices on next weekend's league "
        "slate (EPL/LaLiga/SerieA/Bundesliga/Ligue1 full families; "
        "Eredivisie+Championship totals-only). Enumeration (enum44c.py, "
        "2026-11-09T07:08Z + live horizon re-check 07:25Z + undated-stub "
        "closure check) found the Gamma listing horizon for all 7 league "
        "tags ends at Mon 2026-11-09 (this round's Monday completions: "
        "e.g. Juventus-Venezia, Marseille-Le Mans, Getafe-Atletico, Hull-"
        "Brighton, Burnley-Blackburn, Feyenoord-Excelsior). Nothing is "
        "listed for Nov 13-15 in scope; the window's 262 soccer events "
        "are all break competitions (Nations League/friendlies) or "
        "leagues outside the break (Brazil, J2, Liga MX, Eerste Divisie, "
        "Serie C, EL1/EL2, WSL, ...). Cross-checks: ESPN scoreboards for "
        "20261113/14/15 return zero fixtures for all 11 league codes; "
        "fresh FotMob /api/data/leagues fetches for all 7 leagues return "
        "finished matches only (EPL 100, Championship 180, LaLiga 120, "
        "SerieA 110, Bundesliga 81, Ligue1 90, Eredivisie 108 - all "
        "complete through Sun Nov-8, zero scheduled beyond). Gamma "
        "date-window params are non-functional in this environment "
        "(r43 enum43.log shows the same symptom), so all conclusions rest "
        "on complete per-tag sweeps. Papersim selfcheck re-run this "
        "session: PASS 10/10. xG bases remain loaded/wired (Big-5 pointer "
        "unchanged, Championship snapshot championship_20261108, "
        "Eredivisie r39/r41 identical sha) but there is nothing to model."),
    "max_new_positions": 0,
    "positions_used": 0,
    "stake_per_position_usd": 250,
    "mw_stake_usd": 150,
    "budget": {
        "max_early_entry_proposals_usd": 400,
        "proposed_usd": 0,
        "note": ("nothing listed in scope; the following week retains its "
                 "own fresh-scan budget per dispatch")},
    "staleness_flags": {
        "snapshot_fresh_through": "2026-11-07 (Sat), all 7 leagues",
        "unmerged_results": (
            "Sun 2026-11-08 and Mon 2026-11-09 results are NOT merged "
            "into the xG bases (fresh FotMob EPL finished=100 vs snapshot "
            "95; SerieA 110 vs 105; Eredivisie 108 vs 103; Bundesliga 81 "
            "vs 78; Ligue1 90 vs 84; LaLiga 120 vs 115; Championship's "
            "Mon Nov-9 completions listed on Gamma). STALE-XG Sunday-club "
            "flagging is moot with no candidates; the model-refresh leg "
            "below re-arms it at the next real scan"),
    },
    "recheck_conditions": [
        "RE-LISTING WATCH: re-enumerate Gamma (tag sweeps epl/"
        "premier-league/efl-championship/bundesliga/la-liga/sea/ligue-1/"
        "ere) when the listing horizon extends past 2026-11-19 - league "
        "listings in this environment appear only a few days ahead "
        "(r38 precedent: full weekend slate live at T-53h)",
        "IF any in-scope listing appears for Nov 13-15 (not expected - "
        "break weekend): run the full frozen-gate scan (net>=+5c fee-"
        "aware, worst>=+4c, var<=6c, liq>=$5k, $250 fill, MW $150 "
        "deprioritized, one per fixture, spreads flagged-only, "
        "Championship/Eredivisie totals-only) + per-candidate T-24h "
        "recheck: drop if ask moves >=3c against, key absences emerge, "
        "or model-refresh flips the edge",
        "MODEL-REFRESH LEG (mandatory before ANY next entry): merge Nov-8 "
        "and Nov-9 league results into the xG bases (Big-5 pointer merge "
        "+ Championship/Eredivisie refresh, same pipeline as "
        "championship_20261108), then re-derive lambdas; post-break "
        "fixtures also need the Nov-10..17 international results excluded "
        "from league xG (they are league-snapshot-external by "
        "construction)",
        "SCOPE GUARD: UEFA Nations League / friendlies now listed in the "
        "window are OUT OF SCOPE for ROUND-44C (league-slate dispatch; "
        "national-team markets have no sanctioned model base here) - "
        "reported in raw only, no entry",
    ],
    "new_candidates": [],
    "raw_scan": SCAN,
    "provenance": {
        "library_commit": "1a2760bc",
        "selfcheck": d["provenance"]["selfcheck"],
        "enum_artifacts": d["artifacts"],
    },
}
json.dump(out, open(OUT, "w"), indent=1)
print("saved", OUT)
print("decision:", out["decision"][:120])
