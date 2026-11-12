#!/usr/bin/env python3
"""Build round44/mon_tue_candidates.json from round44/raw/mon_tue_scan.json
(r38 schema). Decision: ENTER NOTHING - zero modelable fixtures exist in the
window (the dispatch's "Nov-10/11 Championship midweek round" does not exist;
international break Nov 9-17, round 16 = Nov 21/22). PAPER ONLY - no orders,
no DB writes."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round44/raw/mon_tue_scan.json"
OUT = "/home/ubuntu/paper-sim/round44/mon_tue_candidates.json"

d = json.load(open(SCAN))
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

board = d["board_only"]
in_window = [b for b in board if not b["post_kickoff_at_scan"]
             and b["kickoff_utc"] <= "2026-11-10T23:59:59Z"]
post_kick = [b for b in board if b["post_kickoff_at_scan"]]
wed = [b for b in board if b["kickoff_utc"] >= "2026-11-11T00:00:00Z"]
N_ROWS = sum(len(b["rows"]) for b in board)
N_CLOB = sum(1 for b in board for r in b["rows"] if r.get("clob"))


def board_summary(b):
    best = None
    for r in b["rows"]:
        try:
            liq = float(r.get("liq_gamma") or 0)
        except Exception:
            liq = 0
        if best is None or liq > best[1]:
            best = (r, liq)
    return {
        "match": b["match"], "league": b["league"],
        "kickoff_utc": b["kickoff_utc"],
        "n_market_rows": len(b["rows"]),
        "top_market": {
            "id": best[0]["id"], "q": best[0]["q"],
            "outcomes": best[0]["outcomes"],
            "gamma_prices": best[0]["gamma_prices"],
            "liq_gamma": best[0]["liq_gamma"],
            "clob": best[0].get("clob")} if best else None,
    }


out = {
    "round": 44,
    "sub_scan": "soccer_44A_mon_tue",
    "scan": "soccer",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": d["window_utc"],
    "decision": (
        "ENTER NOTHING (0 candidates, $0 of the <=$400 budget): ZERO "
        "modelable fixtures exist in the entry window 2026-11-09T01:30Z.."
        "2026-11-10T23:59Z. The dispatch's expected main content - a Nov-10/11 "
        "Championship midweek round - DOES NOT EXIST: the November 2026 "
        "international break runs Nov 9-17; Championship round 15 completed "
        "Sat Nov-7 and round 16 is Sat Nov-21/Sun Nov-22 (verified "
        "independently by Gamma's 69 active efl-championship events - no "
        "gameStartTime before 2026-11-21; ESPN eng.2 scoreboard Nov 9/10/11 - "
        "zero fixtures; FotMob league 48 fixture list - round 16 kicks "
        "2026-11-21T12:30Z; and public fixture listings). No Monday Big-5 "
        "league games are scheduled this week either (no Ligue 1 Monday, no "
        "Serie A Monday, no La Liga Monday - ESPN shows only La Liga 2 on "
        "Monday). Window content is entirely outside the model universe: "
        "Liga MX (post-kick), Serie C, La Liga 2, FA Cup 1st round, National "
        "League N/S, Romanian/Norwegian/Paraguayan/Ecuadorian/Colombian/"
        "Bolivian leagues, Womens Champions League, and Copa del Rey (6 ties, "
        "all cross-tier Big-5-club-vs-minnow - MODEL-VOID per dispatch, "
        "board-only). Frozen gates never evaluated a single row (board_rows=0, "
        "matches=0); nothing passes = enter nothing."),
    "decision_rationale": (
        "111 unique Gamma soccer events enumerated over 2026-11-09T00:00Z.."
        "2026-11-11T23:59Z (17 sweeps: 2 date-window + 15 tag sweeps; "
        "date-window sweeps are decorative - Gamma ignores start_date_min/max, "
        "known since r39) -> 37 fixtures after grouping, ALL board-only. "
        "Zero fixtures in a modelable league (Big-5/Championship/Eredivisie), "
        "so soccer_model.fixture_variants was never invoked (matches=0) and "
        "the gate pipeline (evaluate_candidate / walk_book / under_risk_check "
        "/ check_cross_league_mw - all wired, all unexercised) produced no "
        "rows. The 6 Copa del Rey ties pair one rated Spanish league club "
        "(Alaves, Eibar, Leganes, Valencia + Segunda sides Amorebieta/"
        "Logrones/Jaen) against an unrated 3rd/4th-tier minnow in every tie - "
        "cross-tier model-void per frozen dispatch rule; their books are "
        "also entry-hostile (e.g. Anaitasuna ML 0.009/0.286 best bid/ask, "
        "Amorebieta ML 0.27/0.78, Mijas O7.5 half-empty book) with stale "
        "2026-10-28 question-date text. Womens CL sides are women's teams "
        "(name-collision hazard with men's snapshot titles documented below - "
        "never modeled: league is BOARD_ONLY and matches=0 proves it). "
        "EFL Trophy Tue/Wed exists on ESPN (17+2 fixtures) but has ZERO "
        "Gamma markets. La Liga 2 Monday: only Sabadell-RSociedad B is on "
        "Gamma (Las Palmas-Eldense not listed); Segunda is outside the model "
        "universe regardless. No held soccer positions (dispatch: all "
        "settled). Budget untouched."),
    "max_new_entries_usd": 400,
    "positions_used": 0,
    "this_ticket_usd": 0,
    "stake_per_position_usd": 250,
    "stake_mw_usd": 150,
    "mw_stake_usd": 150,
    "max_new_positions": 0,
    "bankroll_usd": None,
    "cash_usd": None,
    "weekend_budget_note": (
        "dispatch R44A: <=$400 total proposals; nothing passes = enter "
        "nothing (this scan: zero modelable fixtures -> zero proposals, $0 "
        "used)"),
    "open_positions_at_scan": 0,
    "open_positions": [],
    "open_positions_note": "no held soccer positions remain (all settled per dispatch)",
    "new_candidates": [],
    "killed_candidates": [],
    "near_miss_numeric_kills": [],
    "held_positions": None,
    "calendar_finding": {
        "headline": ("No Championship midweek round exists on Nov-10/11; "
                     "November 2026 international break Nov 9-17"),
        "evidence": [
            ("Gamma direct query: 69 active efl-championship events; "
             "gameStartTime values >= Nov-8 across their markets are only "
             "2026-11-21 12:30, 2026-11-21 15:00, 2026-11-22 12:00 (UTC)"),
            ("ESPN eng.2 scoreboard 20261109/10/11: zero Championship "
             "fixtures; Mon Nov-9 shows only La Liga 2 (Sabadell-RSociedad "
             "II, Las Palmas-Eldense); Tue Nov-10 shows EFL Trophy x17 + "
             "Copa del Rey x6; Wed Nov-11 EFL Trophy x2"),
            ("FotMob league 48 (Championship) fixtures: first unfinished "
             "kickoffs are round 16 on 2026-11-21T12:30Z/15:00Z (Millwall-"
             "QPR, Norwich-Cardiff, Southampton-Derby, ...) and 2026-11-22 "
             "(Burnley-Blackburn); round 17 starts 2026-11-24"),
            ("championship_20261108 snapshot meta: rounds 1-15 complete, "
             "180 matches, last date 2026-11-07 15:00 (the Sat Nov-7 round "
             "was round 15 - there is no round between 15 and 16)"),
            ("Public fixture listings corroborate the break: 2026-27 EFL "
             "season international break Nov 9-17, matchweek 16 on Sat "
             "Nov 21 2026"),
        ],
        "consequence": ("The dispatch's 'main enterable content' does not "
                        "exist; window has zero modelable fixtures; nothing "
                        "proposed"),
    },
    "board_summary": {
        "total_board_only_fixtures": len(board),
        "in_entry_window_pre_kick": len(in_window),
        "post_kickoff_at_scan": len(post_kick),
        "wednesday_outside_entry_window": len(wed),
        "fixtures": [board_summary(b) for b in board],
    },
    "xg_bases": {
        "championship": (
            "NEW PATH per dispatch: championship_20261108/"
            "xg_fotmob_championship.json (fresh through Sat Nov-7, 180 "
            "matches, 24 clubs x 15 rounds, rounds 1-15 complete; meta "
            "embedded in scan provenance) - loaded via fotmob."
            "load_fotmob_snapshot, UNUSED (no Championship fixture in "
            "window)"),
        "big5": (
            "understat_latest.json pointer -> round41/raw/"
            "xg_fotmob_big5_merged.json (pointer untouched, pointed_at "
            "2026-11-08T02:24:14Z): round25 Understat through Oct-31 + "
            "FotMob Nov-1..Nov-7; SUNDAY NOV-8 BIG-5 GAMES NOT MERGED "
            "(snapshot cut predates them). Sunday-participating clubs would "
            "be 1-round stale if modeled - runtime builder flags 57 clubs "
            "(Sunday-unmerged). FotMob Sunday backfill (merge41.py pattern, "
            "allowed per dispatch) NOT RUN: zero modelable fixtures, no "
            "modeled club affected; pointer never moved, no Block-2 "
            "re-point needed"),
        "eredivisie": (
            "round41/raw/xg_fotmob_eredivisie.json (103 matches through "
            "Sat Nov-7 20:00Z) - Sunday Nov-8 Eredivisie games likewise "
            "unmerged (stale flags report-only); no Eredivisie fixture in "
            "window"),
        "staleness": (
            "runtime builder: exact Sunday 2026-11-08 participant set from "
            "round43/raw/espn_fixtures_43e.json vs snapshot history dates -> "
            "57 clubs flagged 'played Sun 2026-11-08, result unmerged' "
            "(report-only; zero modeled fixtures); generic pre-Oct-30 "
            "missing-games fallback retained (0 additional flags)"),
    },
    "data_quality_flags": [
        ("DISPATCH-PREMISE MISS: no Nov-10/11 Championship round exists "
         "(international break Nov 9-17; round 16 = Nov 21/22). Triple-"
         "provider verified + web-corroborated. Future midweek scans should "
         "check the provider fixture calendar before assuming a round."),
        ("EFL Trophy Tue/Wed (17+2 ESPN fixtures incl. Leicester-Walsall, "
         "Bristol Rovers-Reading) has ZERO Gamma markets - not enterable "
         "on Polymarket at all this window."),
        ("Copa del Rey Gamma markets carry stale question-date text "
         "('Will X win on 2026-10-28?') while gameStartTime is 2026-11-10; "
         "books are extremely wide or one-sided (Anaitasuna ML 0.009/0.286, "
         "Amorebieta ML 0.27/0.78, Tavernes-Valencia Valencia 0.921/0.952) "
         "- board-only regardless (cross-tier model-void)."),
        ("WOMENS-SIDE NAME-COLLISION HAZARD (cosmetic, no modeling impact): "
         "4 Womens CL fixtures show coverage='modeled' in the fixtures table "
         "because women's-side names substring-resolve to MEN'S snapshot "
         "titles (Real Madrid CF Femenino->Real Madrid, Paris FC->Paris FC, "
         "FC Internazionale Milano->Inter, Manchester City WFC->Manchester "
         "City, FC Bayern Muenchen->Bayern Munich, OL Lyonnes->Lyon). The "
         "BOARD_ONLY league gate runs before any modeling (matches=0, "
         "board_rows=0); women's football is outside the men's-league model "
         "universe. A future scan with womens fixtures in a modelable-"
         "tagged league must add an explicit womens deny-list."),
        ("La Liga 2 Monday: Gamma lists only Sabadell-RSociedad B; ESPN "
         "also has Las Palmas-Eldense (not on Gamma). Segunda is outside "
         "the model universe either way."),
        ("DISPATCH-SLATE CROSSCHECK MATCHER ARTIFACT: 4 of 6 Copa ties "
         "report found_on_gamma=False in dispatch_slate_crosscheck because "
         "the matcher compares whole normalized name strings (single-word "
         "slate labels like 'Anaitasuna Alaves' never equal prefixed Gamma "
         "titles 'CD Anaitasuna'/'Deportivo Alaves'). The board fixtures "
         "list is authoritative: all 6 Copa ties ARE on Gamma (92 market "
         "rows each). Amorebieta-Logrones and Tavernes-Valencia matched "
         "only because one side normalizes to a single word."),
        ("Gamma date-window sweeps (start_date_min/max) return 1500-row "
         "generic lists (broken since r39); enumeration relies on the 15 "
         "tag sweeps + soccer tag sweep as in prior rounds."),
        ("Monday-night lower-tier boards (Kristiansund-Vlerenga, Cucuta "
         "questions) show stale question-date text ('win on 2026-11-07/"
         "2026-11-08') vs gameStartTime Nov-9/10 - same Polymarket "
         "question-date artifact class as Copa."),
        ("unparsed_questions: 0 (the frozen market-family parser never ran "
         "- no modeled fixture reached it; board-only rows are raw prices "
         "by design)."),
    ],
    "news_audit": {
        "candidates_searched": 0,
        "note": ("zero candidates -> zero per-candidate rotation/team-news "
                 "searches required; one focused corroboration search run "
                 "on the load-bearing calendar finding instead"),
        "calendar_corroboration": {
            "verdict": ("CONFIRMED: November 2026 international break Mon "
                        "Nov 9 - Tue Nov 17; Championship matchweek 16 "
                        "resumes Sat Nov 21 2026 (Millwall-QPR, Norwich-"
                        "Cardiff, Southampton-Derby, ...). No Championship "
                        "or Big-5 fixtures exist in the Nov 9-10 window."),
            "sources": [
                ("https://www.espn.com/soccer/schedule/_/league/eng.2 - "
                 "2026-27 Championship schedule (round 16: Nov 21, 2026)"),
                ("https://www.bbc.com/sport/football/championship/scores-"
                 "fixtures - EFL Championship fixtures (Nov 21-22 round)"),
                ("https://www.whufc.com/matches/fixtures - West Ham United "
                 "official fixture list (Sat 21 November 2026 vs "
                 "Portsmouth; West Ham are a Championship club in the "
                 "2026-27 snapshot)"),
            ],
        },
    },
    "provenance": {
        "library_commit": "1a2760bc",
        "selfcheck": "PASS 10/10 (re-run 2026-11-09T07:06Z pre-scan)",
        "raw_board": ("round44/raw/mon_tue_scan.json (%d board-only "
                      "fixtures, %d raw market rows with gamma prices, %d "
                      "rows with CLOB top-6 books; 0 modeled matches; 0 "
                      "gate-evaluated rows)" % (len(board), N_ROWS, N_CLOB)),
        "enumeration": ("round44/raw/enum44.py -> events_window_44.json "
                        "(111 unique soccer events, enumeration range "
                        "2026-11-09T00:00Z..2026-11-11T23:59Z) + "
                        "espn_fixtures_44.json (27 fixtures across 21 "
                        "league codes x 3 dates incl. Copa del Rey and EFL "
                        "Trophy probes)"),
        "scan_script": ("round44/raw/scan44.py = round43/raw/scan43a.py "
                        "patched (patch44.py, exact-replacement, 20 ops): "
                        "window Nov-9 01:30Z..Nov-10 23:59Z, round44 paths, "
                        "NEW championship_20261108 snapshot path, held/"
                        "kill sets emptied, dispatch slate = actual ESPN "
                        "Mon/Tue slate, board-only league set extended, "
                        "Copa cross-tier coverage label, r44 Sunday-"
                        "unmerged staleness builder, budget $400"),
        "gamma_verification": (
            "not applicable: zero candidates -> no /markets/{id} "
            "verification set (method remains one-by-one /markets/{id}; "
            "the Gamma ids= list param is broken since r39)"),
        "budget_note": "$0 of <=$400 proposed; no orders, no DB writes",
    },
}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("wrote", OUT)
print("decision:", out["decision"][:120], "...")
print("new_candidates:", len(out["new_candidates"]),
      "| killed:", len(out["killed_candidates"]),
      "| near-miss:", len(out["near_miss_numeric_kills"]),
      "| board fixtures:", len(board))
