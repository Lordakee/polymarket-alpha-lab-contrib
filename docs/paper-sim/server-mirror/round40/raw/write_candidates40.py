"""Build round40/candidates.json from round40/raw/scan.json (r38 schema)."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round40/raw/scan.json"
VERIF = "/home/ubuntu/paper-sim/round40/raw/verify_markets.json"
OUT = "/home/ubuntu/paper-sim/round40/candidates.json"

d = json.load(open(SCAN))
board = d["board"]
verif = {v["id"]: v for v in json.load(open(VERIF))}


def row(mid):
    for r in board:
        if r["id"] == str(mid):
            return r
    raise SystemExit("row not found: %s" % mid)


def row_by(match, kind, side, line):
    for r in board:
        if (r.get("match") == match and r.get("kind") == kind
                and r.get("side") == side and r.get("line") == line):
            return r
    raise SystemExit("row not found: %s %s %s %s" % (match, kind, side, line))


def gate_row(r):
    fails = [k for k, v in r["checks"].items() if not v and k != "news_concordant"]
    return {
        "market_id": r["id"], "market_question": r["q"], "kind": r["kind"],
        "side": r["side"], "line": r["line"],
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
        "failed_checks": fails,
        "gamma_verified": (
            {"question": verif[r["id"]]["question"],
             "closed": verif[r["id"]]["closed"],
             "gameStartTime": verif[r["id"]]["gameStartTime"],
             "endDate": verif[r["id"]]["endDate"]}
            if r["id"] in verif else "not in verify set"),
    }


# rows for the killed/near-miss documentation
osasuna_tt05 = row(6180838)          # held #65 market family: numeric passer, entry barred
osasuna_ml = row(6179441)            # Osasuna ML home: var 8.29c
osasuna_tt15 = row(6180841)          # Osasuna TT O1.5: var 6.16c marginal
auxerre_no = row(6171231)            # Paris FC no-win: var 34.7c worst -9.6c
auxerre_home = row(6171223)          # Auxerre ML: var 28.5c worst -5.9c
psg_no = row(6171537)                # PSG no-win: var 12.0c
psg_troyes_o05 = row(6175541)        # Troyes TT O0.5: var 7.63c
psg_u25 = row(6175525)               # PSG TT U2.5: var 16.3c
forest_tt15 = row(6175546)           # Forest TT O1.5: var 19.7c worst +0.6c
forest_ml = row(6172022)             # Forest ML: var 22.1c
psg_btts = row_by("Paris Saint-Germain FC vs. ES Troyes AC", "btts", "yes", None)
parma_tt = max(
    [r for r in board if r.get("match") == "Parma Calcio 1913 vs. Bologna FC 1909"
     and r.get("kind") == "team_total" and r.get("exec_edge_haircut") is not None],
    key=lambda r: r["exec_edge_haircut"])
fortuna_o25 = row_by("Fortuna Sittard vs. Telstar 1963", "total", "over", 2.5)

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

killed = [
    {**gate_row(osasuna_tt05),
     "match": "CA Osasuna vs. Athletic Club", "league": "La_liga",
     "kill": ("HELD-FIXTURE / one-position-per-fixture: this IS held position "
              "#65 (same market id 6180838, entered $250 @ 0.6611). Dispatch "
              "rule: held fixtures are monitor marks, NO new positions. The "
              "row passes every numeric gate (net +9.3c, worst +7.6c, var "
              "4.46c, liq $21k, fill ok) - recorded as evidence the held "
              "position remains +EV per model, NOT as a new entry."),
     "news": ("WhoScored/Oddschecker/Sports Mole: tipsters predict 1-1 draw, "
              "cagey low-scoring game; 1-1 => Osasuna scores => TT O0.5 wins; "
              "CONCORDANT with the held YES-over side")},
    {**gate_row(osasuna_ml),
     "match": "CA Osasuna vs. Athletic Club", "league": "La_liga",
     "kill": ("variant spread 8.29c > frozen 6c bar (and same held fixture "
              "anyway); tipsters 1-1/draw or narrow Athletic win vs model "
              "Osasuna 40.2% - model-market divergence unexplained by news")},
    {**gate_row(osasuna_tt15),
     "match": "CA Osasuna vs. Athletic Club", "league": "La_liga",
     "kill": ("MARGINAL var 6.16c vs frozen 6.00c bar; also held fixture; "
              "1-1 predicted scoreline contradicts Osasuna scoring 2+ "
              "(scoreline-concordance r32 would also kill)"),
     "news": ("predicted 1-1 (WhoScored/Oddschecker) => Osasuna 1 goal => "
              "TT O1.5 OVER loses; scoreline-concordant kill")},
    {**gate_row(auxerre_no),
     "match": "AJ Auxerre vs. Paris FC", "league": "Ligue_1",
     "kill": ("variant spread 34.73c >> 6c AND worst variant -9.6c < +4c: "
              "10-variant model disagreement - Paris FC is a first-season "
              "Ligue 1 side (no 2025 Ligue 1 prior; same promoted-side "
              "fallback divergence class as ADO/Cambuur/Willem II in "
              "Eredivisie r39). Market prices Paris FC ~57% (-132) vs model "
              "38.8% win; tipsters split 0-1 Paris FC / 1-1 draw - news NOT "
              "concordant with the no-win side either"),
     "news": ("Paris FC 4th/17pts, betting favorite -132; predictions: 0-1 "
              "Paris FC win (kills away_no) or 1-1 draw (wins) - mixed, "
              "insufficient concordance")},
    {**gate_row(auxerre_home),
     "match": "AJ Auxerre vs. Paris FC", "league": "Ligue_1",
     "kill": "var 28.48c + worst -5.9c (promoted-side variant divergence, Paris FC)"},
    {**gate_row(psg_no),
     "match": "Paris Saint-Germain FC vs. ES Troyes AC", "league": "Ligue_1",
     "kill": ("var 11.99c > 6c. PSG rotation confirmed in previews (Safonov "
              "GK; Mayulu/Beraldo/Digne fringe starts) - genuine lineup "
              "uncertainty the variant spread is pricing; no entry"),
     "news": ("SportsGambler/WhoScored predicted XIs rotate PSG heavily "
              "(Safonov; fringe XI); prediction 'PSG win to nil' - the "
              "no-win side is news-CONTRARY")},
    {**gate_row(psg_troyes_o05),
     "match": "Paris Saint-Germain FC vs. ES Troyes AC", "league": "Ligue_1",
     "kill": "var 7.63c > 6c (Troyes promoted-side prior fallback divergence)",
     "news": "'PSG win to nil' predictions => Troyes 0 goals => O0.5 loses (news-contrary)"},
    {**gate_row(psg_u25),
     "match": "Paris Saint-Germain FC vs. ES Troyes AC", "league": "Ligue_1",
     "kill": "var 16.30c + worst +0.3c < +4c; PSG rotation uncertainty"},
    {**gate_row(psg_btts),
     "match": "Paris Saint-Germain FC vs. ES Troyes AC", "league": "Ligue_1",
     "kill": "var 6.57c > 6c and worst +3.3c < +4c; 'win to nil' predictions are BTTS-no side"},
    {**gate_row(forest_tt15),
     "match": "Nottingham Forest FC vs. Manchester City FC", "league": "EPL",
     "kill": ("var 19.72c + worst +0.6c < +4c; AND scoreline-concordance r32: "
              "published predictions 1-2 City and 4-0 City both give Forest "
              "<=1 goal => TT O1.5 loses"),
     "news": ("SportsGambler 1-2 City; SI/Goal consensus comfortable City "
              "win; Forest worst attack in division (6 goals), lost 4 of 5")},
    {**gate_row(forest_ml),
     "match": "Nottingham Forest FC vs. Manchester City FC", "league": "EPL",
     "kill": "var 22.13c + worst +0.3c; every preview picks City"},
    {**gate_row(parma_tt),
     "match": "Parma Calcio 1913 vs. Bologna FC 1909", "league": "Serie_A",
     "kill": ("var 7.57c > 6c; additionally kicks T-1.6h (<2h) so it would "
              "need confirmed lineups in the news check - no concordant "
              "lineup evidence gathered; timing kill stands regardless")},
    {**gate_row(fortuna_o25),
     "match": "Fortuna Sittard vs. Telstar 1963", "league": "Eredivisie",
     "kill": ("under-risk elevated exec bar: net +6.2c clears the normal +5c "
              "bar but the library flagged under-risk (no recent-form O2.5 "
              "evidence available for Eredivisie sides in this wiring, so "
              "o25_hits=0 -> conservative 8c net bar) and +6.2c < +8c; "
              "fixture also kicked 15:30Z, minutes after the board walk - "
              "post-kick at decision time regardless"),
     "note": ("best Championship/Eredivisie totals-family row of the scan; "
              "worst +4.2c and var 3.67c both passed - only the elevated "
              "under-risk exec bar killed it")},
]

held_marks = d["held_positions"]

out = {
    "round": 40,
    "scan": "soccer-12h-window-round40",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": {"lo": "2026-11-07T13:50:00Z", "hi": "2026-11-08T01:50:00Z"},
    "decision": (
        "ENTER NOTHING. $0 of the $600 round-40 new-entry budget. Exactly ONE "
        "row in the entire pre-kick board passes all frozen numeric gates "
        "(net>=+5c fee-aware, worst>=+4c, var<=6c, liq>=5k, fill_250, entry "
        ".10-.92): Osasuna team-total O0.5 (market 6180838) - and that row IS "
        "held position #65 itself (same market id, entered $250 @ 0.6611). "
        "The dispatch bars new positions on held fixtures and the "
        "one-position-per-fixture rule bars doubling the same market, so the "
        "passer is recorded as a favorable re-mark of the held position, not "
        "an entry. Every other positive-edge row dies on the frozen gates - "
        "overwhelmingly the 6c variant-spread bar (promoted-side prior "
        "fallback divergence: Paris FC/Troyes in Ligue 1, Telstar/ADO in "
        "Eredivisie) plus worst-variant failures and, for Forest-City, the "
        "r32 scoreline-concordance rule. If nothing passes, enter nothing."),
    "decision_rationale": (
        "Scan executed 15:22Z-15:47Z, mid-window: Serie A 14:00Z and "
        "Bundesliga 14:30Z games (incl. held #64 Mainz-Bayern) plus the entire "
        "15:00Z EPL/Championship slate were already post-kickoff -> modeled "
        "1X2 recorded for the report table, Gamma prices only, no gates, no "
        "entry. 866 in-window Gamma soccer events -> 41 league fixtures: 28 "
        "modeled (EPL 3, Championship 8, Bundesliga 5, La Liga 3, Serie A 5, "
        "Ligue 1 2, Eredivisie 3) + 13 board-only (Belgian 4, Scottish 4, "
        "Portuguese 3, Turkish 2; prices reported, no model coverage, no "
        "entry by rule). 700 gated rows on the 10 pre-kick modeled fixtures; "
        "1902 board rows total. Championship/Eredivisie kept totals-family-"
        "only (1X2 ineligible per gate-E/first-run rule); Big-5 ran full "
        "families with MW $150 deprioritized; spreads flagged-only; no "
        "cross-league pair occurred (all 28 fixtures domestic), and the "
        "check_cross_league_mw + CROSS_LEAGUE_ML_CLASS wiring is in the scan "
        "script per DELIVERY_PLAN section 72 (exercised only if a cross pair "
        "appears). xG bases: Big-5 pointer fresh through Nov-2 (no Big-5 "
        "games Nov 3-5), Championship through Nov-3 with the known 6-club "
        "Nov-4 staleness (Cardiff, West Ham, Wrexham, Middlesbrough, Bristol "
        "City, Wolves - affects 3 of the 8 post-kick 15:00Z Championship "
        "fixtures only, flagged, none passes gates regardless), Eredivisie "
        "fresh through Nov-6 19:00Z. Library selfcheck PASS 10/10 at repo "
        "1a2760bc re-run before modeling; 11 candidate/near-miss market ids "
        "Gamma-verified via /markets/{id} (ids= list param avoided - broken "
        "per r39); all closed=false with endDate at kickoff. Budget intact: "
        "$600 untouched, $1,700 soccer headroom preserved, >=$1,100 UCL/UEL "
        "reserve preserved for Nov 10-12."),
    "max_new_positions": 0,
    "positions_used": 0,
    "stake_per_position_usd": None,
    "total_stake_usd": 0,
    "budget": {"round_max_new_entries_usd": 600, "used_usd": 0,
               "soccer_pool_usd": 3000, "headroom_usd": 1700,
               "ucl_uel_reserve_usd": ">=1100 (Nov 10-12)"},
    "bankroll_usd": None,
    "bankroll_note": ("not provided in this dispatch; pool accounting per "
                      "brief: soccer pool $3,000, $1,700 headroom"),
    "open_positions_note": (
        "held per dispatch: #64 Mainz-Bayern BTTS YES $250 @0.6578 (kicked "
        "14:30Z, in-play at scan), #65 Osasuna TT O0.5 $250 @0.6611 (17:30Z), "
        "#66 Valencia-RealMadrid U3.5 $250 @0.56 (20:00Z); #67/#68/#63 Sunday "
        "- outside window, ignored"),
    "new_candidates": [],
    "killed_candidates": killed,
    "held_position_marks": {
        "64_mainz_bayern_btts_yes": {
            "market_id": 6176123, "entry": "$250 @ 0.6578",
            "kickoff_utc": "2026-11-07T14:30:00Z",
            "status_at_scan": "IN-PLAY (~55 min elapsed)",
            "gamma_prices": {"Yes": 0.484, "No": 0.516},
            "clob_at_scan": {"yes_bid": 0.462, "yes_ask": 0.469,
                             "yes_bid_depth_shares": 180949,
                             "yes_ask_depth_shares": 107550},
            "mark_to_bid_vs_entry_c": round(100 * (0.462 - 0.6578), 2),
            "note": ("mark-to-bid -19.6c; deep two-sided book ($180k/$107k "
                     "shares); game live - BTTS still resolvable")},
        "65_osasuna_tt_o05": {
            "market_id": 6180838, "entry": "$250 @ 0.6611",
            "kickoff_utc": "2026-11-07T17:30:00Z",
            "status_at_scan": "pre-kick T-2.1h",
            "gamma_prices": {"Over": 0.635, "Under": 0.365},
            "clob_at_scan": {"over_bid": 0.63, "over_ask": 0.64,
                             "over_bid_depth_shares": 21440,
                             "over_ask_depth_shares": 30919},
            "mark_to_bid_vs_entry_c": round(100 * (0.63 - 0.6611), 2),
            "model_at_scan": {"p_med": 0.7547, "p_min": 0.726, "p_max": 0.7706,
                              "net_edge_vs_ask_c": 9.34},
            "note": ("mark-to-bid -3.1c but model median 0.755 vs ask 0.6499 "
                     "(+9.3c net) - held position looks +EV; news concordant "
                     "(predicted 1-1 => Osasuna scores); T-2h recheck: drop "
                     "confidence only if Osasuna XI loses both Garcia and "
                     "Gomez or Athletic rest their front line to a degree "
                     "that turns the game one-sided)")
        },
        "66_valencia_rm_u35": {
            "market_id": 6180689, "entry": "$250 @ 0.56 (UNDER 3.5)",
            "kickoff_utc": "2026-11-07T20:00:00Z",
            "status_at_scan": "pre-kick T-4.6h",
            "gamma_prices": {"Over": 0.425, "Under": 0.575},
            "clob_at_scan": {"under_bid": 0.57, "under_ask": 0.58,
                             "under_bid_depth_shares": 85321,
                             "under_ask_depth_shares": 74484},
            "mark_to_bid_vs_entry_c": round(100 * (0.57 - 0.56), 2),
            "model_at_scan": {"p_med_under35": None,
                              "note": ("held fixture rows were report-only "
                                       "(no gate walk); report-table model: "
                                       "Valencia-RM lam 1.26/1.81, 1X2 "
                                       "0.27/0.23/0.50")},
            "note": ("mark-to-bid +1.0c; deep book ($85k bid shares); "
                     "T-2h recheck at ~18:00Z with Real Madrid XI news")},
    },
    "board_only_leagues": {
        "leagues": ["Belgian Pro League (4)", "Scottish Premiership (4)",
                    "Primeira Liga (3)", "Turkish Super Lig (2)"],
        "policy": ("NO MODEL COVERAGE - prices reported only, no entry "
                   "(dispatch rule); top board liquidity: Goztepe-Basaksehir "
                   "$110k ML, CD Nacional-Academico $98k, Galatasaray-Amed "
                   "$90k ML, Sporting-Moreirense $49k"),
    },
    "news_concordance": {
        "osasuna_athletic": {
            "verdict": "CONCORDANT with held #65 Over side (1-1 predicted)",
            "findings": [
                "tipsters predict 1-1 draw, cagey low-scoring game (WhoScored/Oddschecker/Sports Mole)",
                "Athletic unbeaten last 5 H2H (W2 D3); under 2.5 in last 4 meetings",
                "market ~47% Athletic win; Osasuna 15th on 11 pts",
                "predicted XIs published (4-2-3-1 both); official XIs T-1h",
            ],
            "sources": [
                "https://www.whoscored.com/matches/1994015/preview/spain-laliga-2026-2027-osasuna-athletic-club",
                "https://www.oddschecker.com/us/picks-parlays/soccer/cng201-20261107-osasuna-vs-athletic-bilbao-lineups-prediction-betting-picks-odds",
                "https://www.fotmob.com/matches/athletic-club-vs-osasuna/2aw50s",
            ],
        },
        "auxerre_paris_fc": {
            "verdict": "NOT CONCORDANT with the killed away_no candidate",
            "findings": [
                "Paris FC 4th (17 pts), betting favorite -132 (~57% implied) vs model 38.8% win",
                "predictions split: 0-1 Paris FC win / 1-1 draw; Auxerre unbeaten in 8 of last 9 home",
                "Paris FC first-season Ligue 1 side -> promoted-side prior fallback = the 34.7c variant spread that killed all Auxerre/ParisFC rows",
            ],
            "sources": ["Ligue 1 previews via web search (statistical/H2H prediction sites)"],
        },
        "psg_troyes": {
            "verdict": "CONTRARY to no-win/btts-yes candidates (rotation uncertainty)",
            "findings": [
                "PSG predicted to rotate: Safonov GK, Mayulu/Beraldo/Digne fringe starts (multiple previews)",
                "common prediction: PSG win to nil (kills Troyes O0.5 and btts yes)",
                "official XIs T-1h; variant spread 7.6-16.3c on Troyes/PSG totals rows is pricing exactly this",
            ],
            "sources": ["SportsGambler/WhoScored PSG-Troyes previews via web search"],
        },
        "forest_mancity": {
            "verdict": "CONTRARY to Forest-side candidates (scoreline-concordance kill)",
            "findings": [
                "predicted 1-2 City (SportsGambler) and 4-0 City (pundit); consensus comfortable City win",
                "Forest worst attack in the division (6 goals), lost 4 of last 5",
                "both published scorelines give Forest <=1 goal -> Forest TT O1.5 dies on r32 scoreline-concordance in addition to var 19.7c",
            ],
            "sources": [
                "https://www.sportsgambler.com/betting-tips/football/nottingham-forest-vs-manchester-city-prediction-lineups-odds-2026-11-07",
                "https://www.si.com/soccer/nottingham-forest-vs-man-city-preview-predictions-lineups-11-7-26",
                "https://www.goal.com/en-us/betting/tips/nottingham-forest-vs-manchester-city-predictions-11-7-2026/A%3Ablt69eb91c8a9aff838",
            ],
        },
    },
    "data_quality_flags": {
        "scan_execution_timing": (
            "window opened 13:50Z; board walked 15:22-15:47Z: 18 of 41 "
            "fixtures already kicked (Serie A 14:00 x2, Bundesliga 14:30 x4 "
            "incl. held #64, EPL/Championship/Scottish/Belgian 15:00 x10, La "
            "Liga 15:15, Eredivisie 15:30) -> those are report-only boards; "
            "gates ran only on the 10 genuinely pre-kick modeled fixtures + "
            "post-kick Fortuna-Telstar walked at T-4min (moot)"),
        "championship_staleness": (
            "6 clubs 1-game stale (Nov-4 midweek round missing from FotMob "
            "snapshot thru Nov-3): Cardiff, West Ham, Wrexham, Middlesbrough, "
            "Bristol City, Wolves; Saturday impact limited to post-kick "
            "15:00Z fixtures (Blackburn-West Ham, Cardiff-Burnley, "
            "Watford-Middlesbrough); all flagged; none passes gates"),
        "eredivisie_promoted_sides": (
            "as predicted by the dispatch: Telstar (Fortuna match) and ADO "
            "den Haag rows show the promoted-side fallback divergence; best "
            "Eredivisie totals row Fortuna-Telstar O2.5 +6.2c net dies on "
            "the conservative under-risk 8c exec bar (no O2.5 form evidence "
            "for Eredivisie in this wiring); ADO-Sparta best ELIGIBLE row "
            "(O0.5 over) was flat at -0.2c net - the +3.1c row was a spread "
            "(flagged-only, never enterable)"),
        "ligue1_promoted_sides_new": (
            "same divergence class newly visible in Ligue 1: Paris FC and "
            "Troyes (first-season sides) produce 7.6c-34.7c variant spreads "
            "on Auxerre-ParisFC and PSG-Troyes; every big net edge on those "
            "two fixtures is variant-spread killed"),
        "held_detection_postfix": d.get("held_detection_patch"),
        "cardiff_burnley_market_gap": (
            "Gamma carries only ML + spread markets for Cardiff-Burnley "
            "(12 rows) - same r38 gap"),
        "womens_fixtures": "none detected in this window's league set",
    },
    "cross_league_wiring": (
        "no cross-league pair in the 28 modeled fixtures (all domestic); "
        "gates.check_cross_league_mw + risk_policy CROSS_LEAGUE_ML_CLASS "
        "wired in scan40.py per DELIVERY_PLAN section 72 and would enforce "
        "bridge_present + worst>=+5c at $150 marginal sizing if a cross pair "
        "appeared; kappa table covers Big-5 only"),
    "library": {
        "package": "polymarket_alpha_lab.papersim",
        "repo_commit": "1a2760bc",
        "selfcheck": "PASS 10/10 (re-run 2026-11-07 ~15:1xZ pre-modeling)",
        "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
        "fee_model": ("evaluate_candidate(fee_rate=FEE_RATE_SPORTS=0.05); "
                      "exec bar NET of fee at walked price; worst-variant "
                      "stays gross"),
    },
    "scan_source": "/home/ubuntu/paper-sim/round40/raw/scan.json",
    "scan_artifacts": {
        "raw_board": "/home/ubuntu/paper-sim/round40/raw/scan.json",
        "events_window": "/home/ubuntu/paper-sim/round40/raw/events_window_40.json",
        "espn_fixtures": "/home/ubuntu/paper-sim/round40/raw/espn_fixtures_40.json",
        "market_verifications": "/home/ubuntu/paper-sim/round40/raw/verify_markets.json",
        "enum_script": "/home/ubuntu/paper-sim/round40/raw/enum40.py",
        "scan_script": "/home/ubuntu/paper-sim/round40/raw/scan40.py",
        "scan_log": "/home/ubuntu/paper-sim/round40/raw/scan40.log",
    },
}
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("decision:", out["decision"][:110])
print("positions_used:", out["positions_used"],
      "killed documented:", len(killed))
