"""Round-34 candidates writer (paper-only). Result: HONEST PASS - 0 new
soccer candidates. Applies the news-concordance layer to the scan's 9
numeric passers (scan: round34/raw/soccer_scan.json), verifies held
positions #59/#60, and emits round34/soccer_candidates.json.

News evidence gathered 2026-11-04 ~15:15-16:00Z via live web search:
- #59 Leverkusen-Marseille (T-29h): CONCORDANT, HOLD. Lev XI vs Stuttgart
  (Flekken; Quansah, Tapsoba, Medina, Gutierrez; F. Carballo, A. Garcia;
  Vazquez, Maza, Bastardo Moreira; Schick; Boniface on bench) - full
  attack. Lev conceded 10 in last 5 (4-2 L Stuttgart, 3-0 L Hoffenheim)
  -> supports the OM-scores leg. OM XI vs Toulouse (W 2-0): de Lange;
  Weah, Egan-Riley, Aguerd, Emerson; Hojbjerg, Harit, Abdelli, Nadi;
  Paixao, Gouiri - full-strength front line, 11 goals in last 5. OM UEL
  0/9 points remains the rotation risk (lineups ~1h pre-kick).
- #60 Wrexham-Middlesbrough (T-4.5h): MILDLY CONCORDANT, HOLD, no thesis
  break. Wrexham missing Broadhead + Windass (attack blunter: 0 goals in
  last 2), Patterson may drop for Ward in goal; Imray + Smith may return.
  Boro near-unchanged (Lankshear cramp-only, starts; Jones + Pukstas
  out). Sports Mole 1-3 remains the lone 4-goal contrary view (known
  fragility since r33).
- Lens-Como ML home +17.1c / TT O0.5 +10.9c: KILL CONFIRMED AND
  STRENGTHENED - Edouard adductor SURGERY (possibly out until 2027),
  Sima sidelined, Ganiou + Nawrocki out; Sports Mole predicts 1-2 HOME
  LOSS (Como scored first in all 3 CL games; Paz + Douvikas fit). Model
  edge is stale-xG artifact; TT O0.5 also has var exactly at the 6.00c
  cap (zero cushion).
- Leipzig-City ML home +12.0c / ML away_no +6.9c: KILL STANDS - City
  predicted near full strength (Donnarumma; Nunes, Khusanov, Guehi,
  O'Reilly; Anderson, Fernandez; Foden, Cherki, Doku; Haaland; only
  Semenyo out); no Leipzig-side supporting news (unknown cannot support
  candidacy, r29-r33 lineage; away_no is anti-City - news discordant
  with model direction).
- Cardiff-West Ham / Bristol City-Wolves / Palace-Hoffenheim / Real
  Sociedad-Lyon / Getafe-Brightton / Dortmund-Betis: NO numeric passer
  (var>6c, worst-variant<bar, or exec<+5c on every eligible row).
- Held-fixture overlay: Lev-OM and Wrexham-Boro rows (incl. Wrexham
  U1.5/U2.5/U4.5 passers and Lev-OM BTTS repeat) are excluded from new
  candidacy - no double-up, no concentration add.
"""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round34/raw/soccer_scan.json"
OUT = "/home/ubuntu/paper-sim/round34/soccer_candidates.json"
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
scan = json.load(open(SCAN))
board = {((r["fixture_key"], r["kind"], r["side"], r["line"])): r
         for r in scan["board"]}


def get(fk, kind, side, line):
    return board[(fk, kind, side, line)]


btts = get("leverkusen-marseille", "btts", "yes", None)
u35 = get("middlesbrough-wrexham", "total", "under", 3.5)

# unique Thursday UEL/UECL slate (dedupe by kickoff + base title)
thu = {}
for f in scan["fixtures"]:
    if f["kickoff_utc"] >= "2026-11-05T15:00:00Z" and f["comp"] in ("UEL", "UECL", "CROSS(other)"):
        base = f["title"].split(" - ")[0]
        key = (f["kickoff_utc"], base)
        if key not in thu or f["modelable"]:
            thu[key] = {
                "kickoff_utc": f["kickoff_utc"], "fixture": base,
                "comp": f["comp"],
                "modelability": f["modelability_class"] if f["modelable"]
                else "model-void (club(s) outside Big-5+Championship snapshot)",
                "home": f["understat_home"], "away": f["understat_away"],
            }
thu_slate = [thu[k] for k in sorted(thu)]

candidates = {
    "round": 34, "scan": "soccer", "paper_only": True,
    "generated_utc": now,
    "decision": "PASS - 0 new soccer candidates this round",
    "decision_rationale": (
        "All 9 numeric passers fail the candidacy overlay: 2 are the HELD "
        "markets themselves (#59 BTTS Yes, #60 U3.5 - no double-up), 4 are "
        "held-fixture concentration rows (Wrexham U1.5/U2.5/U4.5, Lev-OM "
        "repeat), 3 are r33-news-killed UCL Wednesday leftovers re-killed "
        "by fresh 15:15-16:00Z searches (Lens x2: Edouard surgery/Sima out/"
        "1-2 predicted home loss; Leipzig x2: City near full strength, no "
        "Leipzig-side support). Every NEW fixture (Cardiff-WHam, BristolCity-"
        "Wolves, Palace-Hoffenheim, RealSociedad-Lyon, Getafe-Brightton, "
        "Dortmund-Betis) has zero eligible-kind numeric passers. Entering "
        "below-gate rows to force action would violate the frozen gates."),
    "max_new_positions": 3, "stake_per_position_usd": 250,
    "new_candidates": [],
    "held_position_verifications": [
        {
            "id": 59,
            "position": "Leverkusen-Marseille BTTS Yes $250 @ 0.575",
            "kickoff_utc": "2026-11-05T20:00:00Z",
            "hours_to_kickoff_at_verify": 29,
            "verdict": "HOLD - CONCORDANT, no thesis break",
            "current_mark": {"bid": btts["book_best_bid"],
                             "ask": btts["book_best_ask"],
                             "mtm_vs_entry_c": round(100 * (btts["book_best_bid"] - 0.575), 1)},
            "model_recheck": {"p_med": btts["p_med"],
                              "exec_edge_now": "+13c vs ask 0.58 (still passes all gates)"},
            "evidence": (
                "Leverkusen most-recent XI (4-2 L Stuttgart): full attack - "
                "Flekken; Quansah, Tapsoba, Medina, Gutierrez; F. Carballo, "
                "A. Garcia; Vazquez, Maza, Bastardo Moreira; Schick (Boniface, "
                "Hofmann, Andrich on bench). Lev conceded 10 in last 5 "
                "(incl 4 and 3) -> supports OM-scores leg. Marseille most-"
                "recent XI (2-0 W Toulouse): de Lange; Weah, Egan-Riley, "
                "Aguerd, Emerson; Hojbjerg, Harit, Abdelli, Nadi; Paixao, "
                "Gouiri - front line intact, 11 scored in last 5. Lev 3W/0L "
                "8-0 in UEL; OM 0/9 points (rotation before dead rubbers "
                "remains the live risk; XIs ~1h pre-kick)."),
            "sources": [
                "bulinews.com/fixture/1039950/lineups/leverkusen-marseille",
                "goal.com/en/news/bayer-leverkusen-marseille-uefa-europa-league-preview",
                "statz.ai/h2h/leverkusen-vs-marseille/19873907/lineups",
                "fotmob.com/matches/bayer-leverkusen-vs-marseille/2bq9g3",
            ],
            "action": "no action - hold to natural settlement",
        },
        {
            "id": 60,
            "position": "Wrexham-Middlesbrough Under 3.5 $250 @ 0.635",
            "kickoff_utc": "2026-11-04T19:45:00Z",
            "hours_to_kickoff_at_verify": 4.5,
            "verdict": "HOLD - MILDLY CONCORDANT, no thesis break",
            "current_mark": {"bid": u35["book_best_bid"],
                             "ask": u35["book_best_ask"],
                             "mtm_vs_entry_c": round(100 * (u35["book_best_bid"] - 0.635), 1)},
            "model_recheck": {"p_med": u35["p_med"],
                              "exec_edge_now": "+9c vs ask 0.65 (still passes all gates)"},
            "evidence": (
                "Wrexham (predicted 3-4-1-2): Broadhead + Windass OUT (attack "
                "blunter - 0 goals in back-to-back defeats); GK Patterson may "
                "drop for Ward after errors; Imray + Sam Smith may return. "
                "Middlesbrough near unchanged from Charlton win: Lankshear "
                "(top scorer) cramp-only and starts; Jones + Pukstas out; "
                "unbeaten since Aug 22, 30 goals in 13. Under thesis needs "
                "Wrexham blunt (supported) + Boro not running away (Boro 13 "
                "in 6 away, only 1 away clean sheet = pressure stays on). "
                "Sports Mole 1-3 (exactly 4 goals) remains the lone contrary "
                "scoreline, known since r33."),
            "sources": [
                "sportsmole.co.uk/football/middlesbrough/preview/wrexham-vs-middlesbrough-prediction-team-news-lineups_608244.html",
                "gazettelive.co.uk/sport/football/football-news/middlesbrough-predicted-team-vs-wrexham-34859164",
                "si.com/soccer/wrexham-vs-middlesbrough-preview-predictions-lineups-11-4-26",
                "flashscore.com match lineups page",
            ],
            "action": "no action - hold to natural settlement (kickoff ~4.5h)",
        },
    ],
    "numeric_passers_disposition": [
        {"fixture": "Lens-Como", "row": "ml home +17.1c worst +12.4c var 5.64c liq $466k",
         "disposition": "KILLED - news",
         "reason": "Edouard adductor surgery (possibly out until 2027), Sima "
                   "sidelined, Ganiou+Nawrocki out; Sports Mole predicts 1-2 "
                   "home loss; stale-xG artifact. Also $150 MW deprioritized."},
        {"fixture": "Leverkusen-Marseille", "row": "btts yes +13.3c worst +11.5c var 5.51c",
         "disposition": "HELD - no double-up", "reason": "paper #59 already open $250 @ 0.575"},
        {"fixture": "Leipzig-ManCity", "row": "ml home +12.0c worst +10.9c var 2.61c liq $389k",
         "disposition": "KILLED - news",
         "reason": "City predicted near full strength (Haaland, Foden, Doku, "
                   "Cherki; only Semenyo out); no Leipzig-side supporting "
                   "news - unknown cannot support candidacy (r29-r33 rule). "
                   "$150 MW deprioritized."},
        {"fixture": "Lens-Como", "row": "team_total over 0.5 +10.9c worst +9.0c var 6.00c",
         "disposition": "KILLED - news",
         "reason": "Lens-scoring-dependent with attack depleted (Edouard/"
                   "Sima out); var exactly at 6.00c cap = zero cushion."},
        {"fixture": "Wrexham-Middlesbrough", "row": "total under 3.5 +9.2c worst +6.8c",
         "disposition": "HELD - no double-up", "reason": "paper #60 already open $250 @ 0.635"},
        {"fixture": "Wrexham-Middlesbrough", "row": "total under 1.5 +8.3c worst +6.2c",
         "disposition": "EXCLUDED - held fixture", "reason": "concentration overlay"},
        {"fixture": "Leipzig-ManCity", "row": "ml away_no +6.9c worst +11.6c var 4.05c",
         "disposition": "KILLED - news",
         "reason": "anti-City direction; City full-strength news is "
                   "discordant with the model tilt."},
        {"fixture": "Wrexham-Middlesbrough", "row": "total under 4.5 +6.1c worst +4.6c",
         "disposition": "EXCLUDED - held fixture", "reason": "concentration overlay"},
        {"fixture": "Wrexham-Middlesbrough", "row": "total under 2.5 +5.8c worst +8.8c",
         "disposition": "EXCLUDED - held fixture", "reason": "concentration overlay"},
    ],
    "uel_thursday_slate": thu_slate,
    "uel_modelable": {
        "leverkusen-marseille": {"bridge": 1.0549, "lambdas": "2.71/1.45",
                                 "note": "HELD fixture (#59); BTTS Yes still +13.3c"},
        "crystalpalace-hoffenheim": {"bridge": 1.25,
                                     "lambdas": "2.03/1.48 (tot 3.52)",
                                     "note": "clamp cap; best eligible row O4.5 +4.7c "
                                             "worst +3.6c (below 5c cross bars)"},
        "lyon-realsociedad": {"bridge": 1.0812, "lambdas": "1.79/1.40 (tot 3.19)",
                              "note": "best rows: ML away +7.0c var 8.87c FAIL; "
                                      "TT O1.5 +4.4c below bar"},
        "brighton-getafe": {"bridge": 0.8074, "lambdas": "0.88/1.78 (tot 2.66)",
                            "note": "UECL cross pair; all rows fail worst-variant "
                                    "bar (best +2.2c exec)"},
    },
    "championship_wednesday": {
        "cardiffcity-westhamunited": {
            "lambdas": "1.64/1.49 (tot 3.13)",
            "markets_on_polymarket": "ML (West Ham win) + spreads only - NO O/U or BTTS markets listed",
            "best_eligible": "ml away_no +15.5c but var 13.95c FAIL (MW $150 deprioritized anyway)",
            "news": "Cardiff defensive crisis (Osho suspended; Lawlor, Chambers, "
                    "Bielik injured; Fish/Ng/Robertson doubts); West Ham league-"
                    "best attack 33 in 13, managerless (Nuno sacked; Noble/"
                    "Potts interim), unbeaten away W3 D3; Sports Mole 1-3; "
                    "SportyTrader tips O3.5; Kalshi WHU 54%",
        },
        "middlesbrough-wrexham": {"note": "HELD #60 U3.5 $250 @ 0.635; see verification above"},
        "bristolcity-wolverhamptonwanderers": {
            "lambdas": "1.31/1.33 (tot 2.65)",
            "best_eligible": "ml home +7.0c worst -1.5c FAIL; TT O1.5 +4.6c worst -1.3c FAIL",
            "news": "Wolves favourites (Sports Mole most-likely 1-1 12.8%, 0-1 "
                    "10.5%; BTTS 50.8%, O2.5 46.1% - low-scoring profile; "
                    "Scores24 tips U2.5; Wolves 3-0 vs Cardiff Oct 31, "
                    "unbeaten last 4 H2H)",
        },
    },
    "ucl_wednesday_in_window_note": (
        "Discovery also swept UCL MD4 Wednesday (AEK-Real, Fener-Liverpool, "
        "Porto-Napoli, PSV-Brugge, Slavia-Arsenal, Viking-Sabah + modeled "
        "Dortmund-Betis, Leipzig-City, Lens-Como). Dortmund-Betis best row "
        "+1.9c (nothing close); Leipzig/Lens passers killed by news (above); "
        "the rest are model-void prices-only."),
    "understat_pointer_status": {
        "path": scan["xg_bases"]["big5"]["path"],
        "pointer_symlink_resolves": True,
        "sha256": scan["xg_bases"]["big5"]["pointer_sha256"],
        "pointed_at_utc": "2026-11-04T14:25:22Z",
        "fresh_through_utc": "2026-10-31 (Big-5 weekend results Nov 1-3 NOT "
                             "absorbed; Understat upstream recovery cron owns "
                             "advancement; http probe at scan: "
                             + str(scan["xg_bases"]["big5"]["http_probe_at_run"]["ok"]) + ")",
        "championship_fotmob": {"path": scan["xg_bases"]["championship"]["path"],
                                "fresh_through_utc": "2026-11-03"},
    },
    "scan_artifact": SCAN,
    "library": {"package": "polymarket_alpha_lab.papersim",
                "repo_commit": "7dc4f3d2",
                "selfcheck": "268 passed, 1 skipped (10/10 papersim test files, re-run this session)"},
}
json.dump(candidates, open(OUT, "w"), indent=1)
print("saved", OUT)
print("decision:", candidates["decision"])
print("held verifications:", [v["verdict"] for v in candidates["held_position_verifications"]])
print("UEL Thursday unique fixtures:", len(thu_slate))
for t in thu_slate:
    print("  %-5s %-16s %-52s %s" % (t["comp"], t["kickoff_utc"][5:16],
                                     t["fixture"][:52],
                                     "MODELED" if t["home"] and t["away"] else "prices-only"))
