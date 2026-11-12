"""Round-31 candidates file writer (paper-only). Verdict: honest pass."""
import json
from datetime import datetime, timezone

OUT = "/home/ubuntu/paper-sim/round31/soccer_candidates.json"
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

doc = {
    "scan": "soccer",
    "round": 31,
    "sub_scan": ("ALL-SOCCER-EXCEPT-UCL-WEDNESDAY; entry window Nov-3 "
                 "16:00Z..Nov-5 16:00Z (48h); UCL Wed slate is r30-owned, "
                 "rechecked with fresh books; Championship/MLS/cups/UEL-Thu "
                 "inventoried"),
    "paper_only": True,
    "generated_utc": now,
    "window_utc": {
        "lo": "2026-11-03T16:00:00Z",
        "hi": "2026-11-05T16:00:00Z",
        "note": ("entry-placement window; Thursday-evening UEL/UECL/Argentina/"
                 "Brazil kickoffs fall 1.75-8.5h after hi - entries placed at "
                 "scan time are ~25-32h pre-kickoff and carry that fragility"),
    },
    "understat_status": {
        "recovered": False,
        "r28_snapshot_published": False,
        "cron_status_at_run": ("2026-11-03T16:00:12Z refresh_failed "
                               "(curl 28: connect timeout to understat.com:443)"),
        "http_probe_at_run": "000 after 12.0s (read-only; cron owns recovery)",
        "xg_base": ("/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json "
                    "(fresh through Sat Oct-31)"),
        "eng2_coverage_verdict": (
            "NOT COVERED. Understat universe = Big-5 only "
            "(EPL/La_liga/Serie_A/Bundesliga/Ligue_1). eng.2 absent; all six "
            "probe clubs (Cardiff/West Ham/Wrexham/Middlesbrough/Bristol "
            "City/Wolves) canon=None. Per the task brief's own fallback rule, "
            "the 'Championship domestic pairs -> standard 10-variant path' "
            "hypothesis is VOID at the data layer: model-void, prices only."),
    },
    "library": {
        "package": "polymarket_alpha_lab.papersim",
        "repo_commit": "7b6cdd47",
        "selfcheck": "10/10 PASS (re-run this session before the scan)",
        "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
    },
    "bankroll_usd": 12841.14,
    "cash_usd": 10355.49,
    "max_new_positions": 3,
    "stake_per_position_usd": 250,
    "verdict": (
        "HONEST PASS - 0 candidates. 134 soccer fixtures with Polymarket "
        "markets in the discovery range (Nov-3 16:00Z..Nov-6 09:00Z); 12 "
        "Championship games (9 Tue + 3 Wed) are MODEL-VOID (eng.2 outside the "
        "Understat Big-5 universe - the brief's domestic-pair hypothesis "
        "fails at the data layer; full gamma price boards captured, no "
        "model, no gates). 11 fixtures modelable, ALL cross-league Big-5 "
        "pairs (4 Tue UCL recheck + 3 Wed UCL recheck + 3 Thu UEL + 1 Thu "
        "UECL): totals/BTTS/TT only via the r7/r8 30-variant path, MW/spread "
        "banned. Corrected board 770 rows: ZERO enterable rows passed the "
        "frozen gates. The 6 numeric passers are all BANNED MW/spread rows "
        "(Leipzig-City ML family exec +8..+27c; Lens-Como spread +12c) - the "
        "same structural false-edge pattern round-30 flagged. Every "
        "allowed-kind row fails var<=6c (observed spreads 7.4-38c, median "
        "~21c) - the r29/r30 structural finding now confirmed on a THIRD "
        "slate (UEL/UECL Thursday included). One canon false-positive caught "
        "and voided post-scan (AZ->Lazio substring; AZ-Juventus is no-data "
        "Eredivisie-vs-Serie-A, not a domestic derby). 3 x $250 budget "
        "unspent."),
    "candidates": [],
    "near_misses": [
        {
            "match": ("Bayer 04 Leverkusen vs. Olympique de Marseille "
                      "(UEL MD4, Nov-5 20:00Z - post-window kickoff, entry "
                      "~28h pre-kick)"),
            "market": "BTTS Yes (id 6091589)",
            "numbers": ("p_med 0.774 [0.710-0.843], bid/ask 0.56/0.58, "
                        "ask250 0.580, exec +19.4c, worst +13.0c, var 13.4c, "
                        "liq $20.6k, fill_250 yes"),
            "failed_gates": ["var<=6c"],
            "news_concordance_if_overridden": (
                "WEAK-CONTRADICTED - previews: Leverkusen -270 favorites, "
                "3/3 UEL wins, predicted 3-1; tipster BTTS-yes ~1.65 "
                "(implied ~61%) vs model 0.774 - the model's 4.46-goal "
                "lambda total is the cross-league averaging artifact "
                "(Bundesliga+Ligue_1 bases averaged, boosts 0/10/20%); the "
                "market's 0.58 is in line with the tipsters. Model edge is "
                "structural, not informational."),
            "sources": ["footballwhispers.com prediction 3-1",
                        "goonersguide.com BTTS ~1.65",
                        "FanDuel -270/+550",
                        "m.dongqiudi.com Leverkusen 3/3 UEL wins"],
        },
        {
            "match": "RB Leipzig vs. Manchester City FC (UCL MD4, Nov-4 20:00Z; r30 near-miss repeat)",
            "market": "RB Leipzig team total O1.5 Over (id 6053970)",
            "numbers": ("p_med 0.645 [0.562-0.771], bid/ask 0.35/0.37, "
                        "ask250 0.379, exec +26.6c (was +26.5c r30), worst "
                        "+18.2c, var 21.0c, liq $9.3k, fill_250 yes"),
            "failed_gates": ["var<=6c"],
            "news_concordance_if_overridden": (
                "FAIL (unchanged r30) - UEFA MD4 predicted XI: young rotated "
                "Leipzig front three vs near-full-strength City defense; "
                "model lambda_home 2.20 is the cross-league artifact; "
                "market 38c embeds the quality gap."),
            "sources": ["uefa.com MD4 predicted line-ups (r30)",
                        "sports.yahoo.com (r30)"],
        },
        {
            "match": "Bayer 04 Leverkusen vs. Olympique de Marseille",
            "market": "O/U 3.5 Over (id 6091583)",
            "numbers": ("p_med 0.647 [0.536-0.850], bid/ask 0.44/0.46, "
                        "ask250 0.460, exec +18.7c, worst +7.6c, var 31.4c, "
                        "liq $6.3k, fill_250 yes"),
            "failed_gates": ["var<=6c", "cross-league worst>=+5c is met "
                            "(+7.6c) but the 31.4c spread is 5x the bar"],
            "news_concordance_if_overridden": (
                "NEUTRAL - a 3-1 tip supports goals but the p-range "
                "[0.536-0.850] spans everything; no information content."),
        },
        {
            "match": "RB Leipzig vs. Manchester City FC",
            "market": "RB Leipzig team total O0.5 Over (id 6053969)",
            "numbers": ("p_med 0.889 [0.848-0.940], ask250 0.746, exec "
                        "+14.3c, worst +10.2c, var 9.2c (closest row on the "
                        "board), liq $8.6k, fill_250 yes"),
            "failed_gates": ["var<=6c"],
            "news_concordance_if_overridden": (
                "WEAK (unchanged r30) - Leipzig 10-straight home wins with "
                "5 clean sheets is the concordant leg, but 0.746 entry pays "
                "thin and depends on the same artifact."),
        },
        {
            "match": "Bayer 04 Leverkusen vs. Olympique de Marseille",
            "market": "Leverkusen team total O0.5 Over (id 6091604)",
            "numbers": ("p_med 0.830 [0.789-0.863], ask250 0.657, exec "
                        "+17.3c, worst +13.2c, var 7.4c, liq $826, fill_250 "
                        "yes (thin book)"),
            "failed_gates": ["var<=6c", "liq>=5k ($826)"],
            "news_concordance_if_overridden": (
                "CONCORDANT direction (Leverkusen scored in all 3 UEL wins) "
                "but two gates fail and 0.657 entry on an $826 book is not "
                "executable at size."),
        },
        {
            "match": "RB Leipzig vs. Manchester City FC (BANNED rows, report-only)",
            "market": ("match_winner/spread family: City-win-No ask 0.37 vs "
                       "model 0.637 (exec +26.8c, var 3.6c); Leipzig-win ask "
                       "0.18 vs model 0.438 (var 4.4c); spread nocover -1.5 "
                       "+21.6c"),
            "numbers": ("6 numeric passers, ALL kind=ml/spread, ALL flagged "
                        "BANNED-CROSS-LEAGUE-MW/spread (FIXES 5-6)"),
            "failed_gates": ["policy: cross-league MW/spread BANNED"],
            "news_concordance_if_overridden": (
                "The banned rows pass every numeric gate (var 2.8-5.0c!) "
                "precisely because the ML family is least sensitive to the "
                "boost grid - and they are the same rows whose direction "
                "lineup news contradicts (full-strength City XI vs rotated "
                "Leipzig front three). Third consecutive slate demonstrating "
                "why the ban exists: tight numeric agreement + wrong "
                "direction = the most dangerous false edge on the board."),
        },
    ],
    "key_findings": {
        "championship": (
            "12 games in window (Tue Nov-3 19:45/20:00Z x9: Blackburn-Stoke, "
            "Charlton-Bolton, Derby-Norwich, Portsmouth-Swansea, "
            "Preston-SheffUtd, QPR-Burnley, Watford-Lincoln, Birmingham-"
            "Millwall, WBA-Southampton; Wed Nov-4 19:45/20:00Z x3: Cardiff-"
            "West Ham, Wrexham-Middlesbrough, Bristol City-Wolves - matches "
            "ESPN). MODEL-VOID: Understat covers Big-5 only; the brief's "
            "'standard 10-variant domestic path' requires both clubs rated. "
            "Full gamma price boards (49 core markets each: ML/draw, O/U "
            "0.5-8.5, BTTS, spreads, team totals) captured verbatim in "
            "soccer_scan.json prices_only. Example Wed prices: Cardiff-WH "
            "O/U 2.5 0.68/0.69, WH win 0.46/0.47, BTTS 0.68/0.69."),
        "uel_listed": (
            "YES - all 17 Thursday UEL MD4 games + Rennes-Olympiakos (Wed "
            "15:30Z) have Polymarket markets, plus 18 UECL Thursday games "
            "(incl. cross-league Getafe-Brighton). The brief's worry "
            "('not listed for Tuesday') no longer applies."),
        "thu_modelable": (
            "4 of 35 Thu Euro games modelable (Palace-Hoffenheim 17:45Z, "
            "RealSociedad-Lyon 17:45Z, Leverkusen-Marseille 20:00Z, Getafe-"
            "Brighton UECL 20:00Z) - all cross-league -> totals/BTTS/TT "
            "only. Not modelable: Milan-Ferencvaros, Juventus-AZ (canon "
            "corrected), Bournemouth-Sparta, Celta-USG, Sunderland-Dinamo, "
            "Benfica-Lech, etc. (one side outside Big-5)."),
        "canon_correction": (
            "AZ vs Juventus FC (UEL): 'AZ' substring-matched 'Lazio' and was "
            "modeled as a DOMESTIC Lazio-Juventus Serie A derby - caught in "
            "post-scan review, 70 board rows voided, fixture reclassified "
            "no-data. Lesson for canon: 2-letter team tokens need a guard."),
        "structural_var_pattern": (
            "r29 (Tue UCL), r30 (Wed UCL), r31 (UEL/UECL Thu) all show the "
            "same cross-league 30-variant grid behavior: totals/TT/BTTS var "
            "spreads 7-38c vs the 6c gate, while the banned MW family shows "
            "2.8-5.0c. The gate is doing exactly what FIXES 5-6 intended."),
        "mls_efl_trophy": (
            "0 MLS playoff events and 0 EFL Trophy events in range Nov-3 "
            "16:00Z..Nov-6 09:00Z (Gamma tag sweeps + ESPN scoreboard both "
            "empty) - nothing to scan."),
        "brazil_argentina_friday": (
            "Brazil Serie A Wed/Thu (Flamengo-Gremio, Paranaense-Vasco, "
            "Botafogo-Atletico-MG, SaoPaulo-Corinthians, Palmeiras-Remo, "
            "Cruzeiro-Bahia Nov-6 00:30Z) + Argentina (Aldosivi-River, "
            "Gimnasia-Belgrano) have PM markets but are no-data "
            "(non-Big-5). Friday-early: only Cruzeiro-Bahia + Sydney FC "
            "A-League Nov-6 08:40Z - both no-data."),
    },
    "outputs": {
        "scan": "/home/ubuntu/paper-sim/round31/raw/soccer_scan.json",
        "board": "/home/ubuntu/paper-sim/round31/raw/odds_board_31.json",
        "events": "/home/ubuntu/paper-sim/round31/raw/events_window_31.json",
        "script": "/home/ubuntu/paper-sim/round31/raw/soccer_scan31.py",
        "candidates": OUT,
    },
}
json.dump(doc, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("verdict:", doc["verdict"][:200])
