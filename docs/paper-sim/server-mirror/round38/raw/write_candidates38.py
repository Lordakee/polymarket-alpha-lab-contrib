"""Build round38/epl_champ_candidates.json from round38/raw/epl_champ_scan.json."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round38/raw/epl_champ_scan.json"
OUT = "/home/ubuntu/paper-sim/round38/epl_champ_candidates.json"
d = json.load(open(SCAN))
board = d["board"]


def row(mid, side, kind, line):
    for r in board:
        if (r["id"] == str(mid) and r["side"] == side
                and r["kind"] == kind and r["line"] == line):
            return r
    raise SystemExit("row not found: %s %s %s %s" % (mid, side, kind, line))


mv = row(6237007, "away_no", "ml", None)      # ManUtd-Villa: Villa no-win
ars_u15 = row(6175988, "under", "team_total", 1.5)   # Arsenal TT U1.5
ars_draw = row(6171515, "draw", "ml", None)          # Arsenal-Hull draw
preston = row(6172011, "home", "ml", None)           # Preston ML home
palace = row(6236266, "away_no", "ml", None)         # Palace-Liverpool divergence
ars_o05a = row(6176002, "over", "team_total", 0.5)   # Hull TT O0.5
ars_u25 = row(6175990, "under", "team_total", 2.5)   # Arsenal TT U2.5 marginal var
mun_home = row(6237004, "home", "ml", None)          # ManUtd ML home marginal var
sun_o25 = row(6239719, "over", "total", 2.5)         # Sunderland-Chelsea O2.5
wat_u25 = row(6185126, "under", "total", 2.5)        # Watford-Middlesbrough U2.5
blb_u15 = row(6185239, "under", "team_total", 1.5)   # Blackburn-West Ham TT U1.5

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
shares = round(150 / 0.70, 2)
gross_ev = round(shares * (0.7806 - 0.70), 2)
fee_total = round(shares * 0.0105, 2)

out = {
    "round": 38,
    "scan": "soccer-weekend-epl-championship",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": {"lo": "2026-11-06T11:00:00Z", "hi": "2026-11-08T23:59:59Z"},
    "decision": (
        "1 of max 3 candidates entered: ManUtd-Villa match_winner NO "
        "(Villa will not win) $150 @ 0.70 ask-VWAP. The other three EPL/"
        "Championship numeric passers are KILLED at the news-concordance "
        "stage: Arsenal TT U1.5 and Arsenal-Hull draw die on the r32 "
        "scoreline-concordance rule (only published scoreline = Sportsmole "
        "2-0 Arsenal, which contradicts both); Preston ML home dies on "
        "universal contrary previews (SportyTrader Preston win ~14.9% vs "
        "model 29.1%; every preview picks Southampton) compounded by the "
        "Championship 1X2 gate-E limitation."),
    "decision_rationale": (
        "Full-weekend fee-aware scan of the 20-fixture EPL+Championship slate "
        "(3168 board rows across all leagues; EPL/Championship rows = full "
        "both-directions O/U + BTTS + TT + MW board). EPL xG base fully fresh "
        "(18/18 clubs; no EPL games Nov-3..5). Championship FotMob fresh "
        "through Nov-3 with 9/9 Nov-3 midweek games verified IN, but the "
        "Nov-4 midweek round is missing -> 6 clubs 1-game stale "
        "(Cardiff, West Ham, Wrexham, Middlesbrough, Bristol City, Wolves), "
        "affecting 5 of 11 Saturday Championship fixtures; all stale-fixture "
        "rows carry STALE-XG flags and none of them passes gates anyway. "
        "Exactly 4 EPL/Championship rows pass all frozen numeric gates "
        "(net>=+5c fee-aware, worst>=+4c, var<=6c, liq>=5k, fill_250, entry "
        ".10-.92). Only the ManUtd-Villa away_no survives news-concordance "
        "with a concordant predicted scoreline (2-2, kickoff.co.uk betting "
        "preview) and Villa's injury list (Baleba, Onana, Ruggeri out; Cash "
        "suspended; Wan-Bissaka doubt) supporting Villa no-win at 0.70 "
        "(model 0.781, worst-variant 0.757). Note one contrary external "
        "signal (one stats site lists Villa win ~37% vs model 21.9%) "
        "recorded in the news audit. Entry is T-53h pre-kick with XIs "
        "unset: flagged for a T-2h re-check (drop rule if Villa XI "
        "strengthens materially)."),
    "max_new_positions": 3,
    "positions_used": 1,
    "stake_per_position_usd": 250,
    "mw_stake_usd": 150,
    "weekend_budget_note": ("weekend total across ALL agents <= $1,500; this "
                            "sub-scan uses $150 of it (1 MW candidate at the "
                            "deprioritized stake)"),
    "bankroll_usd": 13409.00,
    "cash_usd": 11923.00,
    "open_positions": 5,
    "open_positions_note": ("per coordinator brief: 5 open = #62 soccer "
                            "(Alaves TT O0.5, kicks Nov-6 20:00Z, different "
                            "slate, no overlay here) + 4 non-soccer"),
    "new_candidates": [
        {
            "rank": 1,
            "id": 63,
            "match": "Manchester United FC vs. Aston Villa FC",
            "fixture_key": "astonvilla-manchesterunited",
            "comp": "EPL",
            "kickoff_utc": "2026-11-08T16:30:00Z",
            "market": "Will Aston Villa FC win on 2026-11-08? (id 6237007)",
            "side_bought": "NO (Villa does not win; ManUtd win or draw)",
            "kind": "ml",
            "policy": "ELIGIBLE-DEPRIORITIZED (domestic match_winner, $150)",
            "entry_ask_vwap": 0.70,
            "best_bid_at_scan": 0.69,
            "stake_usd": 150,
            "shares": shares,
            "fee_per_share": 0.0105,
            "fee_total_usd": fee_total,
            "expected_value_gross_usd": gross_ev,
            "expected_value_net_usd": round(gross_ev - fee_total, 2),
            "model_p": {"median": 0.7806, "min": 0.7570, "max": 0.7941,
                        "n_variants": 10},
            "edge": {"net_haircut_c": 7.01, "gross_c": 8.06,
                     "worst_variant_c": 5.70, "var_spread_c": 3.71},
            "liquidity_gamma_usd": 50288.70,
            "depth_2c_shares": 11066,
            "fill_250": True,
            "model_1x2": {"H": 0.5661, "D": 0.2106, "A": 0.2194},
            "lambdas": {"home": 2.069, "away": 1.253},
            "news_audit": {
                "verdict": "CONCORDANT (with one contrary win-prob source noted)",
                "for": [
                    "predicted 2-2 draw (kickoff.co.uk / betting preview) -> Villa does not win",
                    "Villa OUT: Baleba (hamstring, late Nov), Onana, Ruggeri; Cash suspended; Wan-Bissaka doubt",
                    "ManUtd H2H dominance: 38/56 PL home-era meetings won",
                ],
                "against": [
                    "one stats site lists Villa win ~37% vs model 21.9% (United 17th on 7 pts poor run)",
                    "ManUtd missing Shaw, Ugarte (doubt), Sesko",
                ],
                "sources": [
                    "https://www.rotowire.com/soccer/article/man-united-vs-aston-villa-prediction-predicted-lineups-team-news-145469",
                    "https://www.sportsmole.co.uk/football/man-utd/injury-news/injuries-and-suspensions/baleba-dorgu-sesko-rashford-latest-man-united-injury-suspension-list-vs-villa_608456.html",
                    "https://www.kickoff.co.uk/english-premier-league-predictions-stats-odds/man-united-vs-aston-villa",
                ],
            },
            "entry_flags": [
                "MW eligible-deprioritized; $150",
                "T-53h pre-kick (XIs unset; ~1h pre-kick drop)",
            ],
            "post_entry_plan": (
                "paper entry at scan reference 0.70; re-check at T-2h "
                "(~14:30Z Nov-8): if Villa XI strengthens materially "
                "(Baleba/Onana surprise return) or bid < 0.60, mark for "
                "paper exit at bid; mark-to-market at best bid otherwise"),
        }
    ],
    "killed_candidates": [
        {
            "match": "Arsenal FC vs. Hull City AFC",
            "market": "Arsenal FC O/U 1.5 - UNDER (id 6175988)",
            "side": "UNDER (Arsenal scores <= 1)",
            "kind": "team_total", "stake_would_be": 250,
            "edge": {"net_haircut_c": 10.74, "worst_variant_c": 9.06,
                     "var_spread_c": 5.67},
            "ask_vwap": 0.2498, "p_med": 0.3666, "liq_gamma_usd": 7390,
            "kill": ("r32 scoreline-concordance: only published scoreline "
                     "(Sportsmole) is Arsenal 2-0 -> contradicts UNDER 1.5; "
                     "nuance recorded: Saka OUT + Dowman suspended cut "
                     "Arsenal scoring, which is pro-UNDER, but the "
                     "mechanical rule kills on the published scoreline"),
            "sources": [
                "https://www.sportsmole.co.uk/football/arsenal/preview/arsenal-vs-hull-city-prediction-team-news-lineups_608461.html",
            ],
        },
        {
            "match": "Arsenal FC vs. Hull City AFC",
            "market": "Will Arsenal FC vs. Hull City AFC end in a draw? (id 6171515)",
            "side": "YES (draw)",
            "kind": "ml", "stake_would_be": 150,
            "edge": {"net_haircut_c": 6.68, "worst_variant_c": 5.33,
                     "var_spread_c": 4.03},
            "ask_vwap": 0.12, "p_med": 0.1921, "liq_gamma_usd": 113602,
            "kill": ("r32 scoreline-concordance: Sportsmole predicts 2-0 "
                     "Arsenal (no draw); also near-perfectly correlated with "
                     "the killed Arsenal TT U1.5"),
        },
        {
            "match": "Preston North End FC vs. Southampton FC",
            "market": "Will Preston North End FC win on 2026-11-07? (id 6172011)",
            "side": "YES (Preston win)",
            "kind": "ml", "stake_would_be": 150,
            "edge": {"net_haircut_c": 8.06, "worst_variant_c": 6.80,
                     "var_spread_c": 5.81},
            "ask_vwap": 0.2023, "p_med": 0.2910, "liq_gamma_usd": 10729,
            "kill": ("news kill: every published preview picks Southampton "
                     "(SportyTrader Preston win ~14.9% vs model 29.1%; "
                     "Forebet Preston 24th vs Southampton 7th; Preston "
                     "winless in last 3 at Deepdale) + Championship 1X2 "
                     "gate-E limitation (relegated-EPL fallback clubs "
                     "distort 1X2 on FotMob data)"),
            "sources": [
                "https://www.sportytrader.com/en/betting-tips/preston-north-end-southampton-385468",
                "https://www.forebet.com/en/football/matches/preston-north-end-southampton-2507188",
                "https://www.sportsgambler.com/betting-tips/football/preston-vs-southampton-prediction-lineups-odds-2026-11-07",
            ],
        },
    ],
    "flagged_not_enterable": [
        {"match": "Crystal Palace FC vs. Liverpool FC",
         "market": "Will Liverpool FC win? NO (id 6236266)",
         "edge": {"net_c": 20.14}, "var_spread_c": 14.89,
         "flag": ("huge model-market divergence: model Liverpool win 39.7% "
                  "vs market ~61%; fails var<=6c. Watch, do not enter; "
                  "Mateta suspended (Palace) already in market?")},
        {"match": "Arsenal FC vs. Hull City AFC",
         "market": "Hull City O/U 0.5 - OVER (id 6176002)",
         "edge": {"net_c": 13.80}, "var_spread_c": 13.59,
         "flag": "model-agreement failure (variants disagree); Hull missing 7 players"},
        {"match": "Arsenal FC vs. Hull City AFC",
         "market": "Arsenal FC O/U 2.5 - UNDER (id 6175990)",
         "edge": {"net_c": 12.32}, "var_spread_c": 6.08,
         "flag": "MARGINAL: var 6.08c vs frozen 6.00c bar; also same Arsenal-score direction as killed U1.5"},
        {"match": "Manchester United FC vs. Aston Villa FC",
         "market": "Will ManUtd win? YES (id 6237004)",
         "edge": {"net_c": 10.37}, "var_spread_c": 6.29,
         "flag": "MARGINAL var fail; near-perfectly correlated with entered away_no"},
        {"match": "Sunderland AFC vs. Chelsea FC",
         "market": "O/U 2.5 - OVER (id 6239719)",
         "edge": {"net_c": 6.70}, "var_spread_c": 12.84,
         "flag": "var fail"},
        {"match": "Watford FC vs. Middlesbrough FC",
         "market": "O/U 2.5 - UNDER (id 6185126)",
         "edge": {"net_c": 5.89}, "var_spread_c": 27.13,
         "flag": "var fail + worst -4.0c; Middlesbrough STALE (Nov-4 game missing)"},
        {"match": "Blackburn Rovers FC vs. West Ham United FC",
         "market": "West Ham O/U 1.5 - UNDER (id 6185239)",
         "edge": {"net_c": 12.92}, "var_spread_c": 42.18,
         "flag": "massive var fail + worst -12.8c + West Ham STALE; liq only $1.7k"},
        {"match": "Arsenal FC vs. Hull City AFC",
         "market": "spread rows (e.g. Arsenal -1.5 nocover +17.8c net)",
         "flag": "spreads are FLAGGED-ONLY by policy (blowout-tail rule); never entered"},
    ],
    "data_quality_flags": {
        "championship_staleness": (
            "6 Championship clubs missing exactly the Nov-4 midweek round "
            "(Cardiff, West Ham, Wrexham, Middlesbrough, Bristol City, "
            "Wolves): FotMob snapshot fresh through Nov-3 only. Affects "
            "Bristol-Norwich, Wrexham-Wolves, Cardiff-Burnley, "
            "Blackburn-West Ham, Watford-Middlesbrough (all STALE-XG "
            "flagged; none passes gates regardless)"),
        "womens_match_leak": (
            "Gamma soccer events included two WOMEN'S fixtures that "
            "name-resolved to men's clubs: Chelsea-Everton 12:45Z Nov-7 "
            "(event 1300005) and Aston Villa WFC vs Manchester United WFC "
            "12:00Z Nov-8 (event 1300013). EXCLUDED from the mandate table "
            "(men's EPL slate confirmed against ESPN)."),
        "cardiff_burnley_market_gap": (
            "Gamma carries only ML + spread markets for Cardiff-Burnley "
            "(no O/U, BTTS or TT listings) -> odds board for that fixture "
            "is ML-only"),
        "fixture_count": (
            "brief said 15 games; ESPN enumeration found 20 (4 EPL Sat + 5 "
            "EPL Sun + 11 Championship Sat + 0 Championship Sun); all 20 "
            "modeled"),
    },
    "marquee_game_news": {
        "Arsenal FC vs. Hull City AFC (Nov-7 15:00Z)": {
            "arsenal": "Saka OUT (thigh), Dowman SUSPENDED (red-card ban, 2 left); Saliba returned to squad; Konsa doubt; Gyokeres/Havertz lead line",
            "hull": "7 out: Crooks (susp), Matazo (ACL), Targett, Gourna-Douath, Ansah, Gyabi, Hughes + Morita (groin, new); Butland may return; 5-4-1 low block expected",
            "prediction": "Sportsmole 2-0 Arsenal",
            "model": "1X2 0.67/0.19/0.13; lambda 2.15/0.86",
        },
        "Nottingham Forest FC vs. Manchester City FC (Nov-7 17:30Z)": {
            "manchester_city": "2nd place, 21 pts; beat RB Leipzig 2-3 in Europe midweek (Maresca); no fresh injury flags found",
            "nottingham_forest": "no specific injury flags found in searches",
            "prediction": "no scoreline published in fetched sources",
            "model": "1X2 0.30/0.23/0.46; lambda 1.40/1.80; O2.5 model 0.622 vs ask 0.59 (+1.9c, no passer)",
        },
        "Manchester United FC vs. Aston Villa FC (Nov-8 16:30Z)": {
            "manchester_united": "Shaw OUT, Ugarte OUT/doubt (hamstring), Sesko OUT (knee)",
            "aston_villa": "Baleba OUT (hamstring, late Nov), Onana OUT, Ruggeri OUT, Cash SUSPENDED, Wan-Bissaka doubt",
            "prediction": "2-2 draw (kickoff.co.uk betting preview); KickOff algo: 80% 2+ goals, BTTS tipped",
            "model": "1X2 0.57/0.21/0.22; lambda 2.07/1.25",
        },
        "Crystal Palace FC vs. Liverpool FC (Nov-8 14:00Z)": {
            "crystal_palace": "Mateta SUSPENDED (3-match ban, red card upheld), Riad OUT (ACL), Woodman doubt",
            "liverpool": "Frimpong OUT (hamstring), Ekitike OUT, Bradley OUT, Leoni OUT",
            "prediction": "no current scoreline found; prior-season H2H 3-1 Liverpool",
            "model": "1X2 0.36/0.23/0.40; model far below market on Liverpool win (39.7% vs ~61%) - flagged divergence",
        },
    },
    "library": d["library"],
    "scan_source": "round38/raw/epl_champ_scan.json",
    "selfcheck": "PASS 10/10 at repo 5bdae2e3 (re-run 2026-11-06 ~10:55Z)",
}
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("decision:", out["decision"][:120])
print("positions_used:", out["positions_used"], "stake:", sum(
    c["stake_usd"] for c in out["new_candidates"]))
