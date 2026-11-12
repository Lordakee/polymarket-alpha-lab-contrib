"""Build round36/soccer_candidates.json from round36/raw/soccer_scan.json."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round36/raw/soccer_scan.json"
OUT = "/home/ubuntu/paper-sim/round36/soccer_candidates.json"

d = json.load(open(SCAN))
board = d["board"]

def row(mid, side, kind=None, line=None):
    for r in board:
        if (r["id"] == mid and r["side"] == side
                and (kind is None or r["kind"] == kind)
                and (line is None or r["line"] == line)):
            return r
    raise SystemExit("row not found: %s %s %s %s" % (mid, side, kind, line))

cand = row("6111575", "over", "team_total", 0.5)   # Alaves TT Over 0.5
ml = row("6109530", "away", "ml")                  # Alaves ML away (killed)
o15 = row("6111578", "over", "team_total", 1.5)    # Alaves TT Over 1.5 (killed)
hn = [r for r in board if r["match"] == cand["match"] and r["kind"] == "ml"
      and r["side"] == "home_no"][0]  # killed by variant spread

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

out = {
 "round": 36,
 "scan": "soccer",
 "paper_only": True,
 "generated_utc": now,
 "window_utc": {"lo": "2026-11-05T23:00:00Z", "hi": "2026-11-06T23:00:00Z"},
 "decision": "ENTER 1 (of max 2) - Alaves team total Over 0.5 $250 @ 0.6277 walked ask-VWAP, net edge +7.9c; second slot unused (honest pass)",
 "decision_rationale": (
   "Six Friday domestic openers all modeled on the standard 10-variant domestic "
   "path (bridge not needed; Championship pair on FotMob WP-P3). 420 board rows, "
   "3 numeric passers, ALL on Sevilla-Alaves: Alaves ML away +11.5c net, Alaves "
   "TT O1.5 +9.4c net, Alaves TT O0.5 +7.9c net. News-concordance kills the "
   "first two: every published scoreline (Sportsmole 2-1, Football Whispers 2-1, "
   "1-1 variants) puts Alaves on exactly 1 goal or on the losing side, and all "
   "tipsters pick Sevilla (Dimers Alaves 25.1% win); r32 precedent kills rows "
   "whose consensus projected scoreline loses the bet. TT O0.5 (Alaves scores "
   ">=1) is CONCORDANT: BTTS tipped likely (73% of Sevilla matches, 64% of "
   "Alaves'), Boye (5 league goals) starts, Sevilla miss THREE defensive pieces "
   "(Marcao muscular, Sierra shoulder, Manu Bueno suspended after Getafe red) "
   "and conceded 3 last time out - the very Getafe defeat that is the stale "
   "game missing from the xG base, so the modeled edge is, if anything, "
   "conservative. Same-fixture concentration discipline caps this fixture at "
   "ONE position (r35 precedent), so ML/O1.5 are not taken alongside O0.5 even "
   "absent the news kills. No other fixture produced a numeric passer: best "
   "non-Sevilla net edges die on worst-variant (Everton rows <= -0.7c worst) or "
   "variant-spread (Venezia-Udinese rows 19-41c spread) or edge (Hamburg, "
   "Toulouse, Derby all <= +1.6c net)."),
 "max_new_positions": 2,
 "positions_used": 1,
 "stake_per_position_usd": 250,
 "bankroll_usd": 13409.00,
 "cash_usd": 11923.00,
 "open_positions": 3,
 "open_positions_note": (
   "per coordinator brief bankroll/cash. r35 soccer positions #59 "
   "(Leverkusen-Marseille BTTS Yes, kicked Nov-5 20:00Z) and #60 "
   "(Middlesbrough-Wrexham U3.5, kicked Nov-4) settled; no open paper position "
   "on any of the six Friday fixtures; held-position overlay empty this round."),
 "new_candidates": [
   {
    "rank": 1,
    "match": "Sevilla FC vs. Deportivo Alaves",
    "comp": "La Liga Friday opener (J12)",
    "kickoff_utc": "2026-11-06T20:00:00Z",
    "market": "Deportivo Alaves team total O/U 0.5 - OVER (id 6111575)",
    "question": "Sevilla FC vs. Deportivo Alavés: Deportivo Alavés O/U 0.5",
    "side_bought": "OVER (Alaves scores >= 1)",
    "entry_ask_vwap250": cand["exec_ask_vwap250"],
    "stake_usd": 250,
    "model": {
      "p_med": cand["p_med"], "p_min": cand["p_min"], "p_max": cand["p_max"],
      "n_variants": cand["n_variants"], "var_spread_c": round(100 * cand["var_spread"], 2),
      "lambda_home": [m["lambda_home"] for m in d["matches"]
                     if "Sevilla" in m["match"]][0],
      "lambda_away": [m["lambda_away"] for m in d["matches"]
                      if "Sevilla" in m["match"]][0],
      "method": "library fixture_variants 10 sweeps, domestic La_liga (Understat round25 snapshot)",
      "under_risk": cand["under_risk"],
    },
    "gates": {
      "exec_edge_gross": cand["exec_edge_gross"],
      "fee_per_share": cand["fee_per_share"],
      "exec_edge_net": cand["exec_edge"],
      "worst_variant_edge": cand["worst_variant_edge"],
      "bar": "+5c NET of sports fee (frozen gate)",
      "liq_gamma_usd": cand["liq_gamma"],
      "fill_250": cand["fill_250"],
      "entry_band": "0.6277 in [.10-.92]",
      "exit_bid_vwap250": cand["exit_bid_vwap250"],
      "round_trip_cost_c": round(100 * (cand["exec_ask_vwap250"] - cand["exit_bid_vwap250"]), 2),
      "checks": cand["checks"],
    },
    "news_concordance": {
      "verdict": "CONCORDANT (weak-to-moderate; thesis = Alaves scores)",
      "supporting": [
        "BTTS tipped likely: 73% of Sevilla's matches and 64% of Alaves' have seen both sides score (stats-based previews)",
        "Sportsmole predicted score 2-1 and Football Whispers 2-1 - Alaves on the scoresheet in both",
        "Sevilla defensive absences: Marcao (muscular), Miguel Sierra (shoulder), Manu Bueno (suspended, red card at Getafe); predicted back line Iglesias/Castrin/Salas/Suazo is improvised",
        "Sevilla conceded 3 at Getafe last time out (that game is the stale one missing from xG base - edge is conservative)",
        "Alaves no fresh injuries from the Barcelona match; Boye (5 league goals) leads the line",
      ],
      "contradicting": [
        "Alaves form: 2 points from last 7 league games, no win since early September",
        "One xG-analyst source projects BTTS only ~30% (own xG line 1.35-1.10) - outlier vs tipster consensus",
        "H2H: Alaves strong vs Sevilla (1 loss in last 7, 4 wins) - actually supports Alaves performance, noted for completeness",
      ],
      "sources": [
        "https://www.sportsmole.co.uk/football/sevilla/preview/sevilla-vs-alaves-prediction-team-news-lineups_608392.html",
        "https://sports.yahoo.com/articles/preview-sevilla-fc-vs-alav-190100892.html",
        "https://www.dimers.com/la-liga/news/sevilla-vs-alaves-prediction-11-06-2026-ac",
        "https://www.whoscored.com/matches/1994023/preview/spain-laliga-2026-2027-sevilla-deportivo-alaves",
      ],
      "stale_xg_direction": (
        "Sevilla missing Nov-1 Getafe 3-1 L (conceded 3): model UNDERRATES Sevilla "
        "defensive weakness -> true p(Alaves scores) >= modeled 0.718; Alaves "
        "fully fresh in snapshot (Oct-31 game included). Direction favors the bet."),
    },
    "entry_plan": (
      "PAPER entry at scan price 0.6277 walked $250 ask-VWAP (best ask 0.62 + "
      "walk); T-20h pre-kick, XIs drop ~19:00Z Nov-6 - if Alaves XI shows heavy "
      "rotation (Boye benched) or Sevilla defensive absences unexpectedly "
      "return, re-verify before marking the paper fill; settle at full time."),
    "entry_flags": cand["entry_flags"],
   },
 ],
 "held_position_verifications": [],
 "blocked_passers": [
   {"match": "Sevilla FC vs. Deportivo Alavés", "kind": "ml", "side": "away (Alaves win)",
    "net_edge": ml["exec_edge_haircut"], "worst": ml["worst_variant_edge"],
    "var_c": round(100 * ml["var_spread"], 2), "ask": ml["exec_ask_vwap250"],
    "p_med": ml["p_med"], "liq": ml["liq_gamma"],
    "blocked_by": ("NEWS-CONCORDANCE (killed): all tipsters pick Sevilla "
                   "(Sportsmole/Football Whispers 2-1; Dimers Alaves 25.1% win); "
                   "Alaves 2 pts from 7 games; ALSO same-fixture concentration "
                   "(1 position per fixture) and MW deprioritized $150")},
   {"match": "Sevilla FC vs. Deportivo Alavés", "kind": "team_total", "side": "over 1.5 (Alaves >= 2)",
    "net_edge": o15["exec_edge_haircut"], "worst": o15["worst_variant_edge"],
    "var_c": round(100 * o15["var_spread"], 2), "ask": o15["exec_ask_vwap250"],
    "p_med": o15["p_med"], "liq": o15["liq_gamma"],
    "blocked_by": ("NEWS-CONCORDANCE (killed): every published scoreline (2-1, "
                   "1-1) has Alaves on exactly 1 goal - consensus projected "
                   "outcome loses the bet (r32 Forebet precedent); ALSO "
                   "same-fixture concentration vs taken O0.5")},
   {"match": "Sevilla FC vs. Deportivo Alavés", "kind": "ml", "side": "home_no (Sevilla not to win)",
    "net_edge": hn["exec_edge_haircut"], "worst": hn["worst_variant_edge"],
    "var_c": round(100 * hn["var_spread"], 2), "ask": hn["exec_ask_vwap250"],
    "blocked_by": "LIBRARY GATE variant_spread 7.19c > 6c (and MW deprioritized)"},
 ],
 "non_passer_fixture_notes": {
   "Everton vs Coventry": ("best nets +10.6c (Coventry ML away) / +8.2c (Coventry TT O1.5) "
                           "but ALL fail worst-variant >= +4c (<= -0.7c): variant specs "
                           "disagree on Coventry's promoted-side rating (n=9); no entry"),
   "Venezia vs Udinese": ("nets up to +10.6c on Venezia TT Over rows but variant-spread "
                          "19-41c >> 6c: model disagreement on Venezia (n=9, stale); "
                          "classic wide-board no-entry"),
   "Hamburg vs Gladbach": ("board dead: best net +1.2c (draw_no); Hamburg stale "
                           "(n=7); model H 41.0% vs market ~43%; nothing close"),
   "Toulouse vs Strasbourg": ("best net +1.6c (spread, flagged-only anyway); ONLY "
                              "fixture with both clubs xG-stale; BTTS No +1.4c "
                              "below bar; nothing close"),
   "Derby vs Bolton": ("fresh FotMob data both sides; board dead: best net +1.2c "
                       "(Derby ML) - market and model agree; nothing close"),
 },
 "fee_model": {
   "note": ("evaluate_candidate(fee_rate=FEE_RATE_SPORTS=0.05): 0.05*p*(1-p) per "
            "share charged at the walked $250 ask VWAP; +5c exec bar NET of fee; "
            "haircut acts on net edge; worst_variant_edge gross."),
   "candidate_fee_drag_c": round(100 * cand["fee_per_share"], 2),
   "board_fee_drag_range_c": "0.3c-1.3c per share across 420 rows",
 },
 "understat_status": {
   "site": "https://understat.com/league/EPL/2026",
   "http": "200 BUT maintenance/error page (errors.css artboard, no teamsData) - site STILL effectively down",
   "base_used": "/home/ubuntu/paper-sim/understat_latest.json -> round25/raw/xg_understat_25.json (pointer set 2026-11-04T14:25:22Z)",
   "fresh_through": "2026-10-31 league results",
   "cron": "understat_refresh.py every 30min still failing (cron retained)",
 },
 "staleness_quantification": d["staleness_quantification"],
 "selfcheck": "277 passed, 1 skipped (papersim test files, re-run this session ~23:30Z Nov-5)",
 "library": d["library"],
 "raw_scan": "round36/raw/soccer_scan.json",
 "raw_log": "round36/raw/scan36_soccer.log",
 "raw_events": "round36/raw/events_window_36.json",
 "raw_espn": "round36/raw/espn_fixtures_20261106.json",
}

json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("decision:", out["decision"])
