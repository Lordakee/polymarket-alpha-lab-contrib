"""Build round42/candidates.json from round42/raw/scan.json (r38 schema +
round-42 early_entry / recheck_conditions fields). Paper-only round."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round42/raw/scan.json"
OUT = "/home/ubuntu/paper-sim/round42/candidates.json"

d = json.load(open(SCAN))
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

out = {
    "round": 42,
    "scan": "ucl-uel-midweek-window-round42",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": {"lo": "2026-11-10T00:00:00Z", "hi": "2026-11-13T00:00:00Z"},
    "decision": (
        "ENTER NOTHING - clean empty board, $0 of the $600 UCL/UEL reserve. "
        "The dispatch premise (Tue-Wed UCL/UEL matchdays Nov 10-12) is "
        "disproven by the enumeration: ZERO men's UCL/UEL fixtures exist in "
        "the window on Gamma or ESPN. In-world matchday calendar: UCL MD4 was "
        "Nov 3-4, UEL MD4 Nov 4-5 (last week, closed); UCL MD5 = Nov 24-25, "
        "UEL MD5 = Nov 26 (open Gamma events confirm). The Nov 10-12 midweek "
        "is the UEFA Nations League international window plus Copa del Rey, "
        "women's UWCL, club friendlies and South American league games - all "
        "out of scope for this dispatch. No fixture reached modeling, so no "
        "bridge lambdas, no gate table, no market-id verification set, and no "
        "news-concordance pass were produced. Per the frozen rule: nothing "
        "passes = enter nothing; gates were NOT stretched to fill budget."),
    "decision_rationale": (
        "Enumeration (02:43Z Nov-8): 8 Gamma sweeps (date-window x2 + tag "
        "soccer/ucl/champions-league/uefa-champions-league/europa-league/uel) "
        "-> 25 in-window soccer events, 0 carrying a men's UCL or UEL tag; "
        "the dispatch-exact /events?closed=false&start_date_min=... query "
        "returns 0 in every timestamp format. ESPN uefa.champions / "
        "uefa.europa scoreboards for Nov 10, 11, 12 all return 0 fixtures. "
        "Adjacent matchdays on ESPN: UCL Nov 3 (9), Nov 4 (9), Nov 24 (9), "
        "Nov 25 (9); UEL Nov 4 (1), Nov 5 (17), Nov 26 (18) - i.e. MD4 last "
        "week, MD5 in 16-18 days. External corroboration (UEFA.com / "
        "Wikipedia 2026-27 UCL league phase): MD4 = Nov 3-4, MD5 = Nov 24-25, "
        "mid-November = international window. The two lookalikes were run "
        "down: PSG vs Bayern Nov 10 20:00Z is the WOMEN'S Champions League "
        "(slug uwcl-psg-bm-2026-11-10), and Wolfsburg vs Union Berlin Nov 12 "
        "13:30Z is a CLUB FRIENDLY (clf series; event description says "
        "'Club Friendlies game... November 12, 2026'; placeholder 0.49/0.51 "
        "pricing, no volume). Copa del Rey fixtures (8) involve La Liga "
        "clubs but are a domestic cup against non-snapshot minnows -> "
        "model-void pairs anyway, and outside the UCL/UEL dispatch scope. "
        "Library selfcheck PASS 10/10 at repo 1a2760bc re-run before "
        "modeling; kappa bridge loaded (Big-5 table, round31 estimation) and "
        "check_cross_league_mw + CROSS_LEAGUE_ML_CLASS wiring armed but "
        "never triggered - no eligible fixture existed. xG base: Big-5 fresh "
        "through Sat Nov-7 (round41 FotMob merge; understat pointer re-pointed "
        "2026-11-08T02:24Z), Sunday Nov-8 domestic round (24 fixtures) "
        "unresulted at scan time - stale-club table recorded for the MD5 "
        "recheck."),
    "max_new_positions": 0,
    "positions_used": 0,
    "stake_per_position_usd": None,
    "total_stake_usd": 0,
    "budget": {
        "round_max_new_entries_usd": 600,
        "used_usd": 0,
        "soccer_pool_usd": 3000,
        "ucl_uel_reserve_usd": ">=1100 intact; round-42 $600 allocation untouched; ' >=$500 stays for Wed/Thu' moot (no Wed/Thu UCL/UEL fixtures exist)",
    },
    "bankroll_usd": None,
    "bankroll_note": ("not provided in this dispatch; pool accounting per "
                      "brief: soccer pool $3,000, >=$1,100 UCL/UEL reserve"),
    "open_positions_note": (
        "no UCL/UEL-midweek positions exist to mark; held domestic positions "
        "#63-#68 (r40 dispatch set) are outside this window and untouched"),
    "new_candidates": [],
    "new_candidates_schema_note": (
        "r38 candidate schema applies per candidate (market_id, question, "
        "kind, side, line, kickoff, gate table, walk metrics, verified IDs, "
        "news) plus round-42 fields early_entry=true and "
        "recheck_conditions[]; zero candidates were produced because zero "
        "in-scope fixtures exist"),
    "killed_candidates": [],
    "killed_candidates_note": (
        "nothing reached a gate - kills require a modeled row; the two "
        "UCL-lookalike fixtures (UWCL PSG-Bayern, clf Wolfsburg-Union) are "
        "documented in scan.json fixtures_in_window_out_of_scope instead"),
    "early_entry": {
        "global": (
            "every numeric passer this round would have carried "
            "early_entry=true (lineups unknown at T-2.5..T-4d) with "
            "sizing via risk_policy.sizing_tier(lineup_confirmation=0.0) "
            "-> EARLY_ENTRY tier $150 (MW cross-league fixed MARGINAL $150); "
            "not triggered - no candidates"),
    },
    "recheck_conditions": {
        "global": (
            "T-24h recheck condition is vacuously satisfied this round (no "
            "entries taken). Recheck obligations for the NEXT round: (1) the "
            "next genuine UCL/UEL window is MD5, Tue-Wed Nov 24-25 (UCL) and "
            "Thu Nov 26 (UEL) - enumerate then; (2) refresh the Big-5 xG base "
            "so the Sunday Nov-8 round (24 fixtures, stale-club table in "
            "scan.json) results before any MD5 modeling; (3) any MD5 "
            "cross-league MW candidate must still pass "
            "gates.check_cross_league_mw (bridge_present + "
            "worst_variant_edge>=+5c) at $150 CROSS_LEAGUE_ML_CLASS."),
    },
    "news_concordance": {
        "calendar_verification": {
            "verdict": (
                "CONCLUSIVE: no men's UCL/UEL matchday exists in the "
                "2026-11-10..13 window; midweek is the Nations League "
                "international window"),
            "findings": [
                "Gamma: 25 in-window soccer events, zero with ucl/uel tags; open men's UCL matchday events all end 2026-11-24/25",
                "ESPN: uefa.champions + uefa.europa scoreboards return 0 fixtures on Nov 10/11/12; UCL Nov 3+4 and UEL Nov 4+5 (MD4) populated last week; UCL Nov 24+25 and UEL Nov 26 (MD5) populated",
                "external: UEFA.com fixtures and the Wikipedia 2026-27 UCL league-phase page give MD4=Nov 3-4, MD5=Nov 24-25, mid-November = international window",
                "Nations League matchday on Gamma Nov 12 19:45Z: Czechia-Spain ($5.5k vol), Italy-France, England-Croatia, Turkiye-Belgium, San Marino-Belarus, Armenia-Cyprus, Montenegro-Latvia",
            ],
            "sources": [
                "https://www.uefa.com/uefachampionsleague/fixtures-results",
                "https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase",
            ],
        },
        "note": ("no per-candidate news pass ran: the dispatch's news "
                 "concordance (one focused search per numeric passer) binds "
                 "only to candidates, and none existed"),
    },
    "data_quality_flags": {
        "dispatch_premise": (
            "dispatch assumed Tue-Wed UCL/UEL matchdays Nov 10-12; in-world "
            "calendar has none (MD4 Nov 3-5, MD5 Nov 24-26) - empty board is "
            "the correct outcome, not a data failure"),
        "xg_base": (
            "Big-5 fresh through Sat Nov-7 via round41 FotMob merge "
            "(understat outage continues; Understat recovery cron retains "
            "priority); Sunday Nov-8 round (EPL 5, La_liga 5, Serie_A 5, "
            "Bundesliga 3, Ligue_1 6 fixtures) unresulted at scan time -> "
            "1-round stale per participating club until next refresh "
            "(full table in scan.json staleness_sunday_nov8)"),
        "gamma_ids_param": (
            "not exercised this round (no candidate verification needed); "
            "r39 evidence that ids= list param is broken stands"),
        "parallel_round41": (
            "round41 (Sat window) ran concurrently on the host; its FotMob "
            "merge + pointer re-point at 02:21-02:24Z were reused read-only "
            "by this round; round42 wrote only under ~/paper-sim/round42/"),
    },
    "library": {
        "package": "polymarket_alpha_lab.papersim",
        "repo_commit": "1a2760bc",
        "selfcheck": "PASS 10/10 (re-run 2026-11-08 ~02:38Z pre-modeling)",
        "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
        "fee_model": ("evaluate_candidate(fee_rate=FEE_RATE_SPORTS=0.05); "
                      "not exercised - no gated rows"),
    },
    "scan_source": "/home/ubuntu/paper-sim/round42/raw/scan.json",
    "scan_artifacts": {
        "raw_board": "/home/ubuntu/paper-sim/round42/raw/scan.json",
        "events_window": "/home/ubuntu/paper-sim/round42/raw/events_window_42.json",
        "espn_fixtures": "/home/ubuntu/paper-sim/round42/raw/espn_fixtures_42.json",
        "stale_sunday_nov8": "/home/ubuntu/paper-sim/round42/raw/stale_nov8_9.json",
        "enum_script": "/home/ubuntu/paper-sim/round42/raw/enum42.py",
        "finalize_script": "/home/ubuntu/paper-sim/round42/raw/finalize42.py",
    },
}
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("decision:", out["decision"][:120])
print("positions_used:", out["positions_used"])
