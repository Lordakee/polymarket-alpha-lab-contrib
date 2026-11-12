"""Round-26 sub-scan B finalizer: patch news_checks into scan_b.json and write
candidates_b.json (honest pass: zero numeric gate passes across 399 rows)."""
import json
from datetime import datetime, timezone

RAW = "/home/ubuntu/paper-sim/round26/raw/scan_b.json"
OUT = "/home/ubuntu/paper-sim/round26/candidates_b.json"

d = json.load(open(RAW))
rows = d["gate_rows"]
by_key = {(r["match"], r["kind"], str(r["side"]), r["line"], r.get("team_side")): r
          for r in rows}


def row(match, kind, side, line, team=None):
    return by_key.get((match, kind, side, line, team))


def brief(r, team):
    if not r:
        return "row missing"
    return ("exec %+.1fc, worst %+.1fc, var %.1fc, liq $%s, ask250 %s, id %s" % (
        (r["exec_edge"] or 0) * 100, (r["worst_variant_edge"] or 0) * 100,
        r["var_spread"] * 100, int(r["liq_gamma"]), r["exec_ask_vwap250"], r["id"]))


LIV = "Liverpool FC vs. Arsenal FC"
UNI = "1. FC Union Berlin vs. 1. FC Köln"
PFC = "Paris FC vs. AS Monaco FC"
FRA = "Eintracht Frankfurt vs. Hamburger SV"
LYO = "Olympique Lyonnais vs. Angers SCO"
STR = "RC Strasbourg Alsace vs. AJ Auxerre"
OM = "Olympique de Marseille vs. Toulouse FC"

news_checks = [
    {"fixture": LIV, "delta": "morning-of (T-7h)", "news_delta": "worse (for Arsenal-favorful sides)",
     "concordant": False,
     "blockers": ["Arsenal crisis not in xG: Saka (quad, out ~Dec), Saliba out, Madueke (ankle), "
                  "Dowman suspended; Rice + Calafiori doubts. Liverpool: Isak out; Ekitike/Bradley/Leoni/"
                  "Frimpong/Szoboszlai/Munoz doubts"],
     "sources": ["standard.co.uk XI/preview", "lastwordonsports.com predicted lineups",
                 "ESPN/DraftKings ARS +155 O/U 2.5", "Paddy Power ML LIV 2.90 / ARS 2.40 / D 3.30",
                 "sportsgambler Under2.5 -109", "FanDuel BTTS Yes -156"]},
    {"fixture": UNI, "delta": "morning-of (T-5h)", "news_delta": "mixed", "concordant": False,
     "blockers": ["Koln beat Union 5-0 in DFB-Pokal Oct 27 (cup match, NOT in league xG); "
                  "Koln strikers Rondic + Dallinga out; Koln league defense worst (2.57 ga/g)"],
     "sources": ["web search: DFB-Pokal report + injury roundup"]},
    {"fixture": PFC, "delta": "morning-of (T-6h)", "news_delta": "worse (for PFC-scoring sides)",
     "concordant": False,
     "blockers": ["PFC: Ikone out (leg), Koleosho doubtful (thigh), Sangui/Camara out, "
                  "Traore/Matondo knocks; Monaco 0.9 ga/g (3rd-best defense), Fati/Dier out for Monaco"],
     "sources": ["sportsmole.co.uk Paris FC vs Monaco preview", "ESPN/DraftKings PAR +145 O/U 2.5"]},
    {"fixture": FRA, "delta": "morning-of (T-6h)", "news_delta": "unchanged",
     "concordant": True, "blockers": [],
     "sources": ["Yahoo preview (4-4-2 vs 3-5-2, no material absences reported)",
                 "ESPN/DraftKings HAM at FRA, O/U 2.5"]},
    {"fixture": LYO, "delta": "morning-of", "news_delta": "unchanged", "concordant": True,
     "blockers": [], "sources": ["ESPN/DraftKings LYON -245 O/U 2.5; no injury news surfaced"]},
    {"fixture": STR, "delta": "morning-of", "news_delta": "unchanged", "concordant": True,
     "blockers": [], "sources": ["ESPN/DraftKings STR -120 O/U 2.5; Strasbourg 16th on 7pts, "
                                 "lost 3-0 at Rennes (in xG base)"]},
    {"fixture": OM, "delta": "morning-of", "news_delta": "unchanged", "concordant": True,
     "blockers": [], "sources": ["ESPN/DraftKings OLM -105, O/U 3.5 line"]},
]
d["news_checks"] = news_checks
json.dump(d, open(RAW, "w"), indent=1)

flagged = [
    {"match": LIV, "market": "Arsenal ML Yes (id %s)" % row(LIV, "ml", "away", None)["id"],
     "numbers": brief(row(LIV, "ml", "away", None), None),
     "reason": "SKIP news-explained + gate-fail: worst +3.7c < +4c, var 8.9c > 6c (and 50-50 "
               "haircut halves exec to +3.5c). Arsenal injury crisis (Saka/Saliba/Madueke out) "
               "explains the whole model edge: books devig ARS ~39% = Polymarket 38c; the xG model "
               "(45%) is the outlier. Domestic ML also deprioritized class."},
    {"match": UNI, "market": "Union Berlin team total O1.5 Over (id %s)" % row(UNI, "team_total", "over", 1.5, "home")["id"],
     "numbers": brief(row(UNI, "team_total", "over", 1.5, "home"), "home"),
     "reason": "SKIP variant gates: worst -8.0c, var 16.4c. Promoted Koln rating uncertainty "
               "(last-season fallback dominates); Koln 5-0 Pokal rematch volatility not in league xG."},
    {"match": PFC, "market": "Paris FC ML Yes (id %s)" % row(PFC, "ml", "home", None)["id"],
     "numbers": brief(row(PFC, "ml", "home", None), None),
     "reason": "SKIP variant gates: worst -2.3c, var 25.7c. PFC promoted-side rating uncertainty."},
    {"match": LIV, "market": "Spread Arsenal -1.5 (id %s)" % row(LIV, "spread", "away", -1.5, "away")["id"],
     "numbers": brief(row(LIV, "spread", "away", -1.5, "away"), "away"),
     "reason": "FLAGGED-ONLY class (spreads never entered): exec +5.5c, worst +3.6c, var 6.7c - "
               "would fail worst/var anyway; Arsenal absences cut blowout tail."},
    {"match": LIV, "market": "Arsenal team total O1.5 (id %s)" % row(LIV, "team_total", "over", 1.5, "away")["id"],
     "numbers": brief(row(LIV, "team_total", "over", 1.5, "away"), "away"),
     "reason": "SKIP gate-fail: worst +1.7c < +4c, var 7.5c > 6c; news worse (Saka + Madueke out "
               "deplete Arsenal scoring the model cannot see)."},
    {"match": FRA, "market": "Hamburg team totals Under 2.5/1.5 + match U3.5/U2.5 (ids %s,%s,%s,%s)" % (
        row(FRA, "team_total", "under", 2.5, "away")["id"], row(FRA, "team_total", "under", 1.5, "away")["id"],
        row(FRA, "total", "under", 3.5, None)["id"], row(FRA, "total", "under", 2.5, None)["id"]),
     "numbers": "exec +5.2c / +5.2c / +4.5c / +4.4c",
     "reason": "SKIP worst-variant everywhere (-4.7c to -6.4c): model's Frankfurt home-attack rating "
               "(lambda 2.05) vs market disagreement is variant-driven, not agreement."},
    {"match": PFC, "market": "Paris FC team total O1.5 (id %s)" % row(PFC, "team_total", "over", 1.5, "home")["id"],
     "numbers": brief(row(PFC, "team_total", "over", 1.5, "home"), "home"),
     "reason": "CLOSEST NEAR-MISS: exec +4.9c (fails 5c by 0.06c; 50-50 haircut takes it to +2.5c), "
               "worst +3.8c (fails by 0.22c). News also worse (Ikone out, Koleosho doubtful, Monaco "
               "3rd-best defense). Honest fail, no relaxation."},
    {"match": UNI, "market": "O/U 2.5 Over (id %s) - the r25 recheck item" % row(UNI, "total", "over", 2.5, None)["id"],
     "numbers": brief(row(UNI, "total", "over", 2.5, None), None),
     "reason": "CHECKED NOW (was absent r25 due to no Gamma totals coverage flag): exec +4.7c < 5c, "
               "worst +1.9c < +4c, var 6.5c > 6c cap. Triple fail. Not a candidate."},
]

near_misses = []
for match, kind, side, line, team in [
        (UNI, "total", "over", 2.5, None),
        (PFC, "team_total", "over", 1.5, "home"),
        (LIV, "ml", "away", None, None),
        (LIV, "team_total", "over", 1.5, "away"),
        (FRA, "ml", "away", None, None),
        (LYO, "ml", "away", None, None),
        (STR, "total", "under", 3.5, None)]:
    r = row(match, kind, side, line, team)
    if not r:
        continue
    failed = [k for k, v in r["checks"].items() if not v and k != "news_concordant"]
    near_misses.append({
        "match": match, "market": "%s %s %s%s" % (kind, side, ("L%s " % line) if line else "",
                                                  ("(%s)" % team) if team else ""),
        "p_med": r["p_med"], "p_range": [r["p_min"], r["p_max"]],
        "ask250": r["exec_ask_vwap250"], "exec_edge": r["exec_edge"],
        "exec_edge_haircut": r["exec_edge_haircut"],
        "worst_variant_edge": r["worst_variant_edge"], "var_spread": r["var_spread"],
        "liq": r["liq_gamma"], "failed_gates": failed})

out = {
    "scan": "soccer",
    "round": 26,
    "sub_scan": "B (EPL + Bundesliga + Ligue 1 + rest; Serie A/La Liga = sibling scan A)",
    "paper_only": True,
    "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "window_utc": d["window_utc"],
    "bankroll_usd": 12374.33,
    "cash_usd": 9488.68,
    "max_new_positions": 1,
    "stake_per_position": 250,
    "verdict": ("HONEST PASS - 0 of 399 gate rows (7 modelable fixtures, all full-match goal "
                "markets both directions) passed the frozen numeric gate set. No candidate; "
                "slot returned to the day's combined cap."),
    "candidates": [],
    "flagged": flagged,
    "near_misses": near_misses,
    "liv_ars_deep_check": {
        "kickoff": "2026-11-01T16:30:00Z (Understat + ESPN both confirm)",
        "model": {"lambda_home": 1.241, "lambda_away": 1.565, "lambda_total": 2.806,
                  "1x2": {"LIV": 0.2949, "DRAW": 0.2482, "ARS": 0.4501}},
        "books_devig": {"ML": "LIV ~32% / DRAW ~28.5% / ARS ~39% (Paddy Power 2.90/3.30/2.40)",
                        "OU25": "Under -109 / Over ~1.91 -> ~50/50 slight Under",
                        "BTTS": "Yes -156 / No +124 -> Yes ~58%"},
        "polymarket_vs_books": ("ML within ~1.6c (PM 34/29/38 vs books 32.4/28.5/39.1); O/U 2.5 PM "
                                "Over ask 50c vs books ~48-50% over; BTTS Yes 57c vs books ~58%. "
                                "Polymarket is efficient on the marquee."),
        "flags_ge_5c": ["Arsenal ML +7.0c (news-explained, worst/var fail)",
                        "Arsenal -1.5 spread +5.5c (flagged-only class)",
                        "Arsenal O1.5 +5.4c (worst/var fail, news worse)"],
        "conclusion": ("Model's Arsenal lean (45% vs market 38%) is xG-blind to the Saka/Saliba/"
                       "Madueke/Rice injury crisis; books and Polymarket agree with each other. "
                       "Nothing actionable >=5c survives gates.")},
    "recheck_items_from_brief": {
        "union_koln_O25": "Market EXISTS (id 5914650, liq $79.6k); Over 61.7% [58.9-65.4] vs ask "
                          "57c: exec +4.7c / worst +1.9c / var 6.5c - triple gate fail. Not flagged r25 "
                          "because r25's Gamma discovery missed this fixture's More Markets event; "
                          "now covered.",
        "frankfurt_hamburg": "All under-side edges +4.4..+5.2c fail worst-variant (-4.7..-6.4c); "
                             "O2.5 Over model 53.6% vs ask 50 - within noise. Nothing qualifies.",
        "ligue1_sunday_slate": "Second consecutive zero-qualifying-edge day for the Ligue 1 Sunday "
                               "slate; closest was PFC O1.5 (double 0.1-0.2c near-miss, news worse).",
        "lorient_brest": "Monday Nov 2 20:00Z - outside today's window, skipped per brief."},
    "library_adoption": {
        "package": "polymarket_alpha_lab.papersim @ repo 7b6cdd47",
        "selfcheck": "10/10 PASS (server venv python 3.12.3)",
        "used": ["xg.load_xg_snapshot", "xg.recent_form", "soccer_model.fixture_variants",
                 "soccer_model.match_lambdas", "soccer_model.median/over_probability/"
                 "team_total_over/cover_probability/both_teams_to_score",
                 "gates.walk_book (via evaluate_candidate)", "gates.evaluate_candidate",
                 "gates.under_risk_check", "gates.suspension_policy", "gates.GATES"],
        "friction": ("None blocking. Two gaps vs a full round pipeline: (1) the library has no "
                     "candidate builder for BTTS/team-total/ML sides (only candidate_from_variants "
                     "for O/U) - scan built gate-safe quote objects directly from fixture_variants "
                     "per-variant outputs, which usage.md endorses as the snapshot-driven variance "
                     "path; (2) Gamma market-question parsing is outside library scope (round "
                     "scripting). No fallback to round25 bespoke tools was needed. One scan-script "
                     "bug was found and fixed mid-scan (Gamma 'More Markets' sub-event suffix broke "
                     "team-name resolution for Koeln; 13-case parser test then clean re-run)."),
        "adoption_note": "candidates_from_variants not used because no O/U candidate reached the "
                         "gate-pass stage; pair-level over_under_quote intentionally NOT used."},
    "other_leagues_today": ("Gamma window also holds ~120 non-modelable events: EFL League One/Two "
                            "Sunday slates (15:00Z), esports, tennis ITF, German regional friendlies "
                            "- none have Understat xG coverage; recorded in scan_b.json fixtures "
                            "with modelable=false. No Serie A/La Liga events were modeled (sibling)."),
    "sources_note": ("Books/odds: ESPN DraftKings/Bet365 scoreboard (espn_fixtures_b.json), Paddy "
                     "Power/sportsgambler/FanDuel via web search. News: standard.co.uk, "
                     "lastwordonsports.com, sportsmole.co.uk, DFB-Pokal reports. All paper-only "
                     "research; no orders, no credentials."),
}
json.dump(out, open(OUT, "w"), indent=1)
print("patched news_checks into scan_b.json:", len(news_checks))
print("wrote", OUT)
print("candidates:", len(out["candidates"]), "| flagged:", len(flagged),
      "| near_misses:", len(near_misses))
