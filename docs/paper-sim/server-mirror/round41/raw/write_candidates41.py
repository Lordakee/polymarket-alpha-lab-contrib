#!/usr/bin/env python3
"""Build round41/candidates.json from round41/raw/scan.json + verify_markets.json
(r38 schema). Decision: ENTER 0 - all three numeric passers die on
news/scoreline concordance. PAPER ONLY."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round41/raw/scan.json"
VERIF = "/home/ubuntu/paper-sim/round41/raw/verify_markets.json"
OUT = "/home/ubuntu/paper-sim/round41/candidates.json"

d = json.load(open(SCAN))
board = d["board"]
verif = {v["id"]: v for v in json.load(open(VERIF))}


def gate_row(r):
    fails = [k for k, v in (r["checks"]).items() if not v and k != "news_concordant"]
    return {
        "market_id": r["id"], "market_question": r["q"], "kind": r["kind"],
        "side": r["side"], "line": r.get("line"),
        "team_side": r.get("team_side"),
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


passers = {
    "6241503": {
        "match": "Real Sociedad de Fútbol vs. Rayo Vallecano de Madrid",
        "league": "La_liga", "stake_usd": 150,
        "kill": ("NEWS-DISCORDANT (MW): every preview leans Real Sociedad home "
                 "win - Sports Mole predicted XI (Remiro; Kubo/Sucic/Guedes/"
                 "Oyarzabal) at near full strength, Real Sociedad 5th/19pts vs "
                 "Rayo 9th/13pts, 'most experts lean toward a Real Sociedad "
                 "home win'. Model 29.1% Rayo vs market 22% has no "
                 "Rayo-favorable injury/rotation fact behind it - unexplained "
                 "model-market divergence. Same kill class as r38 Rayo ML "
                 "away (scoreline-concordance standard). MW family also "
                 "eligible-DEPRIORITIZED (2W-3L record) - deprioritized + "
                 "news-discordant = dead."),
        "news": ("Sports Mole preview: Real Sociedad favourites at home, "
                 "predicted XI near first-choice; Rayo 4-2-3-1 with Audero/"
                 "Ratiu/Lejeune. Expert consensus: home win / tight "
                 "low-scoring game. NOT concordant with an away-win ticket."),
    },
    "6239948": {
        "match": "Genoa CFC vs. AC Milan", "league": "Serie_A", "stake_usd": 250,
        "kill": ("SCORELINE-CONCORDANCE INSUFFICIENT (r32 standard): "
                 "projections split 0-2 / 1-2 Milan and SportsGambler's "
                 "featured value correct-score pick is Milan 2-0 (+700) - a "
                 "clean-sheet scoreline that loses BTTS-Yes. Half the "
                 "consensus scorelines lose the ticket; r38 precedent "
                 "(Auxerre-Paris FC 'mixed, insufficient concordance') kills "
                 "this. Model 57.0% vs ask 0.4972 is not enough to override "
                 "mixed news."),
        "news": ("Genoa 11th/13pts (2-1 win at Lecce, De Rossi), Milan "
                 "favourite (AH -0.5/-1.0, goal line 2.5). Common projected "
                 "scorelines 0-2 or 1-2 Milan; SportsGambler value CS pick "
                 "Milan 2-0. MIXED for BTTS-Yes."),
    },
    "6239569": {
        "match": "Brighton & Hove Albion FC vs. Brentford FC",
        "league": "EPL", "stake_usd": 250,
        "kill": ("SCORELINE-DISCORDANT (r32): consensus scorelines are "
                 "Brighton 2-1 and 1-1 - Brentford on EXACTLY 1 goal in both; "
                 "Brentford TT OVER 1.5 needs 2+. Brentford have drawn all "
                 "four away league games (draw-heavy, low away scoring "
                 "profile). Only minority poll picks (Brentford 2-0 / "
                 "Brighton 3-2) carry the over. Exact r38 Osasuna TT O1.5 "
                 "kill pattern (predicted 1 goal vs 1.5 line)."),
        "news": ("Brighton unbeaten in 4 home league games, title-picture "
                 "form, favourites (-114); consensus prediction Brighton 2-1, "
                 "1-1 draw also in play; Brentford 0 away wins (4 draws). "
                 "Predicted scorelines put Brentford on <=1 goal - "
                 "discordant with TT O1.5."),
    },
}

killed = []
for mid, meta in passers.items():
    killed.append({**gate_row(row_by(mid)), **meta,
                   "status": "KILLED at news/scoreline-concordance gate"})

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
        "entry": "MW NO $150 @0.44", "current_no_side": "bid 0.42 / ask 0.43",
        "model_p_no_side": 0.6389, "model_range": [0.6129, 0.6517],
        "model_view": "strongly +EV per model; mark ~flat/slightly behind entry"},
    "68_brest_lyon_o25_over": {
        "entry": "O2.5 Over $250 @0.51", "current_over": "bid 0.50 / ask 0.51",
        "model_p_over": 0.5866, "model_range": [0.572, 0.592],
        "model_view": "+EV per model; mark flat"},
    "63_manutd_villa_mw_no": {
        "entry": "MW NO $150 @0.70", "current_no_side": "bid 0.69 / ask 0.70",
        "model_p_no_side": 0.7806, "model_range": [0.757, 0.7941],
        "model_view": "+EV per model; mark flat"},
}

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
out = {
    "round": 41,
    "sub_scan": "soccer_41A",
    "scan": "soccer",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": d["window_utc"],
    "decision": (
        "ENTER 0 of max $600: all three numeric passers die at the "
        "news/scoreline-concordance gate. (1) Rayo ML away +6.2c - expert "
        "consensus Real Sociedad home win, no Rayo-favorable fact behind the "
        "model-market gap (r38 Rayo kill class; MW deprioritized anyway). "
        "(2) Genoa-Milan BTTS Yes +6.0c - projections split 0-2/1-2 with the "
        "featured CS value pick Milan 2-0 = mixed/insufficient concordance "
        "(r38 Auxerre-Paris FC class). (3) Brentford TT O1.5 +5.9c - "
        "consensus scorelines 2-1/1-1 put Brentford on exactly 1 goal (r38 "
        "Osasuna TT O1.5 class). Every remaining board row fails a frozen "
        "numeric gate (dominant killer: variant spread >6c). Dispatch rule: "
        "nothing passes = enter nothing. Pool $3,000 untouched at $1,700 "
        "headroom incl. $1,100 UCL/UEL reserve."),
    "decision_rationale": (
        "2030-row fee-aware board over 29 modeled fixtures (26 enterable + "
        "3 held, none post-kickoff at scan; 15 board-only fixtures in Belgian/Turkish/"
        "Portuguese/Scottish priced without entry; 551 untagged league events "
        "recorded raw-board-only). xG bases REFRESHED THIS SESSION: Big-5 "
        "merged through Sat Nov-7 (FotMob backfill, 45 window matches, all "
        "with xG; merge41.py added 8 title overrides; understat_latest "
        "pointer re-pointed after validation) and Eredivisie refetched (103 "
        "matches through Sat Nov-7) -> ZERO stale clubs in the Sunday slate; "
        "no STALE-XG flags raised. Three numeric passers, all killed on "
        "news/scoreline concordance (one focused search each): details in "
        "killed_candidates. Largest numeric kills: Crystal Palace-Liverpool "
        "ml away_no +21.1c net but var 14.89c (10-variant model disagrees "
        "with itself badly on this fixture); Lens-Marseille family var "
        "12-20c (and team-total rows also fail liq>=$5k); Cambuur-PSV "
        "promoted-club divergence var 10-15c as expected for a first-season "
        "Eredivisie side; Twente-Ajax ml home +12.8c var 12.37c AND "
        "Eredivisie 1X2 INELIGIBLE (totals-only, gate-E). No cross-league "
        "pairs in the window (all 29 fixtures single-league; "
        "check_cross_league_mw wiring present but unexercised). Held marks "
        "#67/#68/#63 fetched: all open, books deep; model fair values 0.639/"
        "0.587/0.781 vs current marks 0.425/0.505/0.695 - all three held "
        "positions remain +EV per model."),
    "max_new_entries_usd": 600,
    "positions_used": 0,
    "this_ticket_usd": 0,
    "stake_per_position_usd": 250,
    "stake_mw_usd": 150,
    "bankroll_usd": None,
    "cash_usd": None,
    "soccer_pool_usd": 3000,
    "headroom_usd": 1700,
    "ucl_uel_reserve_usd": 1100,
    "open_positions_at_scan": 3,
    "new_candidates": [],
    "killed_candidates": killed,
    "near_miss_numeric_kills": near,
    "held_positions": {
        "marks": d["held_positions"],
        "model_context": held_model,
    },
    "xg_bases": {
        "big5": ("understat_latest.json pointer -> round41/raw/"
                 "xg_fotmob_big5_merged.json; round25 Understat through "
                 "Oct-31 + FotMob Nov-1..Nov-8 backfill; Sat Nov-7 MERGED "
                 "(last dates EPL 11-07 17:30Z, La_liga 20:00Z, Serie_A "
                 "19:45Z, Bundesliga 17:30Z, Ligue_1 19:45Z); validated "
                 "(team counts 20/20/20/18/18, no duplicate history dates, "
                 "2025 blocks byte-identical) then pointer re-pointed"),
        "eredivisie": ("round41/raw/xg_fotmob_eredivisie.json refetched "
                       "02:34Z (103 completed matches, Sat Nov-7 round "
                       "Telstar-Fortuna/ADO-Sparta/Excelsior-GAE merged)"),
        "championship": ("round31 snapshot wired; NO Sunday Championship "
                         "games in window (tag sweep in_window=0); unused"),
        "staleness": ("runtime last-match-date check: ZERO clubs flagged; "
                      "no STALE-XG entries on the board"),
    },
    "provenance": {
        "library_commit": "1a2760bc",
        "selfcheck": "PASS 10/10 (re-run 2026-11-08T02:11Z pre-scan)",
        "raw_board": "round41/raw/scan.json (2030 board rows, 29 matches, "
                     "15 board-only fixtures, 210 report-only rows)",
        "enumeration": "round41/raw/events_window_41.json (882 unique soccer "
                       "events) + espn_fixtures_41.json (45 fixtures, dates "
                       "Nov-8/Nov-9)",
        "gamma_verification": "round41/raw/verify_markets.json (3 market "
                              "ids; /markets/{id} one-by-one; ids= list "
                              "param confirmed broken in r39 and not used)",
    },
}
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print("wrote", OUT)
print("decision:", out["decision"][:120], "...")
print("killed:", len(killed), "| near-miss:", len(near))
