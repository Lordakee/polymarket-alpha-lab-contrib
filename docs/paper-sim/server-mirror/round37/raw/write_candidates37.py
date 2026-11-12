"""Build round37/soccer_candidates.json from round37/raw/soccer_scan.json."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round37/raw/soccer_scan.json"
OUT = "/home/ubuntu/paper-sim/round37/soccer_candidates.json"
d = json.load(open(SCAN))
board = d["board"]


def row(mid, side, kind, line):
    for r in board:
        if (r["id"] == str(mid) and r["side"] == side
                and r["kind"] == kind and r["line"] == line):
            return r
    raise SystemExit("row not found: %s %s %s %s" % (mid, side, kind, line))


held_row = row(6111575, "over", "team_total", 0.5)   # = #62 market
ml_away = row(6109530, "away", "ml", None)           # Alaves ML away
tt_o15 = row(6111578, "over", "team_total", 1.5)     # Alaves TT O1.5
ven_tt = None
for r in board:
    if ("Venezia" in r["match"] and r["kind"] == "team_total"
            and r["side"] == "over" and r["line"] == 1.5):
        ven_tt = r
        break
ev_ml = None
for r in board:
    if ("Everton FC vs. Coventry" in r["match"] and r["kind"] == "ml"
            and r["side"] == "away"):
        ev_ml = r
        break

shares62 = round(250 / 0.6277, 2)
unreal = round(shares62 * (held_row["exit_bid_vwap250"] - 0.6277), 2)
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

out = {
    "round": 37,
    "scan": "soccer",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": {"lo": "2026-11-06T10:00:00Z", "hi": "2026-11-07T10:00:00Z"},
    "decision": (
        "HONEST PASS 0 (of max 2) new positions - every non-held fixture fails "
        "frozen numeric gates; the only 3 numeric passers are all on Sevilla-"
        "Alaves, blocked by the held-fixture overlay (#62 same-fixture "
        "concentration discipline). Held #62 verified CONCORDANT and held."),
    "decision_rationale": (
        "T-10h fee-aware re-scan of the six Friday domestic openers on the FRESH "
        "xG base (FotMob merge through Nov-1/2; all 12 clubs verified complete - "
        "r36 stale flags resolved). 706 board rows. Three numeric passers, ALL on "
        "Sevilla-Alaves: Alaves ML away +13.6c net (worst +13.3c, var 5.7c), "
        "Alaves TT O1.5 +13.2c net (worst +13.3c, var 1.3c), Alaves TT O0.5 "
        "+11.8c net vs current ask (the held #62 market). All three are blocked "
        "for NEW entry: #62 is already live on this fixture ($250 Alaves TT O0.5 "
        "@ 0.6277), and the three rows are near-perfectly correlated (all win "
        "when Alaves performs); r35/r36 same-fixture concentration precedent "
        "caps this fixture at one position. The two higher-edge rows "
        "additionally carry r36 news kills that still stand: every published "
        "scoreline (Sportsmole 2-1 again today) puts Alaves on exactly 1 goal "
        "or the losing side, killing TT O1.5 and ML away under the r32 "
        "scoreline-concordance rule. Every other fixture fails gates outright: "
        "Venezia-Udinese best row TT O1.5 +12.5c dies on variant spread 32.2c "
        "(bar 6c) and worst +3.9c (bar +4c); Everton-Coventry ML away +10.6c "
        "dies on worst -0.7c (var 18.2c); Hamburg-Gladbach (+2.7c), "
        "Toulouse-Strasbourg (+2.8c), Derby-Bolton (+2.2c) never reach the +5c "
        "net bar. Saturday early: zero games kick before Nov-7 10:00Z in any of "
        "the six leagues (earliest Saturday kick 12:30Z) - nothing to act on."),
    "max_new_positions": 2,
    "positions_used": 0,
    "stake_per_position_usd": 250,
    "bankroll_usd": 13409.00,
    "cash_usd": 11923.00,
    "open_positions": 5,
    "open_positions_note": ("per coordinator brief: 5 open = #62 soccer (this "
                            "scan verifies it) + 4 non-soccer"),
    "new_candidates": [],
    "held_position_verifications": [
        {
            "id": 62,
            "round_entered": 36,
            "match": "Sevilla FC vs. Deportivo Alaves",
            "kickoff_utc": "2026-11-06T20:00:00Z",
            "market": "Deportivo Alaves team total O/U 0.5 - OVER (id 6111575)",
            "side_bought": "OVER (Alaves scores >= 1)",
            "entry_ask_vwap250": 0.6277,
            "stake_usd": 250,
            "shares": shares62,
            "verification_utc": now,
            "hours_to_kickoff": "T-10h at scan; T-9h at board pull",
            "verdict": ("HOLD - thesis intact, news CONCORDANT, nothing changed "
                        "since r36 entry"),
            "model_recheck_fresh_xg": {
                "p_med": held_row["p_med"], "p_min": held_row["p_min"],
                "p_max": held_row["p_max"],
                "var_spread_c": round(100 * held_row["var_spread"], 2),
                "n_variants": held_row["n_variants"],
                "lambda_sevilla": 1.303, "lambda_alaves": 1.266,
                "note": ("fresh snapshot (Getafe 1-3 Nov-1 now IN) reproduces "
                         "r36 model almost exactly; p(Alaves scores) 0.718 "
                         "unchanged"),
            },
            "market_now": {
                "best_bid": held_row["book_best_bid"],
                "best_ask": held_row["book_best_ask"],
                "exit_bid_vwap250": held_row["exit_bid_vwap250"],
                "unrealized_at_exit_bid_usd": unreal,
                "mark_note": ("entry 0.6277 vs bid 0.57 = -4.0c/share "
                              "mark-to-market (-$%.2f on %.0f sh); settle-to-"
                              "full-time position, mark is informational; "
                              "model still +9.0c vs entry price"
                              % (unreal, shares62)),
                "model_edge_vs_entry": round(held_row["p_med"] - 0.6277, 4),
                "model_edge_vs_current_ask_net": held_row["exec_edge"],
            },
            "news_concordance_recheck": {
                "verdict": ("CONCORDANT (unchanged from r36; re-verified "
                            "2026-11-06 ~10:30Z)"),
                "supporting": [
                    ("Sportsmole (fetched today): Sevilla miss Marcao (muscular) "
                     "and Miguel Sierra (shoulder); Manu Bueno suspended (red "
                     "card in the 3-1 Getafe defeat); Isaac Romero a major "
                     "doubt - predicted back line Iglesias/Castrin/Salas/Suazo "
                     "again improvised"),
                    ("Sportsmole predicted XI has Boye starting (5 league "
                     "goals) with T. Martinez back in the side - Alaves "
                     "attack intact, no rotation reported"),
                    "Sportsmole predicted scoreline 2-1 Sevilla - Alaves on the scoresheet",
                    ("Yahoo preview: Alaves have scored in 4 consecutive "
                     "matches; Sevilla conceded 3 at Getafe last time out "
                     "(now IN the fresh xG base)"),
                    ("Alaves absentees (Garces + Rodriguez/Ulacia per source "
                     "variance) are defensive/bench - no attacker affected"),
                ],
                "contradicting": [
                    ("Alaves winless in 7 league games, winless in 5 away; "
                     "hammered 1-6 by Barcelona Oct-31 (scored 1)"),
                    ("No source found reporting Sevilla defensive returns or "
                     "Alaves attacking rotation"),
                ],
                "sources": [
                    "https://www.sportsmole.co.uk/football/sevilla/preview/sevilla-vs-alaves-prediction-team-news-lineups_608392.html",
                    "https://sports.yahoo.com/articles/preview-sevilla-fc-vs-alav-190100892.html",
                ],
            },
            "action_items": (
                "confirmed XIs drop ~18:30-19:00Z: if Boye is benched/rotated "
                "heavily or Sevilla defensive absences unexpectedly return, "
                "re-verify #62 before kickoff; otherwise hold to settlement."),
        },
    ],
    "blocked_passers": [
        {"match": "Sevilla FC vs. Deportivo Alaves", "kind": "ml",
         "side": "away (Alaves win)",
         "net_edge": round(ml_away["exec_edge_haircut"], 4),
         "worst": ml_away["worst_variant_edge"],
         "var_c": round(100 * ml_away["var_spread"], 2),
         "ask": ml_away["exec_ask_vwap250"], "p_med": ml_away["p_med"],
         "liq_gamma": ml_away["liq_gamma"],
         "blocked_by": ("held-fixture overlay (#62) + same-fixture concentration "
                        "+ r36 news kill still standing: consensus scorelines "
                        "(2-1) put Alaves on the losing side; MW deprioritized $150")},
        {"match": "Sevilla FC vs. Deportivo Alaves", "kind": "team_total",
         "side": "over 1.5",
         "net_edge": round(tt_o15["exec_edge_haircut"], 4),
         "worst": tt_o15["worst_variant_edge"],
         "var_c": round(100 * tt_o15["var_spread"], 2),
         "ask": tt_o15["exec_ask_vwap250"], "p_med": tt_o15["p_med"],
         "liq_gamma": tt_o15["liq_gamma"],
         "blocked_by": ("held-fixture overlay (#62) + r36 news kill still "
                        "standing: consensus scorelines give Alaves exactly 1 "
                        "goal -> O1.5 loses")},
        {"match": "Sevilla FC vs. Deportivo Alaves", "kind": "team_total",
         "side": "over 0.5 (= #62 market)",
         "net_edge": round(held_row["exec_edge_haircut"], 4),
         "worst": held_row["worst_variant_edge"],
         "var_c": round(100 * held_row["var_spread"], 2),
         "ask": held_row["exec_ask_vwap250"], "p_med": held_row["p_med"],
         "liq_gamma": held_row["liq_gamma"],
         "blocked_by": ("held-fixture overlay: #62 already live at 0.6277 "
                        "(ask now 0.5883)")},
        {"match": "Venezia FC vs. Udinese Calcio", "kind": "team_total",
         "side": "over 1.5",
         "net_edge": round(ven_tt["exec_edge_haircut"], 4),
         "worst": ven_tt["worst_variant_edge"],
         "var_c": round(100 * ven_tt["var_spread"], 2),
         "ask": ven_tt["exec_ask_vwap250"], "p_med": ven_tt["p_med"],
         "liq_gamma": ven_tt["liq_gamma"],
         "blocked_by": ("variant spread 32.2c >> 6c bar AND worst +3.9c < +4c "
                        "bar (n=10 samples per club still thin post-merge)")},
        {"match": "Everton FC vs. Coventry City FC", "kind": "ml",
         "side": "away (Coventry win)",
         "net_edge": round(ev_ml["exec_edge_haircut"], 4),
         "worst": ev_ml["worst_variant_edge"],
         "var_c": round(100 * ev_ml["var_spread"], 2),
         "ask": ev_ml["exec_ask_vwap250"], "p_med": ev_ml["p_med"],
         "liq_gamma": ev_ml["liq_gamma"],
         "blocked_by": ("worst variant -0.7c < +4c bar; variant spread 18.2c > "
                        "6c; MW deprioritized")},
    ],
    "saturday_early_check": {
        "deadline_utc": "2026-11-07T10:00:00Z",
        "games_before_deadline": [],
        "finding": (
            "ZERO games kick before 10:00Z Nov-7 across EPL, Championship, "
            "Serie A, La Liga, Bundesliga, Ligue 1 (ESPN verified). Earliest "
            "Saturday kickoffs are 12:30Z (Leeds-Tottenham EPL; Bristol City-"
            "Norwich, Portsmouth-Stoke, Wrexham-Wolves Championship). Serie A "
            "earliest is 14:00Z (no 11:30Z slot this week). All Saturday games "
            "are report-only for this window; the 12:30Z/12:45Z/13:00Z games "
            "were nonetheless modeled and priced in the board for next-round "
            "inventory (post-window flag set)."),
    },
}
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("decision:", out["decision"][:120])
