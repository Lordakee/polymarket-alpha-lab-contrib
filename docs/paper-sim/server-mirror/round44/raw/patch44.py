#!/usr/bin/env python3
"""Build round44/raw/scan44.py from round43/raw/scan43a.py (paper-only).

Round-44A changes applied by this patch:
  1. docstring -> ROUND-44A Mon-Tue window + calendar finding
  2. window LO/HI -> 2026-11-09T01:30Z .. 2026-11-10T23:59:59Z (entry
     window; enumeration file covers the wider Mon-Wed range)
  3. paths -> round44/raw (events_window_44, espn_fixtures_44,
     mon_tue_scan.json out)
  4. Championship snapshot -> championship_20261108/xg_fotmob_championship.json
     (NEW path per dispatch; 180 matches, 24 clubs, through Sat Nov-7)
  5. HELD_IDS/HELD_PAIRS -> empty (no held soccer positions remain)
  6. R41_KILLS -> empty (all r41 kills settled; no recheck this round)
  7. DISPATCH_SLATE -> the actual Mon/Tue ESPN slate (La Liga 2 Mon,
     Copa del Rey + EFL Trophy Tue) for the Gamma cross-check
  8. LEAGUE_TAGS + BOARD_ONLY extended with every league found by
     enumeration (all board-only this window)
  9. Copa del Rey coverage label -> model-void (cross-tier minnow opponent)
 10. build_staleness -> r44 version: Sunday 2026-11-08 participants vs
     snapshot blocks (Big-5 pointer ends Nov-7; Sunday results NOT merged)
     + generic pre-Oct-30 fallback
 11. budget -> <=$400 proposals (dispatch R44A)
 12. provenance/dispatch notes/round number -> r44
"""
import re
import sys

SRC = "/home/ubuntu/paper-sim/round43/raw/scan43a.py"
DST = "/home/ubuntu/paper-sim/round44/raw/scan44.py"

s = open(SRC, encoding="utf-8").read()
n0 = len(s)


def rep(old, new, label):
    global s
    assert old in s, "MISSING BLOCK: " + label
    assert s.count(old) == 1, "NON-UNIQUE BLOCK: " + label
    s = s.replace(old, new)
    print("ok:", label)


# ---- 1. docstring ----
NEW_DOC = '''"""ROUND-44A scan (paper-only): MONDAY-TUESDAY window
2026-11-09T01:30Z .. 2026-11-10T23:59:59Z (entry window; enumeration range
2026-11-09T00:00Z .. 2026-11-11T23:59:59Z so Wednesday content is boarded).

CALENDAR FINDING (triple-verified pre-scan: Gamma tag sweep + direct Gamma
event query + ESPN scoreboard + FotMob league fixtures): there is NO
Championship midweek round on Nov-10/11. Championship round 15 completed
Sat Nov-7; round 16 is Sat Nov-21/Sun Nov-22 (international break). The
69 active Gamma efl-championship events have no gameStartTime before
2026-11-21. The dispatch's "Nov-10/11 Championship midweek round" does not
exist. Also NO Monday Big-5 league games are scheduled this week (no Ligue 1
Monday, no Serie A Monday, no La Liga Monday; ESPN shows only La Liga 2 on
Monday). EFL Trophy Tue/Wed exists on ESPN but has ZERO Gamma markets.

Window content (all board-only, none modelable):
  Mon Nov-9: Liga MX (post-kick), Romanian/Norwegian/Serie C/La Liga 2/
    FA Cup/National League/Paraguay/Portugal 2/Ecuador/Colombia fixtures.
  Tue Nov-10: Copa del Rey 6 ties (Spanish league clubs vs 3rd/4th-tier
    minnows - MODEL-VOID cross-tier per dispatch, board-only prices),
    Womens Champions League 5 ties (women's sides outside the men's-league
    snapshot universe, board-only), National League N/S.

Coverage (dispatch, frozen): Championship totals-only (gate-E) - wired,
unused (no Championship fixtures in window). Big-5 full families - wired,
unused (no Big-5 fixtures in window). Cross-league MW wiring retained
(check_cross_league_mw + CROSS_LEAGUE_ML_CLASS $150) - unexercised.

xG bases:
  Big-5: understat_latest.json pointer -> round41/raw/xg_fotmob_big5_merged.json
    (through Sat Nov-7). Sunday Nov-8 Big-5 games NOT merged (snapshot cut
    02:24Z predates them) -> Sunday-participating clubs carry runtime
    STALE-XG flags. NO modeled fixture this window involves any of them
    (zero modelable fixtures), so the allowed FotMob Sunday backfill is NOT
    needed; documented instead.
  Championship: championship_20261108/xg_fotmob_championship.json (NEW path
    per dispatch; 180 matches, 24 clubs x 15 rounds, through Sat Nov-7).
  Eredivisie: round41/raw/xg_fotmob_eredivisie.json (103 matches through
    Sat Nov-7 20:00Z; Sunday Eredivisie games unmerged -> stale flags).

Held fixtures: NONE (all prior soccer positions settled per dispatch).

Frozen gates (library 1a2760bc, selfcheck re-run this session pre-scan
2026-11-09T07:06Z, PASS 10/10): net>=+5c after sports fee 0.05 (8c if
under-risk), worst>=+4c, var<=6c, liq>=$5k, $250 walk fill, entry .10-.92,
50-50 haircut on net edge, news concordance (one focused search per serious
candidate), scoreline concordance (r32), one position per fixture, spreads
flagged-only. Budget: <=$400 proposals this window; nothing passes = enter
nothing.
"""'''
s = re.sub(r'"""ROUND-43A scan.*?"""', NEW_DOC, s, count=1, flags=re.S)
print("ok: docstring")

# ---- 2. championship snapshot path ----
rep('FOTMOB_CHAMP = f"{HOME}/round31/raw/xg_fotmob_championship.json"',
    'FOTMOB_CHAMP = f"{HOME}/championship_20261108/xg_fotmob_championship.json"',
    "championship snapshot path")

# ---- 3. paths + window ----
rep('OUTDIR = f"{HOME}/round43/raw"', 'OUTDIR = f"{HOME}/round44/raw"',
    "outdir")
rep('OUT = f"{OUTDIR}/euro_day_scan.json"', 'OUT = f"{OUTDIR}/mon_tue_scan.json"',
    "out path")
rep('EVENTS = f"{OUTDIR}/events_window_43a.json"',
    'EVENTS = f"{OUTDIR}/events_window_44.json"', "events path")
rep('ESPN = f"{OUTDIR}/espn_fixtures_43a.json"',
    'ESPN = f"{OUTDIR}/espn_fixtures_44.json"', "espn path")
rep('LO = "2026-11-08T05:30:00Z"\nHI = "2026-11-08T17:59:59Z"',
    'LO = "2026-11-09T01:30:00Z"   # entry window (dispatch)\n'
    'HI = "2026-11-10T23:59:59Z"   # Wednesday events are board-only',
    "window")

# ---- 4. board-only leagues ----
rep('''BOARD_ONLY = ("Belgian Pro League", "Turkish Super Lig", "Primeira Liga",
              "Scottish Premiership")''',
    '''BOARD_ONLY = ("Belgian Pro League", "Turkish Super Lig", "Primeira Liga",
              "Scottish Premiership", "Greek Super League", "Hungarian NB1",
              "Israeli Premier League", "Norwegian Eliteserien",
              "Polish Ekstraklasa", "Serbian Superliga", "Serie B",
              "Belgian Challenger Pro League", "Portuguese Liga 2",
              "Spanish Primera Federacion", "German 3. Liga",
              # --- R44A: leagues found by this window's enumeration ---
              "Liga MX", "Copa del Rey", "La_liga_2", "FA Cup",
              "National League North", "National League South", "Serie C",
              "Romanian SuperLiga", "Paraguayan Primera",
              "Ecuadorian Serie A", "Colombian Primera A",
              "Colombian Primera B", "Bolivian LFPB",
              "Womens Champions League", "Brazil Serie B", "FIFA Friendly")''',
    "board-only leagues")

# ---- 5. league tags ----
rep('''    "scottish-premiership": "Scottish Premiership",
}''',
    '''    "scottish-premiership": "Scottish Premiership",
    # --- R43B other European leagues (board-only) ---
    "gre1": "Greek Super League",
    "hungary-nb1": "Hungarian NB1",
    "israel-premier-league": "Israeli Premier League",
    "norway-eliteserien": "Norwegian Eliteserien",
    "poland-ekstraklasa": "Polish Ekstraklasa",
    "serbian-superliga": "Serbian Superliga",
    "serie-b": "Serie B",
    "bel2": "Belgian Challenger Pro League",
    "es3": "Spanish Primera Federacion",
    "bl3": "German 3. Liga",
    # --- R44A: leagues found by this window's enumeration (board-only) ---
    "mex": "Liga MX",
    "copa-del-rey": "Copa del Rey",
    "la-liga-2": "La_liga_2",
    "fa-cup": "FA Cup",
    "nln": "National League North",
    "nls": "National League South",
    "serc": "Serie C",
    "Romania-SuperLiga": "Romanian SuperLiga",
    "par1": "Paraguayan Primera",
    "ecu1": "Ecuadorian Serie A",
    "colombia-primera-a": "Colombian Primera A",
    "col2": "Colombian Primera B",
    "Bolivia-LFPB": "Bolivian LFPB",
    "womens-champions-league": "Womens Champions League",
    "brazil-serie-b": "Brazil Serie B",
    "fifa-friendly": "FIFA Friendly",
}''',
    "league tags")

# ---- 6. held -> empty ----
rep('''HELD_IDS = {  # marks-only positions from the dispatch
    "67_le_mans_monaco_mw_no": 6236736,
    "68_brest_lyon_o25_over": 6239548,
    "63_manutd_villa_mw_no": 6237007,
}
HELD_PAIRS = [  # held fixtures: marks only, no new positions
    ("Le Mans", "Monaco"),
    ("Brest", "Lyon"),
    ("Manchester United", "Aston Villa"),
]''',
    '''HELD_IDS = {}   # R44A: NO held soccer positions remain (all settled)
HELD_PAIRS = []  # R44A: none''',
    "held empty")

# ---- 7. r41 kills -> empty ----
rep('''# R41 news-killed passers (recheck at fresh prices; revive rules in docstring)
R41_KILLS = {
    "6241503": {"label": "Rayo ML away (RSociedad-Rayo)",
                "r41_ask": 0.22, "r41_vwap250": 0.22, "r41_p_med": 0.2908,
                "our_side": "away", "kickoff": "2026-11-08T15:15:00Z"},
    "6239948": {"label": "Genoa-Milan BTTS Yes",
                "r41_ask": 0.49, "r41_vwap250": 0.4972, "r41_p_med": 0.5696,
                "our_side": "yes", "kickoff": "2026-11-08T14:00:00Z"},
    "6239569": {"label": "Brentford TT O1.5 (Brighton-Brentford)",
                "r41_ask": 0.35, "r41_vwap250": 0.3544, "r41_p_med": 0.4250,
                "our_side": "over", "kickoff": "2026-11-08T14:00:00Z"},
}''',
    '''# R44A: no prior-round kill rechecks (all r41/r43 markets settled)
R41_KILLS = {}''',
    "r41 kills empty")

# ---- 8. dispatch slate -> actual Mon/Tue ESPN slate ----
rep('''# Dispatch slate for Gamma cross-check ("include anything missed")
DISPATCH_SLATE = [
    ("Eredivisie", "Heerenveen Feyenoord", "2026-11-08T11:15:00Z"),
    ("Eredivisie", "Twente Ajax", "2026-11-08T13:30:00Z"),
    ("Eredivisie", "AZ Groningen", "2026-11-08T15:45:00Z"),
    ("Eredivisie", "Cambuur PSV", "2026-11-08T15:45:00Z"),
    ("Serie_A", "Napoli Lazio", "2026-11-08T11:30:00Z"),
    ("Serie_A", "Monza Atalanta", "2026-11-08T14:00:00Z"),
    ("Serie_A", "Genoa Milan", "2026-11-08T14:00:00Z"),
    ("Serie_A", "Inter Como", "2026-11-08T17:00:00Z"),
    ("La_liga", "Elche Betis", "2026-11-08T13:00:00Z"),
    ("La_liga", "Real Sociedad Rayo", "2026-11-08T15:15:00Z"),
    ("La_liga", "Celta Levante", "2026-11-08T17:30:00Z"),
    ("La_liga", "Villarreal Getafe", "2026-11-08T17:30:00Z"),
    ("EPL", "Brighton Brentford", "2026-11-08T14:00:00Z"),
    ("EPL", "Palace Liverpool", "2026-11-08T14:00:00Z"),
    ("EPL", "Ipswich Bournemouth", "2026-11-08T14:00:00Z"),
    ("EPL", "Sunderland Chelsea", "2026-11-08T14:00:00Z"),
    ("EPL", "ManUtd Villa", "2026-11-08T16:30:00Z"),
    ("Ligue_1", "Rennes Lille", "2026-11-08T14:00:00Z"),
    ("Ligue_1", "Angers Nice", "2026-11-08T16:15:00Z"),
    ("Ligue_1", "Le Havre Lorient", "2026-11-08T16:15:00Z"),
    ("Ligue_1", "Le Mans Monaco", "2026-11-08T16:15:00Z"),
    ("Ligue_1", "Brest Lyon", "2026-11-08T16:15:00Z"),
    ("Bundesliga", "Koln Leverkusen", "2026-11-08T14:30:00Z"),
    ("Bundesliga", "Freiburg Union Berlin", "2026-11-08T16:30:00Z"),
]''',
    '''# Dispatch slate for Gamma cross-check: the ACTUAL Mon/Tue ESPN slate
# (dispatch premise of a Nov-10/11 Championship round is wrong; this slate
# documents what really is scheduled in the entry window)
DISPATCH_SLATE = [
    ("La_liga_2", "CD Sabadell Real Sociedad II", "2026-11-09T19:30:00Z"),
    ("La_liga_2", "Las Palmas Eldense", "2026-11-09T19:30:00Z"),
    ("Copa del Rey", "Anaitasuna Alaves", "2026-11-10T18:00:00Z"),
    ("Copa del Rey", "Pamplona Eibar", "2026-11-10T18:00:00Z"),
    ("Copa del Rey", "Amorebieta Logrones", "2026-11-10T19:00:00Z"),
    ("Copa del Rey", "Mijas Real Jaen", "2026-11-10T19:00:00Z"),
    ("Copa del Rey", "Trival Valderas Leganes", "2026-11-10T19:00:00Z"),
    ("Copa del Rey", "Tavernes Valencia", "2026-11-10T20:00:00Z"),
    ("EFL Trophy", "Barnet Leyton Orient", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Bristol Rovers Reading", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Burton Albion Notts County", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Crewe Alexandra Wigan Athletic", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Grimsby Town Nottingham Forest U21", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Huddersfield Town Liverpool U21", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Leicester City Walsall", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Mansfield Town Chesterfield", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Northampton Town Gillingham", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Oxford United Cheltenham Town", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Plymouth Argyle Swindon Town", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Stevenage Fulham U21", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Stockport County Tranmere Rovers", "2026-11-10T19:00:00Z"),
    ("EFL Trophy", "Bradford City York City", "2026-11-10T19:30:00Z"),
    ("EFL Trophy", "Bromley Milton Keynes Dons", "2026-11-10T19:30:00Z"),
    ("EFL Trophy", "Crawley Town Brentford U21", "2026-11-10T19:30:00Z"),
    ("EFL Trophy", "Colchester United Ipswich Town U21", "2026-11-10T19:45:00Z"),
]''',
    "dispatch slate")

# ---- 9. build_staleness -> r44 version ----
OLD_STALE = '''def build_staleness(snapshot):
    """r41/r43a dynamic staleness: xG bases reused from r41 (fresh through
    Sat Nov-7 for Big-5 + Eredivisie per r41 runtime check), so a club is
    flagged only when its last snapshot league match predates the prior
    league round - i.e. genuinely missing games. Sunday-slate clubs cannot
    be stale: their last completed league match is inside both snapshots."""
    thresholds = {lg: "2026-10-30" for lg in (
        "EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1",
        "Championship", "Eredivisie")}
    out = {}
    for lgk in list(snapshot.keys()):
        if not lgk.endswith("_2026"):
            continue
        lg = lgk[:-5]
        thr = datetime.strptime(thresholds.get(lg, "2026-10-30"), "%Y-%m-%d")
        for t in (snapshot.get(lgk) or {}).get("teams", {}).values():
            hist = [e for e in (t.get("history") or [])
                    if e.get("xG") is not None]
            if not hist:
                continue
            last = max(datetime.strptime(str(e["date"])[:10], "%Y-%m-%d")
                       for e in hist)
            if last < thr:
                out[t["title"]] = {
                    "missing": 1,
                    "detail": ("last snapshot league match %s predates %s "
                               "(1-round stale); treat conservatively"
                               % (last.date().isoformat(),
                                  thresholds.get(lg, "2026-10-30")))}
    return out'''
NEW_STALE = '''def _norm_local(v):
    sv = "".join(c for c in unicodedata.normalize("NFKD", str(v or "").lower())
                 if not unicodedata.combining(c))
    return re.sub(r"\\s+", " ", re.sub(r"[^a-z0-9 ]", " ", sv)).strip()


def build_staleness(snapshot):
    """r44 staleness: Big-5 pointer (r41 merge) ends Sat Nov-7 and the
    Eredivisie refetch ends Sat Nov-7, so every Sunday 2026-11-08 league
    result is UNMERGED. The exact Sunday-participant set is taken from the
    r43e ESPN capture (espn_fixtures_43e.json, date 20261108); a snapshot
    club that played Sun Nov-8 and has no 2026-11-08 history entry is
    flagged 1-round stale (would matter only if modeled - this window has
    zero modelable fixtures). Generic pre-Oct-30 fallback retained."""
    out = {}
    sunday_names = []
    try:
        espn_raw = json.load(open(f"{HOME}/round43/raw/espn_fixtures_43e.json"))
        for label, evs in (espn_raw.get("20261108") or {}).items():
            if not isinstance(evs, list):
                continue
            for ev in evs:
                teams = ev.get("teams") or {}
                for side in ("home", "away"):
                    nm = (teams.get(side) or {}).get("name")
                    if nm:
                        sunday_names.append((label, nm, _norm_local(nm)))
    except Exception as e:
        print("sunday espn capture unreadable:", repr(e), flush=True)
    n_sun = 0
    for lgk in list(snapshot.keys()):
        if not lgk.endswith("_2026"):
            continue
        lg = lgk[:-5]
        thr = datetime.strptime("2026-10-30", "%Y-%m-%d")
        for t in (snapshot.get(lgk) or {}).get("teams", {}).values():
            hist = [e for e in (t.get("history") or [])
                    if e.get("xG") is not None]
            if not hist or not t.get("title"):
                continue
            dates = [str(e["date"])[:10] for e in hist]
            last = max(datetime.strptime(d, "%Y-%m-%d") for d in dates)
            has_sunday = any(d == "2026-11-08" for d in dates)
            played_sunday = any(
                nn and (nn == _norm_local(t["title"])
                        or (len(nn) >= 5 and nn in _norm_local(t["title"]))
                        or (len(_norm_local(t["title"])) >= 5
                            and _norm_local(t["title"]) in nn))
                for _, _, nn in sunday_names)
            if played_sunday and not has_sunday:
                n_sun += 1
                out[t["title"]] = {
                    "missing": 1, "league": lg,
                    "detail": ("played Sun 2026-11-08 (r43e ESPN capture) but "
                               "no 2026-11-08 entry in its snapshot block "
                               "(pointer cut pre-Sunday): 1-round stale if "
                               "modeled; FotMob backfill allowed per dispatch "
                               "but NOT needed - no modelable fixture this "
                               "window involves this club")}
            elif last < thr:
                out[t["title"]] = {
                    "missing": 1, "league": lg,
                    "detail": ("last snapshot league match %s predates "
                               "2026-10-30 (missing games); treat "
                               "conservatively" % last.date().isoformat())}
    print("sunday-unmerged stale flags: %d (report-only; zero modeled "
          "fixtures this window)" % n_sun, flush=True)
    return out'''
rep(OLD_STALE, NEW_STALE, "build_staleness")

# ---- 10. copa coverage label ----
rep('''            "coverage": ("modeled" if (home and away) else
                         "board-only (no model coverage)" if lg in BOARD_ONLY
                         else "model-void (club not in snapshot universe)"),''',
    '''            "coverage": ("modeled" if (home and away) else
                         "model-void (cross-tier cup: minnow opponent "
                         "outside snapshot universe)" if lg == "Copa del Rey"
                         else "board-only (no model coverage)" if lg in BOARD_ONLY
                         else "model-void (club not in snapshot universe)"),''',
    "copa coverage label")

# ---- 11. scan meta ----
rep('''        "scan": "soccer-euro-day-window", "round": 43, "sub_scan": "euro_day_43A",''',
    '''        "scan": "soccer-mon-tue-window", "round": 44, "sub_scan": "mon_tue_44A",''',
    "scan meta")

# ---- 12. dispatch note ----
OLD_NOTE = '''        "dispatch_note": (
            "ROUND-43A Europe Sunday DAY window scan (05:30Z-17:59Z Nov-8); "
            "scan executed with early slate post-kickoff (board historical) "
            "and afternoon slate T-0.3h..T-4.3h; held #67 Le Mans-Monaco / "
            "#68 Brest-Lyon O2.5 / #63 ManUtd-Villa marks fetched separately; "
            "R41 3 news-killed passers re-checked at fresh prices; untagged "
            "leagues are raw-board-only; PAPER ONLY, no DB writes, no orders"),'''
NEW_NOTE = '''        "dispatch_note": (
            "ROUND-44A Monday-Tuesday window scan (2026-11-09T01:30Z.."
            "2026-11-10T23:59:59Z entry window; enumeration through Wed "
            "Nov-11T23:59Z, Wednesday rows board-only outside entry window). "
            "CALENDAR FINDING: the dispatch premise of a Nov-10/11 "
            "Championship midweek round is WRONG - Championship round 15 "
            "ended Sat Nov-7, round 16 is Nov-21/22 (international break); "
            "Gamma's 69 active efl-championship events have no kickoff "
            "before 2026-11-21; ESPN eng.2 shows zero Mon-Wed games. No "
            "Monday Big-5 league games exist this week. Window content: "
            "Liga MX (post-kick), lower-tier European/South American "
            "leagues, Copa del Rey (cross-tier model-void, board-only), "
            "Womens CL (board-only), National League N/S. ZERO modelable "
            "fixtures -> no candidates, ENTER NOTHING. Sunday Nov-8 Big-5 "
            "results unmerged (pointer ends Nov-7): runtime STALE-XG flags "
            "on Sunday clubs; backfill not needed (none modeled). PAPER "
            "ONLY, no DB writes, no orders"),'''
rep(OLD_NOTE, NEW_NOTE, "dispatch note")

# ---- 13. provenance blocks ----
rep('''            "championship_snapshot": {
                "path": FOTMOB_CHAMP, "fresh_through_utc": "2026-11-03",
                "note": ("Championship Sunday games checked via tag sweep; "
                         "snapshot wired for coverage if any exist")},''',
    '''            "championship_snapshot": {
                "path": FOTMOB_CHAMP,
                "fresh_through_utc": "2026-11-07",
                "meta": json.load(open(FOTMOB_CHAMP + ".meta.json")),
                "note": ("NEW championship_20261108 snapshot per dispatch "
                         "(180 matches, 24 clubs x 15 rounds, through Sat "
                         "Nov-7); NO Championship fixture exists in the "
                         "window (round 16 = Nov-21/22; Gamma next champ "
                         "kickoff 2026-11-21) - loaded for coverage, unused")},''',
    "championship provenance")

rep('''            "selfcheck": "PASS 10/10 (re-run this session pre-scan "
                         "2026-11-08T13:40Z)",''',
    '''            "selfcheck": "PASS 10/10 (re-run this session pre-scan "
                         "2026-11-09T07:06Z)",''',
    "selfcheck provenance")

rep('''            "big5_refresh": {
                "merged": "round41/raw/xg_fotmob_big5_merged.json",
                "detail": ("REUSED unchanged from r41 (pointer untouched): "
                           "round25 Understat through Oct-31 + FotMob Nov-"
                           "1..Nov-8 backfill; Sat Nov-7 Big-5 games MERGED; "
                           "zero staleness per r41 runtime check, re-verified "
                           "at runtime this scan")},''',
    '''            "big5_refresh": {
                "merged": "round41/raw/xg_fotmob_big5_merged.json",
                "detail": ("REUSED unchanged from r41 (pointer untouched): "
                           "round25 Understat through Oct-31 + FotMob Nov-"
                           "1..Nov-7 backfill; Sun Nov-8 Big-5 games NOT "
                           "merged (snapshot cut 02:24Z pre-Sunday) -> "
                           "runtime STALE-XG flags on Sunday clubs; FotMob "
                           "Sunday backfill ALLOWED per dispatch but NOT "
                           "run: zero modelable fixtures this window, no "
                           "modeled club affected")},''',
    "big5 provenance")

# ---- 14. budget ----
OLD_BUDGET = '''        "budget": {"max_new_entries_usd_this_agent": 200,
                   "note": ("ROUND-43A dispatch: this agent proposes <=$200 "
                            "total; coordinator arbitrates across 3 agents; "
                            "soccer pool $3,000 @ $1,700 headroom incl. "
                            "$1,100 UCL/UEL reserve (unchanged: r42 entered "
                            "nothing)")},'''
NEW_BUDGET = '''        "budget": {"max_new_entries_usd_this_agent": 400,
                   "note": ("ROUND-44A dispatch: <=$400 total proposals this "
                            "window; nothing passes = enter nothing (this "
                            "scan: zero modelable fixtures -> zero "
                            "proposals)")},'''
rep(OLD_BUDGET, NEW_BUDGET, "budget")

open(DST, "w", encoding="utf-8").write(s)
print("wrote", DST, len(s), "bytes (src", n0, ")")
