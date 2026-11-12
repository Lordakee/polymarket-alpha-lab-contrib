#!/usr/bin/env python3
"""Build scan43.py from round41/raw/scan41.py (exact-replacement patch).
Every replacement must hit exactly once or the patch aborts. PAPER ONLY."""
import sys

SRC = "/home/ubuntu/paper-sim/round41/raw/scan41.py"
DST = "/home/ubuntu/paper-sim/round43/raw/scan43.py"

NEW_DOCSTRING = '''"""ROUND-43B scan (paper-only): Europe Sunday-night window
2026-11-08T18:00Z .. 2026-11-09T01:14Z.

Coverage (dispatch, frozen):
  Big-5 (Bundesliga, Serie_A, La_liga, Ligue_1 + any EPL stragglers): FULL
    market families, match_winner eligible-deprioritized $150.
  Eredivisie: TOTALS FAMILY ONLY (gate-E); Utrecht-NEC 19:00Z.
  Championship: wired; enum tag sweep in_window=0 (no Sunday-night games).
  Board-only leagues (prices reported, NO model coverage, no entry):
    Belgian Pro League, Turkish Super Lig, Primeira Liga, Scottish
    Premiership + other European leagues found by enumeration (Greek Super
    League, Hungarian NB1, Israeli Premier League, Norwegian Eliteserien,
    Polish Ekstraklasa, Serbian Superliga, Serie B, Belgian 2nd, Portuguese
    Liga 2, Spanish 3rd tier, German 3. Liga).
  Cross-league MW: wired through gates.check_cross_league_mw (bridge_present
    + worst>=+5c) and sized via risk_policy sizing_tier(CROSS_LEAGUE_ML_CLASS)
    per DELIVERY_PLAN section 72 (no cross pairs expected this window; all
    Sunday-night fixtures single-league).

Held fixtures: NONE in this window (HELD_IDS/HELD_PAIRS empty).

xG bases (r41 refresh earlier today - unchanged and still current):
  Big-5: understat_latest.json pointer -> round41/raw/xg_fotmob_big5_merged.json
    (round25 Understat through Oct-31 + FotMob Nov-1..Nov-8 backfill; Sat
    Nov-7 games MERGED). Sunday-participating clubs carry Oct-31/Nov-2
    last-completed-match ratings - CORRECT, not stale: no Sunday results
    exist in the snapshot because Sunday games kick after it was cut.
  Eredivisie: round41/raw/xg_fotmob_eredivisie.json (103 completed matches
    through Sat Nov-7 20:00Z); no Sunday Eredivisie results exist pre-kick.

Frozen gates (library 1a2760bc, selfcheck re-run this session pre-scan
2026-11-08T13:40Z, PASS 10/10):
  net>=+5c after sports fee 0.05 (8c if under-risk), worst>=+4c, var<=6c,
  liq>=$5k, $250 walk fill (MW $150), entry .10-.92, 50-50 haircut on net
  edge, news concordance (one focused search per serious candidate),
  scoreline concordance (r32), one position per fixture, spreads
  flagged-only, Eredivisie totals-only.
R41 context for this same slate (scanned ~10h pre-kick): Lens-Marseille
  family died var 12-20c (+liq); Atletico-Barcelona and Fiorentina-Juventus
  not passers. Re-evaluated at fresh prices - var kills are model-fixed,
  only edge can flip.
Entry timing: scan ~4-8h pre-kick; T-2h XI recheck condition noted per
candidate; predicted-lineup news captured in the news checks.
"""'''


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        print("PATCH-FAIL %s: %d occurrences" % (label, n))
        sys.exit(1)
    return text.replace(old, new, 1)


src = open(SRC, "r", encoding="utf-8").read()

# 1. module docstring: swap between the first pair of triple quotes
first = src.index('"""')
second = src.index('"""', first + 3) + 3
src = NEW_DOCSTRING + src[second:]

# 2. window bounds
src = replace_once(src, 'LO = "2026-11-08T01:15:00Z"', 'LO = "2026-11-08T18:00:00Z"', "LO")
src = replace_once(src, 'HI = "2026-11-09T01:15:00Z"', 'HI = "2026-11-09T01:14:00Z"', "HI")

# 3. paths
src = replace_once(src, 'OUTDIR = f"{HOME}/round41/raw"', 'OUTDIR = f"{HOME}/round43/raw"', "OUTDIR")
src = replace_once(src, 'OUT = f"{OUTDIR}/scan.json"', 'OUT = f"{OUTDIR}/euro_night_scan.json"', "OUT")
src = replace_once(src, 'EVENTS = f"{OUTDIR}/events_window_41.json"', 'EVENTS = f"{OUTDIR}/events_window_43.json"', "EVENTS")
src = replace_once(src, 'ESPN = f"{OUTDIR}/espn_fixtures_41.json"', 'ESPN = f"{OUTDIR}/espn_fixtures_43.json"', "ESPN")

# 4. held fixtures: none in this window
src = replace_once(src, '''HELD_IDS = {  # marks-only positions from the dispatch
    "67_le_mans_monaco_mw_no": 6236736,
    "68_brest_lyon_o25_over": 6239548,
    "63_manutd_villa_mw_no": 6237007,
}''', 'HELD_IDS = {}  # R43B: NO held fixtures in this window', "HELD_IDS")
src = replace_once(src, '''HELD_PAIRS = [  # held fixtures: marks only, no new positions
    ("Le Mans", "Monaco"),
    ("Brest", "Lyon"),
    ("Manchester United", "Aston Villa"),
]''', 'HELD_PAIRS = []  # R43B: none in this window', "HELD_PAIRS")

# 5. extra European board-only leagues
src = replace_once(src, '''    "primeira-liga": "Primeira Liga",
    "scottish-premiership": "Scottish Premiership",
}''', '''    "primeira-liga": "Primeira Liga",
    "scottish-premiership": "Scottish Premiership",
    # --- R43B: other European leagues found by enumeration (board-only) ---
    "gre1": "Greek Super League",
    "hungary-nb1": "Hungarian NB1",
    "israel-premier-league": "Israeli Premier League",
    "norway-eliteserien": "Norwegian Eliteserien",
    "poland-ekstraklasa": "Polish Ekstraklasa",
    "serbian-superliga": "Serbian Superliga",
    "serie-b": "Serie B",
    "bel2": "Belgian Challenger Pro League",
    "pt2": "Portuguese Liga 2",
    "es3": "Spanish Primera Federacion",
    "bl3": "German 3. Liga",
}''', "LEAGUE_TAGS")
src = replace_once(src, '''BOARD_ONLY = ("Belgian Pro League", "Turkish Super Lig", "Primeira Liga",
              "Scottish Premiership")''', '''BOARD_ONLY = ("Belgian Pro League", "Turkish Super Lig", "Primeira Liga",
              "Scottish Premiership", "Greek Super League", "Hungarian NB1",
              "Israeli Premier League", "Norwegian Eliteserien",
              "Polish Ekstraklasa", "Serbian Superliga", "Serie B",
              "Belgian Challenger Pro League", "Portuguese Liga 2",
              "Spanish Primera Federacion", "German 3. Liga")''', "BOARD_ONLY")

# 6. dispatch note + round labels
src = replace_once(src, '"scan": "soccer-24h-window", "round": 41,', '"scan": "euro-sunday-night", "round": 43,', "round-label")
src = replace_once(src, '''        "dispatch_note": (
            "ROUND-41 24h Sunday window scan (slate + late-Sunday-night); "
            "scan executed ~9-18h pre-kick; all modeled fixtures pre-kickoff "
            "at scan; held #67 Le Mans-Monaco / #68 Brest-Lyon O2.5 / #63 "
            "ManUtd-Villa marks fetched separately; untagged leagues "
            "(A-League, CSL, Americas etc.) are raw-board-only; PAPER ONLY, "
            "no DB writes, no real orders"),''', '''        "dispatch_note": (
            "ROUND-43B Europe Sunday-night window scan (2026-11-08T18:00Z -> "
            "2026-11-09T01:14Z); scan executed ~4-8h pre-kick; NO held "
            "fixtures in window; other European leagues (Greek/Hungarian/"
            "Israeli/Norwegian/Polish/Serbian/Serie B/lower divisions) "
            "priced board-only with no model coverage and no entry; "
            "non-European untagged leagues recorded raw-board-only in "
            "events_window_43.json; PAPER ONLY, no DB writes, no real "
            "orders"),''', "dispatch_note")

# 7. budget: dispatch cap $200, coordinator arbitrates
src = replace_once(src, '''        "budget": {"max_new_entries_usd": 600,
                   "soccer_pool_usd": 3000, "headroom_usd": 1700,
                   "ucl_uel_reserve_usd": 1100},''', '''        "budget": {"max_new_entries_usd": 200,
                   "note": ("dispatch R43B: propose entries totaling "
                            "<=$200; coordinator arbitrates; nothing "
                            "passes = enter nothing")},''', "budget")

# 8. provenance strings
src = replace_once(src, '''            "selfcheck": "PASS 10/10 (re-run this session pre-scan "
                         "2026-11-08T02:11Z)",''', '''            "selfcheck": "PASS 10/10 (re-run this session pre-scan "
                         "2026-11-08T13:40Z)",''', "selfcheck")
src = replace_once(src, '''                "note": ("NO Sunday Championship games in the r41 window "
                         "(tag sweep in_window=0); snapshot wired but "
                         "unused this round")},''', '''                "note": ("NO Sunday-night Championship games in the r43 "
                         "window (tag sweep in_window=0); snapshot wired "
                         "but unused this round")},''', "champ-note")
src = replace_once(src, '''                "fresh_through_utc": ("2026-11-07 20:00Z refetched this "
                                      "session (103 matches 2026/27; Sat "
                                      "Nov-7 round merged)")},''', '''                "fresh_through_utc": ("2026-11-07 20:00Z (r41 refetch "
                                      "earlier today; 103 matches 2026/27; "
                                      "no Sunday Eredivisie results exist "
                                      "pre-kick - base still current for "
                                      "R43B)")},''', "ered-note")
src = replace_once(src, '''            "big5_refresh": {
                "merged": "round41/raw/xg_fotmob_big5_merged.json",''', '''            "big5_refresh": {
                "note_r43b": ("base reused unchanged from the r41 refresh "
                              "earlier today; no Sunday results existed at "
                              "refresh time, so Sunday clubs correctly "
                              "carry Oct-31/Nov-2 last-completed ratings"),
                "merged": "round41/raw/xg_fotmob_big5_merged.json",''', "big5-note")

open(DST, "w", encoding="utf-8").write(src)
print("patched OK ->", DST, "| lines:", src.count("\\n") + 1)
