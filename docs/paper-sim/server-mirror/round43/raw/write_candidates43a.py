#!/usr/bin/env python3
"""Build round43/euro_day_candidates.json from round43/raw/euro_day_scan.json +
verify_markets.json (r38 schema). Decision: ENTER 0 within this agent's <=$200
proposal cap - three FULL-GATE passers exist but each is a $250-class entry
(frozen stake), individually exceeding the cap; referred to coordinator.
PAPER ONLY."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round43/raw/euro_day_scan.json"
VERIF = "/home/ubuntu/paper-sim/round43/raw/verify_markets.json"
OUT = "/home/ubuntu/paper-sim/round43/euro_day_candidates.json"

d = json.load(open(SCAN))
board = d["board"]
verif = {v["id"]: v for v in json.load(open(VERIF))}
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def row_by(mid):
    for r in board:
        if r["id"] == str(mid):
            return r
    raise SystemExit("row not found: %s" % mid)


def cand_row(mid, rank, verdict, extra_news, extra_kill=None):
    r = row_by(mid)
    fails = [k for k, v in (r["checks"]).items() if not v and k != "news_concordant"]
    out = {
        "rank": rank,
        "match": r["match"], "league": r["league"],
        "kickoff_utc": r["kickoff_utc"],
        "market_question": r["q"], "market_id": r["id"],
        "kind": r["kind"], "side": r["side"], "line": r.get("line"),
        "team_side": r.get("team_side"),
        "hours_to_kick_at_scan": r["hours_to_kick_at_scan"],
        "stake_usd": r["stake_usd"],
        "entry_ask_vwap": r["exec_ask_vwap250"],
        "shares_if_filled": round(r["stake_usd"] / r["exec_ask_vwap250"], 2),
        "p_med": r["p_med"], "p_min": r["p_min"], "p_max": r["p_max"],
        "n_variants": r["n_variants"],
        "var_spread_c": round(100 * r["var_spread"], 2),
        "net_edge_c": round(100 * r["exec_edge_haircut"], 2),
        "gross_edge_c": round(100 * r["exec_edge_gross"], 2),
        "fee_per_share_c": round(100 * r["fee_per_share"], 2),
        "worst_variant_edge_c": round(100 * r["worst_variant_edge"], 2),
        "liq_gamma": round(r["liq_gamma"], 0),
        "fill_250": r["fill_250"],
        "depth_2c_shares": r.get("depth_2c"),
        "exit_bid": r.get("exit_bid"),
        "exit_bid_vwap250": r.get("exit_bid_vwap250"),
        "book_best_bid": r.get("book_best_bid"),
        "book_best_ask": r.get("book_best_ask"),
        "under_risk": r["under_risk"],
        "policy": r.get("policy"),
        "failed_checks": fails,
        "news_concordance": extra_news,
        "gamma_verified": (
            {"question": verif[r["id"]]["question"],
             "closed": verif[r["id"]]["closed"],
             "gameStartTime": verif[r["id"]]["gameStartTime"],
             "endDate": verif[r["id"]]["endDate"]}
            if r["id"] in verif else "not in verify set"),
        "verdict": verdict,
    }
    if extra_kill:
        out["kill_or_block"] = extra_kill
    return out


news_koln = {
    "verdict": "CONCORDANT (O0.5: team-to-score)",
    "sources": [
        {"pub": "Preview tip (search aggregation)", "detail": "1-1 draw (13/2) tip; BTTS Yes 4/7 tip",
         "concord": True},
        {"pub": "Spiegel/kicker lineup reports", "detail": "Koln derby XI: Schwabe; Sebulonsen; "
                  "Okon-Engstler, Sosa, Maina, Moore; Buelter + El Mala starting (full-strength "
                  "attack, no attacking absences flagged)", "concord": True},
        {"pub": "Leverkusen reports (Tipico/Yahoo)", "detail": "Leverkusen voraussichtlich: Flekken; "
                  "Quansah, Tapsoba, Medina, Gutierrez; Schick up top", "concord": True},
    ],
    "note": ("Both a 1-1 scoreline tip and a BTTS-4/7 tip keep Koln scoring >=1; "
             "reported XI is full-strength for the derby; T-0.7h at scan so "
             "lineup confirmation was required - German lineup reports show "
             "the expected first-choice attack starting."),
}
news_lille = {
    "verdict": "CONCORDANT (O0.5: team-to-score)",
    "sources": [
        {"pub": "Tips.GG", "detail": "high-scoring affair, narrow Rennes edge",
         "concord": True},
        {"pub": "Tipster aggregation", "detail": "'1-2 style outcome' (Lille scoring 2)",
         "concord": True},
        {"pub": "Starting11/SportsGambler predicted XIs", "detail": "Lille 4-3-3 under Ancelotti: "
                  "Ozer; Ngoy, Nianzou, Alexsandro, Perraud; Mukau, Andre...; main squad, no "
                  "attacking-injury red flags in previews", "concord": True},
    ],
    "note": ("Every cited projection has Lille scoring; kicked 14:00Z (in play "
             "at decision time, official XIs released pre-kick per schedule); "
             "T-0.2h at scan."),
}
news_brentford = {
    "verdict": "CONCORDANT (O0.5: team-to-score)",
    "sources": [
        {"pub": "Yahoo Sports", "detail": "hard-fought 1-1 draw prediction", "concord": True},
        {"pub": "R41 news basis (same fixture, still current)", "detail": "consensus scorelines "
                  "Brighton 2-1 and 1-1 - Brentford score exactly 1 in both", "concord": True},
        {"pub": "Sports Gambler (updated ~1h pre-kick)", "detail": "Brighton predicted XI near "
                  "first choice; Brighton 10/11 favourites, Brentford 13/5", "concord": True},
    ],
    "note": ("O0.5 needs only a Brentford goal; both consensus scorelines "
             "(2-1, 1-1) satisfy it - the SAME news that killed the O1.5 "
             "ticket in R41 is concordant for O0.5. Kicked 14:00Z (in play at "
             "decision time). One-position-per-fixture: O0.5 is this "
             "fixture's candidate (O1.5 R41-dead, O2.5 discordant)."),
}
news_rayo_tt = {
    "verdict": "DISCORDANT (scoreline concordance, r32 standard)",
    "sources": [
        {"pub": "Sportskeeda", "detail": "last 8 La Liga H2H meetings ALL under 2.5 goals; tight, "
                  "low-scoring defensive contest expected", "concord": False},
        {"pub": "Sports Mole / Sports Gambler previews", "detail": "Real Sociedad near full "
                  "strength (Remiro; Kubo/Sucic/Gomez/Oyarzabal-class front), home-favourite "
                  "consensus; tight low-scoring game", "concord": False},
    ],
    "note": ("Rayo TT O1.5 needs 2+ Rayo goals; under-2.5 tight-game consensus "
             "and home-favourite previews put Rayo on <=1 - same kill class as "
             "R41's Rayo tickets. Numeric pass (+8.2c) dies at the "
             "scoreline-concordance gate."),
}
news_rayo_ml = {
    "verdict": "NOT REACHED - R41 revive price leg failed",
    "sources": [{"pub": "CLOB book (scan recheck)", "detail": "Yes-token ask 0.22 vs R41 0.22",
                 "concord": None}],
    "note": ("R41 news-kill standing: revive needs ask >=3c cheaper AND news "
             "flip. Ask moved 0c; R41 discordance (home-win consensus) "
             "unchanged in this round's previews. DEAD."),
}
news_btts = {
    "verdict": "NOT REACHED - R41 revive price leg failed",
    "sources": [{"pub": "CLOB book (scan recheck)", "detail": "Yes-token ask 0.53 vs R41 0.49",
                 "concord": None}],
    "note": ("Ask moved 4c AGAINST us (0.49 -> 0.53); did not re-pass "
             "numerics either. R41 scoreline-concordance kill stands. DEAD."),
}
news_brent_o15 = {
    "verdict": "NOT REACHED - R41 revive price leg failed",
    "sources": [{"pub": "CLOB book (scan recheck)", "detail": "Over-token ask 0.33 vs R41 0.35",
                 "concord": None}],
    "note": ("Ask moved only +2c in our favor (<3c bar); R41 kill "
             "(consensus scorelines put Brentford on exactly 1 goal) stands "
             "and this round's 1-1 draw tip repeats it. DEAD. (Its numeric "
             "re-pass at +8.4c is recorded but not actionable.)"),
}
news_brent_o25 = {
    "verdict": "DISCORDANT + superseded (one position per fixture)",
    "sources": [{"pub": "Yahoo/R41 consensus scorelines", "detail": "2-1 / 1-1 both put Brentford "
                 "on <=1 goal; O2.5 needs 3+", "concord": False}],
    "note": ("Weakest concordance on the fixture; O0.5 is the fixture's "
             "candidate under the one-position-per-fixture rule."),
}

referrals = [
    cand_row(6239547, 1, "PASS ALL GATES - REFERRAL (over cap)",
             news_koln,
             "Full-gate passer ($250 class). Exceeds this agent's <=$200 "
             "proposal cap by $50 at frozen stake sizing; referred to "
             "coordinator. Best edge on the board: net +9.2c, worst +7.4c."),
    cand_row(6240191, 2, "PASS ALL GATES - REFERRAL (over cap)",
             news_lille,
             "Full-gate passer ($250 class), exceeds <=$200 cap; referred. "
             "Kicked 14:00Z (T-0.2h at scan; in play at decision time) - "
             "entry only actionable at scan-time prices."),
    cand_row(6239565, 3, "PASS ALL GATES - REFERRAL (over cap)",
             news_brentford,
             "Full-gate passer ($250 class), exceeds <=$200 cap; referred. "
             "Kicked 14:00Z (T-0.2h at scan; in play at decision time)."),
]

killed = [
    cand_row(6243362, 4, "KILLED at scoreline-concordance gate", news_rayo_tt),
    cand_row(6241503, 5, "DEAD - R41 news-kill, revive price leg failed", news_rayo_ml),
    cand_row(6239569, 6, "DEAD - R41 news-kill, revive price leg failed", news_brent_o15),
    cand_row(6239573, 7, "KILLED (discordant + one-position-per-fixture)", news_brent_o25),
]
# 6239948 Genoa-Milan BTTS: no live board row this scan (kicked/in-play); record from recheck
rk = d["r41_kill_recheck"]["6239948"]
killed.append({
    "rank": 8, "match": "Genoa CFC vs. AC Milan", "league": "Serie_A",
    "kickoff_utc": "2026-11-08T14:00:00Z",
    "market_question": rk.get("question"), "market_id": "6239948",
    "kind": "btts", "side": "yes", "line": None, "team_side": None,
    "hours_to_kick_at_scan": None, "stake_usd": 250,
    "r41_baseline": {"ask": 0.49, "vwap250": 0.4972, "p_med": 0.5696,
                     "net_edge_haircut_c": 5.99},
    "fresh_ask_our_side": rk.get("fresh_ask_our_side"),
    "ask_move_favorable_c": rk.get("ask_move_favorable_c"),
    "verdict": "DEAD - R41 news-kill, revive price leg failed (-4c)",
    "news_concordance": news_btts,
    "note": ("In play at scan (kicked 14:00Z; no live gated row). Price leg "
             "0.49 -> 0.53 = 4c AGAINST; R41 mixed-scoreline kill stands."),
})

# R41-kill recheck with corrected Rayo token mapping (raw scan JSON recorded
# the No-token 0.79 as 'fresh_ask_our_side' for 6241503; our side is the Yes
# token idx 0 = 0.22; both books are in the raw record)
recheck_fixed = {}
for mid_s, rec in d["r41_kill_recheck"].items():
    r2 = dict(rec)
    if mid_s == "6241503":
        yes_book = next((b for b in rec.get("books", [])
                         if b.get("token_idx") == 0), None)
        fresh = yes_book.get("best_ask") if yes_book else None
        r2["token_correction"] = ("raw scan mis-mapped our side to No-token "
                                  "(idx 1, 0.79); corrected to Yes-token "
                                  "idx 0")
        r2["fresh_ask_our_side"] = fresh
        r2["ask_move_favorable_c"] = round(100 * (0.22 - fresh), 1) if fresh else None
        r2["price_leg_revive_ok"] = bool(fresh is not None and 0.22 - fresh >= 0.03)
    recheck_fixed[mid_s] = r2

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

held_model = {
    "67_le_mans_monaco_mw_no": {
        "entry": "MW NO $150 @0.44",
        "mark_at_scan": "No bid 0.41 / ask 0.42 (gamma 0.585/0.415)",
        "model_p_no_side": 0.6389, "model_range": [0.6129, 0.6517],
        "model_view": "+EV per model (identical reused xG base as r41); mark ~1-3c behind entry price"},
    "68_brest_lyon_o25_over": {
        "entry": "O2.5 Over $250 @0.51",
        "mark_at_scan": "Over bid 0.54 / ask 0.55 (gamma 0.545/0.455)",
        "model_p_over": 0.5866, "model_range": [0.572, 0.592],
        "model_view": "+EV per model; mark 3-4c ahead of entry"},
    "63_manutd_villa_mw_no": {
        "entry": "MW NO $150 @0.70",
        "mark_at_scan": "No bid 0.69 / ask 0.70 (gamma 0.305/0.695)",
        "model_p_no_side": 0.7806, "model_range": [0.757, 0.7941],
        "model_view": "+EV per model; mark flat vs entry"},
}

out = {
    "round": 43,
    "sub_scan": "euro_day_43A",
    "scan": "soccer-euro-day-window",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": d["window_utc"],
    "decision": (
        "ENTER 0 within this agent's <=$200 proposal cap. Three candidates "
        "pass EVERY frozen gate (numeric + news/scoreline concordance + "
        "verified IDs), but all three are $250-class entries at frozen stake "
        "sizing, so each individually exceeds the cap - they are REFERRED to "
        "the coordinator (who arbitrates the round budget across 3 agents), "
        "not proposed as entries by this agent. Ranked referrals: (1) Koln "
        "TT O0.5 net +9.2c worst +7.4c var 5.42c liq $16.8k ask 0.72 "
        "(T-0.7h); (2) Lille TT O0.5 net +7.3c worst +6.7c var 4.98c liq "
        "$16.3k ask 0.73 (T-0.2h, kicked 14:00Z); (3) Brentford TT O0.5 net "
        "+5.5c worst +6.1c var 2.42c liq $45.5k ask 0.70 (T-0.2h, kicked "
        "14:00Z). Everything else on the board dies at frozen gates: R41 "
        "news-kills all stay dead (price legs: Rayo ML 0c move, Brentford "
        "O1.5 +2c < +3c, Genoa-Milan BTTS -4c against); Rayo TT O1.5 "
        "(+8.2c) dies on scoreline discordance (last-8 H2H all U2.5); "
        "dominant numeric killer elsewhere is variant spread >6c. Nothing "
        "passes = enter nothing was NOT triggered - things passed, but none "
        "fits <=$200 at frozen stakes."),
    "decision_rationale": (
        "1610-row fee-aware board over 24 modeled fixtures (all 24 dispatch "
        "slate fixtures found on Gamma and modeled; ESPN cross-check "
        "teams_agree on every matched fixture; Napoli-Lazio post-kick at "
        "enum with primary markets closed -> 0 residual rows, expected for "
        "an in-play game whose main markets resolved at kickoff; 11 "
        "board-only fixtures priced in Belgian/Turkish/Portuguese/Scottish "
        "leagues, no model coverage, no entry; 805 in-window soccer events "
        "enumerated). Scan ran 13:49-13:58Z: morning slate post-kickoff "
        "(board historical), afternoon slate T-0.2h..T-4.3h - earlier than "
        "the dispatch's assumed T-6h..T-12h, so every candidate fixture "
        "kicked <2h from scan and required lineup confirmation: Koln's "
        "derby XI reports show a full-strength attack (Buelter/El Mala "
        "starting), Brighton-Brentford and Rennes-Lille official XIs were "
        "released pre-kick per schedule (both kicked 14:00Z). xG bases "
        "REUSED unchanged from r41 per dispatch (Big-5 merged through Sat "
        "Nov-7; Eredivisie 103 matches through Sat Nov-7): runtime "
        "staleness check = ZERO flags, 138 registry titles. 7 numeric "
        "passers on 4 fixtures; after one-position-per-fixture, the R41 "
        "revive rule, and scoreline concordance: 3 full passers (all "
        "referred, over cap), 5 kills. Largest numeric kills: "
        "Palace-Liverpool ml away_no +22.2c net but var 14.89c; Monza-"
        "Atalanta ml home +15.1c var 12.82c; Rennes-Lille total over +14.2c "
        "var 21.73c; Koln-Leverkusen ml home +13.7c var 13.69c; Cambuur-PSV "
        "rows var 10-15c (promoted-club divergence) and team-total rows also "
        "fail liq>=$5k ($2.9-3.5k); Angers-Nice ml home +12.3c var 10.59c. "
        "Eredivisie totals-only respected (Cambuur-PSV ml home +11.2c was "
        "INELIGIBLE anyway). No cross-league pairs in window (check_cross_"
        "league_mw + CROSS_LEAGUE_ML_CLASS wiring present, unexercised). "
        "Held marks #67/#68/#63 fetched: all open, books deep; model fair "
        "values 0.639/0.587/0.781 vs scan marks 0.415/0.545/0.695."),
    "max_new_positions": 0,
    "max_new_entries_usd_this_agent": 200,
    "positions_used": 0,
    "stake_per_position_usd": 250,
    "mw_stake_usd": 150,
    "total_stake_usd": 0,
    "bankroll_usd": None,
    "cash_usd": None,
    "weekend_cap_all_agents_usd": None,
    "this_subscan_share_usd": 200,
    "open_positions_note": (
        "3 held positions marked (no new positions on held fixtures): #67 "
        "Le Mans-Monaco MW NO $150@0.44, #68 Brest-Lyon O2.5 Over $250@0.51, "
        "#63 ManUtd-Villa MW NO $150@0.70. Soccer pool $3,000 @ $1,700 "
        "headroom incl. $1,100 UCL/UEL reserve (unchanged - r42 entered "
        "nothing). This agent's <=$200 cap consumed: $0."),
    "new_candidates": [],
    "coordinator_referrals_over_cap": referrals,
    "blocked_passers": killed,
    "killed_candidates": killed,
    "near_miss_numeric_kills": near,
    "r41_kill_recheck": {
        "verdicts": {
            "6241503": "DEAD - ask 0.22 -> 0.22 (0c move; needs >=3c favorable)",
            "6239948": "DEAD - ask 0.49 -> 0.53 (4c AGAINST)",
            "6239569": "DEAD - ask 0.35 -> 0.33 (+2c < +3c bar)",
        },
        "rule": ("revive ONLY if ask moved >=3c in our favor AND fresh "
                 "search shows news flipped; default dead. All three failed "
                 "the price leg, so no news-flip search was required."),
        "records_corrected": recheck_fixed,
        "correction_note": ("raw euro_day_scan.json r41_kill_recheck."
                            "6241503.fresh_ask_our_side recorded the "
                            "No-token (0.79) due to a token-index mapping "
                            "bug; corrected here from books[token_idx=0] "
                            "(Yes = our side) = 0.22. All other values "
                            "unchanged; both books are in the raw record."),
    },
    "held_positions": {
        "marks": d["held_positions"],
        "model_context": held_model,
    },
    "key_game_notes": {
        "napoli_lazio": "kicked 11:30Z; post-kick at enum, primary markets "
                        "closed -> 0 modeled residual rows (expected)",
        "koeln_leverkusen": "top referral: Koln TT O0.5; derby, Koln "
                            "full-strength attack reported; ask 0.72 vs "
                            "p_med 0.822",
        "brighton_brentford": "O1.5 R41-kill not revived (+2c); O0.5 "
                              "concordant (1-1/2-1 scorelines both have "
                              "Brentford scoring); O2.5 discordant",
        "real_sociedad_rayo": "both live rows killed: TT O1.5 scoreline-"
                              "discordant (U2.5 consensus), ML away R41-dead "
                              "(0c move)",
        "rennes_lille": "Lille TT O0.5 referral; kicked 14:00Z (in play at "
                        "decision time); entry only actionable at scan-time "
                        "prices",
        "eredivisie": "totals-only respected; Cambuur-PSV promoted-club "
                      "variance kills all rows; AZ-Groningen no passer",
        "board_only": "11 fixtures (Turkish x3, Belgian x2, Scottish x2, "
                      "Portuguese x3, +1) priced board-only, no entry",
    },
    "xg_bases": {
        "big5": "REUSED r41 understat_latest pointer -> round41/raw/"
                "xg_fotmob_big5_merged.json (NOT re-refreshed per dispatch)",
        "eredivisie": "REUSED round41/raw/xg_fotmob_eredivisie.json (103 "
                      "matches through Sat Nov-7)",
        "staleness": "runtime last-match-date check: ZERO clubs flagged",
    },
    "scan_artifacts": {
        "raw_board": "round43/raw/euro_day_scan.json (1610 board rows, 24 "
                     "matches, 11 board-only fixtures)",
        "enumeration": "round43/raw/events_window_43a.json (805 in-window "
                       "soccer events) + espn_fixtures_43a.json (92 "
                       "fixtures)",
        "gamma_verification": "round43/raw/verify_markets.json (5 market "
                              "ids via /markets/{id}; ids= list param "
                              "broken per r39, not used)",
        "scripts": "round43/raw/enum43a.py, scan43a.py, verify43a.py, "
                   "write_candidates43a.py",
    },
    "provenance": {
        "library_commit": "1a2760bc",
        "selfcheck": "PASS 10/10 (re-run 2026-11-08T13:40Z pre-scan)",
        "scan_window_utc": {"lo": "2026-11-08T05:30:00Z",
                            "hi": "2026-11-08T17:59:59Z"},
        "paper_only": True,
    },
}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("wrote", OUT)
print("decision:", out["decision"][:140], "...")
print("referrals:", len(referrals), "| killed:", len(killed), "| near:", len(near))
for mid, v in out["r41_kill_recheck"]["verdicts"].items():
    print("R41KILL", mid, v)
