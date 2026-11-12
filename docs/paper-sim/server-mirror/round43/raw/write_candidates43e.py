#!/usr/bin/env python3
"""Build round43/euro_night_candidates.json from round43/raw/euro_night_scan.json
+ euro_night_verify.json (r38 schema). Decision: PROPOSE ENTER 1 (coordinator
arbitrates) - Lens-Marseille draw NO $150 @0.74, the sole numeric passer,
news-concordant. PAPER ONLY - no orders, no DB writes."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round43/raw/euro_night_scan.json"
VERIF = "/home/ubuntu/paper-sim/round43/raw/euro_night_verify.json"
ESPN43E = "/home/ubuntu/paper-sim/round43/raw/espn_fixtures_43e.json"
OUT = "/home/ubuntu/paper-sim/round43/euro_night_candidates.json"

d = json.load(open(SCAN))
board = d["board"]
verif = {v["id"]: v for v in json.load(open(VERIF))}


def gate_row(r):
    fails = [k for k, v in (r["checks"]).items() if not v and k != "news_concordant"]
    return {
        "market_id": r["id"], "market_question": r["q"], "kind": r["kind"],
        "side": r["side"], "line": r.get("line"), "team_side": r.get("team_side"),
        "kickoff_utc": r.get("kickoff_utc") or r.get("kick"),
        "hours_to_kick_at_scan": r.get("hours_to_kick_at_scan"),
        "net_edge_haircut_c": round(100 * (r["exec_edge_haircut"] or 0), 2),
        "gross_edge_c": round(100 * (r["exec_edge_gross"] or 0), 2),
        "worst_variant_edge_c": round(100 * (r["worst_variant_edge"]
                                             if r["worst_variant_edge"] is not None else -9), 2),
        "var_spread_c": round(100 * (r["var_spread"] or 0), 2),
        "p_med": r["p_med"], "p_min": r["p_min"], "p_max": r["p_max"],
        "entry_ask_vwap250": r["exec_ask_vwap250"], "fill_250": r["fill_250"],
        "liq_gamma": round(r["liq_gamma"], 0),
        "depth_2c_shares": r.get("depth_2c"),
        "exit_bid": r.get("exit_bid"),
        "policy": r.get("policy"),
        "failed_checks": fails,
        "gamma_verified": (
            {"question": verif[r["id"]]["question"],
             "closed": verif[r["id"]]["closed"],
             "gameStartTime": verif[r["id"]]["gameStartTime"],
             "endDate": verif[r["id"]]["endDate"]}
            if r["id"] in verif else "not in verify set"),
    }


def row_by(mid):
    for r in board:
        if r["id"] == str(mid):
            return r
    raise SystemExit("row not found: %s" % mid)


passer = row_by(6237097)
lam = next(m for m in d["matches"] if "Lens" in m["match"])
v = verif["6237097"]

entry = {
    "rank": 1,
    "id": 6237097,
    "match": passer["match"],
    "fixture_key": "olympiquemarseille-racingclublens",
    "comp": "Ligue_1",
    "kickoff_utc": passer["kickoff_utc"],
    "market": "%s (id 6237097)" % passer["q"],
    "side_bought": ("NO (match does NOT end in a draw - Lens win or "
                    "Marseille win)"),
    "kind": "ml",
    "policy": "ELIGIBLE-DEPRIORITIZED (domestic match_winner family, $150)",
    "entry_ask_vwap": passer["exec_ask_vwap250"],
    "best_bid_at_scan": passer["book_best_bid"],
    "stake_usd": 150,
    "shares": round(150 / passer["exec_ask_vwap250"], 2),
    "fee_per_share": passer["fee_per_share"],
    "fee_total_usd": round((150 / passer["exec_ask_vwap250"]) * passer["fee_per_share"], 2),
    "expected_value_gross_usd": round((150 / passer["exec_ask_vwap250"])
                                      * (passer["p_med"] - passer["exec_ask_vwap250"]), 2),
    "expected_value_net_usd": round((150 / passer["exec_ask_vwap250"])
                                    * (passer["exec_edge_haircut"] or 0), 2),
    "model_p": {"median": passer["p_med"], "min": passer["p_min"],
                "max": passer["p_max"], "n_variants": passer["n_variants"]},
    "edge": {"net_haircut_c": round(100 * passer["exec_edge_haircut"], 2),
             "gross_c": round(100 * passer["exec_edge_gross"], 2),
             "worst_variant_c": round(100 * passer["worst_variant_edge"], 2),
             "var_spread_c": round(100 * passer["var_spread"], 2)},
    "liquidity_gamma_usd": round(passer["liq_gamma"], 2),
    "depth_2c_shares": passer["depth_2c"],
    "fill_250": passer["fill_250"],
    "exit_liquidity": {"best_bid": passer["exit_bid"],
                       "bid_vwap250": passer["exit_bid_vwap250"],
                       "bid_depth_2c_shares": passer["exit_bid_depth_2c"]},
    "model_1x2": lam["p1x2_med"],
    "lambdas": {"home": lam["lambda_home"], "away": lam["lambda_away"],
                "total": lam["lambda_total"]},
    "gamma_verified": {"question": v["question"], "closed": v["closed"],
                       "active": v["active"],
                       "gameStartTime": v["gameStartTime"],
                       "endDate": v["endDate"],
                       "endDate_after_kick_within_30h": v["endDate_after_kick_within_30h"],
                       "verified_utc": v["verified_utc"],
                       "method": "/markets/{id} one-by-one (ids= list param broken since r39)"},
    "news_audit": {
        "verdict": ("CONCORDANT (one minority draw-tip noted) - featured "
                    "scoreline pick is a decisive result; bookmaker draw "
                    "price and model variants all lean non-draw"),
        "for": [
            "SportsGambler featured correct-score pick: Lens 1-2 Marseille -> "
            "decisive, ticket WINS",
            "SportsGambler headline tip Marseille +0.25 AH 'avoid defeat' - "
            "OM competitive, not a stalemate call",
            "Odds Lens 2.28 / Draw 3.60 / Marseille 2.85 -> market draw ~21-26% "
            "raw, decisive result ~74%+ (model 81.0%, all 10 variants >=0.7953)",
            "Marseille form surge: 4 straight wins (2-0 Toulouse, 1-0 at "
            "Leverkusen UEL), 6th/15pts; Lens crisis: 1-9 UCL home loss to "
            "Como, conceded in 13 consecutive matches, 2 without a win",
            "High expected total (model lambdas 2.42/1.48, total ~3.9; O2.5 "
            "1.61, BTTS 1.50) - goal-filled games rarely stalemate",
            "Yahoo lineups full-strength midfields (Lens 3-4-2-1 "
            "Thauvin/Hazard/Sotoca; Marseille 4-2-3-1 Weah/Hojbjerg/Paixao/"
            "Gouiri) - no packed-defensive setup on either side",
        ],
        "against": [
            "unnamed 'other tipsters forecast a 1-1 draw' (minority view; the "
            "same line concedes Lens slightly more likely to win)",
            "Marseille only 4 wins in last 10 away; Lens 7 wins in last 10 "
            "home (Bollaert) - competitive sides, draw not impossible",
            "SportsGambler AH +0.25 cover includes the draw scenario",
        ],
        "sources": [
            "https://www.sportsgambler.com/betting-tips/football/lens-vs-marseille-prediction-lineups-odds-2026-11-08",
            "https://sports.yahoo.com/articles/preview-lens-vs-marseille-team-184500556.html",
            "https://www.whoscored.com/matches/1984140/preview/france-ligue-1-2026-2027-lens-marseille",
        ],
    },
    "entry_flags": passer["entry_flags"],
    "post_entry_plan": (
        "paper entry at scan reference 0.74 (T-5.9h at scan). T-2h recheck "
        "(~17:45Z): confirm XIs vs Yahoo predicted lineups; if draw-side NO "
        "ask collapses below model worst-variant fair (~0.795) or a major "
        "defensive-setup/injury report inverts the read (e.g. Lens parking "
        "the bus after the 1-9), mark for paper exit at bid; mark-to-market "
        "at best bid otherwise (0.73 at scan, 29,463 shares within 2c). "
        "Resolution: NO wins on any non-draw scoreline."),
}

# near-miss documentation: top net-edge rows killed by numeric gates
gated = [r for r in board if not r.get("report_only")
         and r.get("exec_edge_haircut") is not None]
gated.sort(key=lambda r: -r["exec_edge_haircut"])
near = []
for r in gated[:14]:
    fails = [k for k, v in (r.get("checks") or {}).items()
             if not v and k != "news_concordant"]
    if not r.get("policy_eligible", False):
        fails.append("policy:" + str(r.get("policy")))
    near.append({
        "match": r["match"], "league": r["league"], "kind": r["kind"],
        "side": r["side"], "line": r.get("line"), "market_id": r["id"],
        "net_edge_haircut_c": round(100 * (r["exec_edge_haircut"] or 0), 2),
        "var_spread_c": round(100 * (r["var_spread"] or 0), 2),
        "worst_variant_edge_c": round(
            100 * (r["worst_variant_edge"]
                   if r["worst_variant_edge"] is not None else -9), 2),
        "liq_gamma": round(r["liq_gamma"] or 0, 0),
        "killed_by": sorted(set(fails)),
    })

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
out = {
    "round": 43,
    "sub_scan": "soccer_43B_euro_night",
    "scan": "soccer",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": d["window_utc"],
    "decision": (
        "PROPOSE ENTER 1 of <=$200 (coordinator arbitrates): Lens-Marseille "
        "DRAW NO $150 @0.74 ask-VWAP (market 6237097) - the sole numeric "
        "passer of the window: net +6.0c after fee & 50-50 haircut, worst "
        "variant +5.5c, var 5.24c, liq $51k, $250 walk fill ok, 10/10 "
        "variants 0.795+. News CONCORDANT: featured scoreline pick Lens 1-2 "
        "Marseille (SportsGambler), draw 3.60 in a 2.28/3.60/2.85 book, "
        "Marseille 4-straight-win form vs Lens crisis (1-9 UCL, conceded 13 "
        "straight); one minority 1-1 tip documented. This is the R41 "
        "edge-flip case playing out: at the R41 scan (~10h pre-kick) this "
        "row was not a passer; the family's var 12-20c kills are "
        "model-fixed and still kill every other Lens-Marseille row - only "
        "the draw_no side's variance (5.24c) sits under the 6c bar and its "
        "edge flipped positive at fresh prices. All other modeled fixtures "
        "fail frozen numeric gates; 16 board-only fixtures priced with no "
        "entry; Eredivisie totals-only enforced (Utrecht-NEC 1X2 rows "
        "INELIGIBLE, totals max edge -0.3c); spreads flagged-only "
        "everywhere; zero cross-league pairs (check_cross_league_mw wiring "
        "present, unexercised). Proposed ticket total $150 <= $200 dispatch "
        "cap."),
    "decision_rationale": (
        "350-row fee-aware board over 5 modeled fixtures (Hoffenheim-Schalke, "
        "Utrecht-NEC, Fiorentina-Juventus, Lens-Marseille, "
        "Atletico-Barcelona; all pre-kick at scan, none held, none "
        "post-kickoff) + 16 board-only fixtures (Belgian/Turkish/Portuguese/"
        "Scottish + Greek/Hungarian/Israeli/Norwegian/Polish/Serbian/Serie B/"
        "Belgian-2/Portuguese-2/Spanish-3/German-3) priced without entry, no "
        "model coverage. xG bases unchanged from the r41 refresh earlier "
        "today (Big-5 merged through Sat Nov-7; Eredivisie 103 matches "
        "through Sat Nov-7 20:00Z) - Sunday clubs correctly carry "
        "Oct-31/Nov-2 last-completed ratings (no Sunday results exist "
        "pre-kick); runtime staleness check flags ZERO clubs. Numeric kill "
        "map: Lens-Marseille team-total/totals/ML home rows +7 to +19c all "
        "die var 12-20c (model-fixed, matches R41); Fiorentina-Juventus best "
        "row spread -1.5 cover +7.3c dies worst +3.6c & var 10.4c (R41 "
        "repeat: still not a passer); Hoffenheim-Schalke total O4.5 +5.5c "
        "dies under-risk 8c bar + var 8.5c; Atletico-Barcelona best +2.3c "
        "worst -0.5c (R41 repeat: edge never materialized); Utrecht-NEC max "
        "edge +0.7c (ML, INELIGIBLE anyway). Single passer Lens-Marseille "
        "draw_no survives news + scoreline concordance (one focused search, "
        "3 sources). Budget: this ticket $150 of the $200 dispatch cap."),
    "max_new_entries_usd": 200,
    "positions_used": 1,
    "this_ticket_usd": 150,
    "stake_per_position_usd": 250,
    "stake_mw_usd": 150,
    "mw_stake_usd": 150,
    "max_new_positions": 1,
    "bankroll_usd": None,
    "cash_usd": None,
    "weekend_budget_note": ("dispatch R43B: propose entries totaling <=$200, "
                            "coordinator arbitrates; nothing passes = enter "
                            "nothing (1 passer proposed at the MW "
                            "deprioritized size)"),
    "open_positions_at_scan": 0,
    "open_positions": [],
    "open_positions_note": "no held fixtures in this window (dispatch)",
    "new_candidates": [entry],
    "killed_candidates": [],
    "near_miss_numeric_kills": near,
    "held_positions": None,
    "xg_bases": {
        "big5": ("understat_latest.json pointer -> round41/raw/"
                 "xg_fotmob_big5_merged.json (r41 refresh earlier today; "
                 "round25 Understat through Oct-31 + FotMob Nov-1..Nov-8 "
                 "backfill, Sat Nov-7 merged; last dates EPL/La_liga/Serie_A/"
                 "Bundesliga/Ligue_1 = Nov-7 17:30/20:00/19:45/17:30/19:45Z); "
                 "reused unchanged for R43B - no Sunday results existed at "
                 "refresh time, so Sunday clubs correctly carry Oct-31/Nov-2 "
                 "last-completed ratings"),
        "eredivisie": ("round41/raw/xg_fotmob_eredivisie.json (103 completed "
                       "matches through Sat Nov-7 20:00Z, r41 refetch earlier "
                       "today); no Sunday Eredivisie results exist pre-kick - "
                       "still current for Utrecht-NEC"),
        "championship": ("round31 snapshot wired; NO Sunday-night "
                         "Championship games in window (tag sweep "
                         "in_window=0); unused"),
        "staleness": ("runtime last-match-date check vs 2026-10-30 "
                      "thresholds: ZERO clubs flagged; no STALE-XG entries "
                      "on the board"),
    },
    "data_quality_flags": [
        ("SIBLING-COLLISION: a parallel Americas scan agent (round 43A) "
         "worked in ~/paper-sim/round43/raw/ during this scan and overwrote "
         "shared-looking filenames. events_window_43.json (original 191-event "
         "version written by enum43.py at ~13:46Z, loaded by scan43.py at "
         "13:50:25Z - 'events loaded: 191') was overwritten at 13:51:18Z "
         "with a 13-event Americas subset; espn_fixtures_43.json was "
         "overwritten at 13:48:52Z (ESPN league labels absent for Europe), "
         "which is why in-scan espn_cross fields are null. Collision-proof "
         "recaptures: events_window_43e.json (191 events) and "
         "espn_fixtures_43e.json (52 fixtures, 14 leagues x 2 dates)."),
        ("ESPN cross-check restored offline from espn_fixtures_43e.json with "
         "the scan's own rule (same league + kickoff within 3h + team-name "
         "overlap): 10/21 fixtures matched, 10 teams_agree - including ALL "
         "5 modeled fixtures (Hoffenheim-Schalke, Utrecht-NEC, "
         "Fiorentina-Juventus, Lens-Marseille, Atletico-Barcelona) and "
         "Besiktas-Genclerbirligi, Vitoria-Porto, St.Truiden-Zulte, "
         "Estrela-Benfica, Rio Ave-Braga. The 11 no-match fixtures are "
         "leagues outside the ESPN fetch set (Serbian/Liga2/Hungarian/"
         "Norwegian/Belgian-2/German-3/Israeli/Serie B/Greek/Polish/"
         "Spanish-3) - enumeration for those is Gamma-only."),
        ("scan43.log contains interleaved lines from sibling-agent processes "
         "holding file descriptors into the same log filename; this scan's "
         "own lines are contiguous and intact (UTC scan start 13:50:25Z -> "
         "saved euro_night_scan.json 13:54Z, board rows 350, matches 5, "
         "board-only fixtures 16)."),
        ("Gamma date-window sweeps (start_date_min/max) return 0 rows - "
         "Gamma ignores those params (known since r39); enumeration relies "
         "on the 11 league-tag sweeps + generic soccer tag sweep as in "
         "prior rounds."),
        ("unparsed_questions: 508 (corners/cards/halftime/player/exact-score "
         "long tail, same class as prior rounds - outside the frozen market "
         "family parser)."),
    ],
    "provenance": {
        "library_commit": "1a2760bc",
        "selfcheck": "PASS 10/10 (re-run 2026-11-08T13:40Z pre-scan)",
        "raw_board": ("round43/raw/euro_night_scan.json (350 board rows incl. "
                      "both sides of each market; 5 matches; 16 board-only "
                      "fixtures; 0 post-kick at scan; 0 cross-league pairs)"),
        "enumeration": ("round43/raw/events_window_43e.json (191 unique "
                        "soccer events, canonical recapture; original "
                        "events_window_43.json clobbered by sibling agent "
                        "post-load) + espn_fixtures_43e.json (52 fixtures)"),
        "gamma_verification": ("round43/raw/euro_night_verify.json (market "
                               "6237097; /markets/{id} one-by-one; closed="
                               "false, active, endDate 2026-11-08T19:45:00Z "
                               "= kickoff, within 30h)"),
        "scan_script": ("round43/raw/scan43.py = round41/raw/scan41.py "
                        "patched (patch43.py, exact-replacement, 16 ops): "
                        "window 18:00Z->01:14Z, no held fixtures, round43 "
                        "paths, extra European board-only leagues, $200 "
                        "budget note"),
    },
}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("wrote", OUT)
print("decision:", out["decision"][:140], "...")
print("new_candidates:", len(out["new_candidates"]),
      "| killed:", len(out["killed_candidates"]), "| near-miss:", len(near))
