#!/usr/bin/env python3
"""Build round41/raw/scan41.py from round40/raw/scan40.py (paper-only).

Round-41 changes applied by this patch:
  1. docstring -> ROUND-41 24h Sunday window
  2. window LO/HI -> 2026-11-08T01:15Z .. 2026-11-09T01:15Z
  3. paths -> round41/raw (events_window_41, espn_fixtures_41)
  4. Eredivisie snapshot -> round41/raw/xg_fotmob_eredivisie.json (refetched
     this session, 103 matches through Sat Nov-7)
  5. held fixtures -> #67 Le Mans-Monaco MW NO 6236736, #68 Brest-Lyon
     O2.5 Over 6239548, #63 ManUtd-Villa MW NO 6237007
  6. held-fixture matching extended: raw-name subset OR canon-resolved title
     subset (Brest-Lyon Gamma titles 'Stade Brestois 29'/'Olympique Lyonnais'
     never subset-match raw short names)
  7. canon_team: exact-alias lookup moved BEFORE the deny-token check
     (unblocks 'AZ'/'NEC' Gamma titles previously swallowed by
     CANON_DENY_EXACT; deny still applies to non-alias strings)
  8. STALENESS hardcoded dict -> runtime builder (snapshot last-match-date
     thresholds); Big-5 merged through Sat Nov-7 this session
  9. TEAM_ALIASES extended for the full Sunday slate
 10. provenance/dispatch notes/round number -> r41
"""
import re
import sys

SRC = "/home/ubuntu/paper-sim/round40/raw/scan40.py"
DST = "/home/ubuntu/paper-sim/round41/raw/scan41.py"

s = open(SRC, encoding="utf-8").read()
n0 = len(s)


def rep(old, new, label):
    global s
    assert old in s, "MISSING BLOCK: " + label
    assert s.count(old) == 1, "NON-UNIQUE BLOCK: " + label
    s = s.replace(old, new)
    print("ok:", label)


# ---- 1. docstring ----
NEW_DOC = '''"""ROUND-41 scan (paper-only): 24h soccer window 2026-11-08T01:15Z..2026-11-09T01:15Z.

Coverage (dispatch, frozen):
  Big-5 (EPL, Bundesliga, La_liga, Serie_A, Ligue_1): FULL market families,
    match_winner eligible-deprioritized $150.
  Eredivisie: TOTALS FAMILY ONLY (gate-E); promoted clubs (ADO/Cambuur/
    Willem II) mostly die on the 6c variant bar - modeled anyway, kills
    documented. Championship: NO Sunday games this window (tag sweep 0).
  Belgian/Turkish/Portuguese/Scottish + untagged leagues: board-only,
    prices reported, no model coverage, no entry.
  Cross-league MW: wired through gates.check_cross_league_mw (bridge_present
    + worst>=+5c) and sized via risk_policy sizing_tier(CROSS_LEAGUE_ML_CLASS)
    per DELIVERY_PLAN section 72 (no cross pairs expected this window; all
    Sunday fixtures are single-league).

xG bases (both refreshed THIS session):
  Big-5: understat_latest.json pointer -> round41/raw/xg_fotmob_big5_merged.json
    (round25 Understat through Oct-31 + FotMob Nov-1..Nov-8 backfill; Sat Nov-7
    games MERGED; merge41.py adds 8 title overrides for Saturday clubs).
  Eredivisie: round41/raw/xg_fotmob_eredivisie.json refetched 02:34Z, 103
    completed matches through Sat Nov-7 (Telstar-Fortuna, ADO-Sparta,
    Excelsior-GAE now in). STALENESS therefore built at runtime from
    last-match-date thresholds; expected ZERO stale clubs in the Sunday slate
    (every modeled club's last completed league match is in its snapshot).

Held fixtures (marks only, NO new positions):
  #67 Le Mans-Monaco MW NO $150 @0.44 (Sun 16:15Z, market 6236736)
  #68 Brest-Lyon O2.5 Over $250 @0.51 (Sun 16:15Z, market 6239548)
  #63 ManUtd-Villa MW NO $150 @0.70 (Sun 16:30Z, market 6237007)

Frozen gates (library 1a2760bc, selfcheck re-run this session pre-scan):
  net>=+5c after sports fee 0.05 (8c if under-risk), worst>=+4c, var<=6c,
  liq>=$5k, $250 walk fill, entry .10-.92, 50-50 haircut on net edge, news
  concordance (one focused search per serious candidate), scoreline
  concordance (r32), one position per fixture, spreads flagged-only.
Entry timing: scan ~9-18h pre-kick; T-2h XI recheck condition noted per
candidate; current predicted-lineup news captured in the news checks.
"""'''
s = re.sub(r'"""ROUND-40 scan.*?"""', NEW_DOC, s, count=1, flags=re.S)
print("ok: docstring replaced")

# ---- 2/3. paths + window ----
rep('OUTDIR = f"{HOME}/round40/raw"', 'OUTDIR = f"{HOME}/round41/raw"', "outdir")
rep('EVENTS = f"{OUTDIR}/events_window_40.json"', 'EVENTS = f"{OUTDIR}/events_window_41.json"', "events")
rep('ESPN = f"{OUTDIR}/espn_fixtures_40.json"', 'ESPN = f"{OUTDIR}/espn_fixtures_41.json"', "espn")
rep('LO = "2026-11-07T13:50:00Z"', 'LO = "2026-11-08T01:15:00Z"', "lo")
rep('HI = "2026-11-08T01:50:00Z"', 'HI = "2026-11-09T01:15:00Z"', "hi")

# ---- 4. eredivisie snapshot path ----
rep('ERED = f"{HOME}/round39/raw/xg_fotmob_eredivisie.json"',
    'ERED = f"{HOME}/round41/raw/xg_fotmob_eredivisie.json"', "ered path")

# ---- 5. held fixtures ----
rep('''HELD_IDS = {  # marks-only positions from the dispatch
    "64_mainz_bayern_btts_yes": 6176123,
    "65_osasuna_tt_o05": 6180838,
    "66_valencia_rm_u35": 6180689,
}
HELD_PAIRS = [  # held fixtures: marks only, no new positions
    ("Mainz 05", "Bayern Munich"),
    ("Osasuna", "Athletic Club"),
    ("Valencia", "Real Madrid"),
]''',
    '''HELD_IDS = {  # marks-only positions from the dispatch
    "67_le_mans_monaco_mw_no": 6236736,
    "68_brest_lyon_o25_over": 6239548,
    "63_manutd_villa_mw_no": 6237007,
}
HELD_PAIRS = [  # held fixtures: marks only, no new positions
    ("Le Mans", "Monaco"),
    ("Brest", "Lyon"),
    ("Manchester United", "Aston Villa"),
]''', "held ids+pairs")

# ---- 8. staleness -> runtime builder ----
rep('''STALENESS = {
    "Cardiff City": {"missing": 1, "detail": "Nov-4 H v West Ham not in snapshot (snapshot thru Nov-3)"},
    "West Ham United": {"missing": 1, "detail": "Nov-4 A at Cardiff not in snapshot"},
    "Wrexham": {"missing": 1, "detail": "Nov-4 H v Middlesbrough not in snapshot"},
    "Middlesbrough": {"missing": 1, "detail": "Nov-4 A at Wrexham not in snapshot"},
    "Bristol City": {"missing": 1, "detail": "Nov-4 H v Wolverhampton not in snapshot"},
    "Wolverhampton Wanderers": {"missing": 1, "detail": "Nov-4 A at Bristol City not in snapshot"},
}
STALE_CLUBS = set(STALENESS)''',
    '''STALENESS = {}   # built at runtime by build_staleness() after snapshot load
STALE_CLUBS = set()


def build_staleness(snapshot):
    """r41 dynamic staleness: both xG bases were refreshed this session
    (Big-5 merged through Sat Nov-7; Eredivisie refetched through Sat Nov-7),
    so a club is flagged only when its last snapshot league match predates
    the prior league round - i.e. genuinely missing games. Sunday-slate
    clubs cannot be stale: their last completed league match (prior weekend,
    Oct 31-Nov 2) is inside both snapshots."""
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
    return out''', "staleness builder")

# ---- 9. aliases ----
rep('''    "pec zwolle": "PEC Zwolle", "willem ii": "Willem II",
}''',
    '''    "pec zwolle": "PEC Zwolle", "willem ii": "Willem II",
    # --- r41 Sunday slate ---
    "brighton & hove albion fc": "Brighton",
    "brighton hove albion": "Brighton", "brighton": "Brighton",
    "brentford fc": "Brentford", "brentford": "Brentford",
    "crystal palace fc": "Crystal Palace", "crystal palace": "Crystal Palace",
    "liverpool fc": "Liverpool", "liverpool": "Liverpool",
    "ipswich town fc": "Ipswich", "ipswich town": "Ipswich",
    "ipswich": "Ipswich",
    "afc bournemouth": "Bournemouth", "bournemouth fc": "Bournemouth",
    "bournemouth": "Bournemouth",
    "sunderland afc": "Sunderland", "sunderland": "Sunderland",
    "chelsea fc": "Chelsea", "chelsea": "Chelsea",
    "manchester united fc": "Manchester United",
    "manchester united": "Manchester United",
    "man utd": "Manchester United",
    "aston villa fc": "Aston Villa", "aston villa": "Aston Villa",
    "koln": "FC Cologne", "fc koln": "FC Cologne",
    "1 fc koln": "FC Cologne",
    "bayer 04 leverkusen": "Bayer Leverkusen",
    "sc freiburg": "Freiburg", "freiburg": "Freiburg",
    "1 fc union berlin": "Union Berlin",
    "union berlin": "Union Berlin",
    "tsg 1899 hoffenheim": "Hoffenheim",
    "tsg hoffenheim": "Hoffenheim", "hoffenheim": "Hoffenheim",
    "fc schalke 04": "Schalke 04", "schalke 04": "Schalke 04",
    "ssc napoli": "Napoli", "napoli": "Napoli",
    "ss lazio": "Lazio", "lazio": "Lazio",
    "ac monza": "Monza", "monza": "Monza",
    "atalanta bc": "Atalanta", "atalanta": "Atalanta",
    "genoa cfc": "Genoa", "genoa": "Genoa",
    "ac milan": "AC Milan", "milan": "AC Milan",
    "fc internazionale milano": "Inter",
    "internazionale": "Inter", "inter milan": "Inter", "inter": "Inter",
    "como 1907": "Como", "como": "Como",
    "acf fiorentina": "Fiorentina", "fiorentina": "Fiorentina",
    "juventus fc": "Juventus", "juventus": "Juventus",
    "elche cf": "Elche", "elche": "Elche",
    "real betis balompie": "Real Betis", "real betis": "Real Betis",
    "real sociedad de futbol": "Real Sociedad",
    "real sociedad": "Real Sociedad",
    "rayo vallecano de madrid": "Rayo Vallecano",
    "rayo vallecano": "Rayo Vallecano",
    "rc celta de vigo": "Celta Vigo", "celta de vigo": "Celta Vigo",
    "celta vigo": "Celta Vigo",
    "levante ud": "Levante", "levante": "Levante",
    "villarreal cf": "Villarreal", "villarreal": "Villarreal",
    "getafe cf": "Getafe", "getafe": "Getafe",
    "club atletico de madrid": "Atletico Madrid",
    "atletico de madrid": "Atletico Madrid",
    "atletico madrid": "Atletico Madrid",
    "fc barcelona": "Barcelona", "barcelona": "Barcelona",
    "stade rennais fc 1901": "Rennes", "stade rennais fc": "Rennes",
    "stade rennais": "Rennes", "rennais": "Rennes", "rennes": "Rennes",
    "lille osc": "Lille", "lille": "Lille",
    "angers sco": "Angers", "angers": "Angers",
    "ogc nice": "Nice", "nice": "Nice",
    "le havre ac": "Le Havre", "le havre": "Le Havre",
    "fc lorient": "Lorient", "lorient": "Lorient",
    "le mans fc": "Le Mans", "le mans": "Le Mans",
    "as monaco fc": "Monaco", "monaco": "Monaco",
    "stade brestois 29": "Brest", "stade brestois": "Brest",
    "brest": "Brest",
    "olympique lyonnais": "Lyon", "lyon": "Lyon",
    "racing club de lens": "Lens", "lens": "Lens",
    "olympique de marseille": "Marseille", "marseille": "Marseille",
}''', "aliases")

# ---- 7. canon_team alias-first ----
rep('''def canon_team(name):
    n = norm_name(name)
    if not n or n in CANON_DENY_EXACT:
        return None
    raw_l = strip_accents(str(name).strip().lower())
    alias = (TEAM_ALIASES.get(str(name).strip().lower())
             or TEAM_ALIASES.get(raw_l) or TEAM_ALIASES.get(n))
    if alias is not None and alias in TITLE_LEAGUE:
        return alias''',
    '''def canon_team(name):
    # r41: exact-alias lookup moved BEFORE the deny-token check so 'AZ' /
    # 'NEC' (Gamma titles) resolve via TEAM_ALIASES; the deny list still
    # blocks bare tokens that reach the substring fallback below.
    n = norm_name(name)
    raw_l = strip_accents(str(name).strip().lower())
    alias = (TEAM_ALIASES.get(str(name).strip().lower())
             or TEAM_ALIASES.get(raw_l) or TEAM_ALIASES.get(n))
    if alias is not None and alias in TITLE_LEAGUE:
        return alias
    if not n or n in CANON_DENY_EXACT:
        return None''', "canon alias-first")

# ---- 6. held matching ----
rep('''        fkey = fixture_key(home_raw, away_raw)
        held_here = any(
            {norm_name(h), norm_name(a)} <=
            {norm_name(home_raw), norm_name(away_raw)}
            for h, a in HELD_PAIRS)''',
    '''        fkey = fixture_key(home_raw, away_raw)
        raw_norms = {norm_name(x) for x in (home_raw, away_raw) if x}
        resolved = {x for x in (home, away) if x}
        held_here = any(
            ({norm_name(h), norm_name(a)} <= raw_norms)
            or ({h, a} <= resolved)
            for h, a in HELD_PAIRS)''', "held matching")

# ---- registry print + staleness build call ----
rep('    print("registry titles:", len(TITLE_LEAGUE), flush=True)',
    '''    print("registry titles:", len(TITLE_LEAGUE), flush=True)
    STALENESS.update(build_staleness(snapshot))
    STALE_CLUBS.update(STALENESS)
    print("runtime staleness flags:", len(STALENESS),
          sorted(STALENESS)[:10], flush=True)''', "staleness build call")

# ---- league policy docstring ----
rep('"""Dispatch-frozen league policy for round 40."""',
    '"""Dispatch-frozen league policy for round 41."""', "policy docstring")

# ---- stale flag text ----
rep('''                    if stale_here:
                        flags.append(
                            "STALE-XG: %s (Nov-4 midweek round missing; 1 league "
                            "game each)" % ", ".join(stale_here))''',
    '''                    if stale_here:
                        flags.append("STALE-XG: %s (%s)" % (
                            ", ".join(stale_here),
                            "; ".join(STALENESS[c]["detail"]
                                      for c in stale_here if c in STALENESS)))''',
    "stale flag text")

# ---- provenance ----
rep('''            "eredivisie_snapshot": {
                "path": ERED,
                "meta": json.load(open(ERED + ".meta.json")),
                "fresh_through_utc": "2026-11-06 19:00Z (100 matches 2026/27)"},''',
    '''            "eredivisie_snapshot": {
                "path": ERED,
                "meta": json.load(open(ERED + ".meta.json")),
                "fresh_through_utc": ("2026-11-07 20:00Z refetched this "
                                      "session (103 matches 2026/27; Sat "
                                      "Nov-7 round merged)")},''', "ered provenance")
rep('''            "championship_snapshot": {
                "path": FOTMOB_CHAMP, "fresh_through_utc": "2026-11-03",
                "nov4_round_missing": ("Cardiff-West Ham, Wrexham-Middlesbrough, "
                                       "Bristol City-Wolves NOT in snapshot -> 6 "
                                       "clubs 1-game stale")},''',
    '''            "championship_snapshot": {
                "path": FOTMOB_CHAMP, "fresh_through_utc": "2026-11-03",
                "note": ("NO Sunday Championship games in the r41 window "
                         "(tag sweep in_window=0); snapshot wired but "
                         "unused this round")},''', "champ provenance")
rep('''            "library_commit": "1a2760bc",
            "selfcheck": "PASS 10/10 (re-run this session pre-scan)",''',
    '''            "library_commit": "1a2760bc",
            "selfcheck": "PASS 10/10 (re-run this session pre-scan "
                         "2026-11-08T02:11Z)",
            "big5_refresh": {
                "merged": "round41/raw/xg_fotmob_big5_merged.json",
                "detail": ("FotMob backfill Nov-1..Nov-8 + round25 Understat; "
                           "Sat Nov-7 Big-5 games MERGED (45 window matches, "
                           "all with xG); merge41.py adds 8 title overrides; "
                           "pointer re-pointed after validation (last dates "
                           "EPL/La_liga/Serie_A/Bundesliga/Ligue_1 = "
                           "Nov-7 17:30/20:00/19:45/17:30/19:45Z)")},''', "provenance misc")

# ---- dispatch note + round id ----
rep('''    out = {
        "scan": "soccer-12h-window", "round": 40,''',
    '''    out = {
        "scan": "soccer-24h-window", "round": 41,''', "round id")
rep('''        "dispatch_note": (
            "ROUND-40 12h window scan; scan executed mid-window (~15:50Z), "
            "fixtures kicking <= scan time are post-kickoff (report-only "
            "boards); held #64/#65/#66 marks fetched separately; PAPER ONLY, "
            "no DB writes, no real orders"),''',
    '''        "dispatch_note": (
            "ROUND-41 24h Sunday window scan (slate + late-Sunday-night); "
            "scan executed ~9-18h pre-kick; all modeled fixtures pre-kickoff "
            "at scan; held #67 Le Mans-Monaco / #68 Brest-Lyon O2.5 / #63 "
            "ManUtd-Villa marks fetched separately; untagged leagues "
            "(A-League, CSL, Americas etc.) are raw-board-only; PAPER ONLY, "
            "no DB writes, no real orders"),''', "dispatch note")

open(DST, "w", encoding="utf-8").write(s)
print("wrote", DST, len(s), "bytes (from", n0, ")")
