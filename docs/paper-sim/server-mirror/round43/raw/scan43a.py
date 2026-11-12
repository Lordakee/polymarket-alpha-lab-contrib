"""ROUND-43A scan (paper-only): EUROPE SUNDAY DAY window
2026-11-08T05:30Z .. 2026-11-08T17:59:59Z.

Coverage (dispatch, frozen):
  Big-5 (EPL, Bundesliga, La_liga, Serie_A, Ligue_1): FULL market families,
    match_winner eligible-deprioritized $150.
  Eredivisie: TOTALS FAMILY ONLY (gate-E); promoted clubs (Cambuur) modeled
    anyway, kills documented.
  Board-only leagues (Belgian/Turkish/Portuguese/Scottish + untagged):
    prices reported, no model coverage, no entry.
  Cross-league MW: wired through gates.check_cross_league_mw (bridge_present
    + worst>=+5c) and sized via risk_policy sizing_tier(CROSS_LEAGUE_ML_CLASS)
    per DELIVERY_PLAN section 72.

xG bases (REUSED, NOT re-refreshed per dispatch; R41 runtime check = ZERO
  staleness):
  Big-5: understat_latest.json pointer -> round41/raw/xg_fotmob_big5_merged.json
    (round25 Understat through Oct-31 + FotMob Nov-1..Nov-8 backfill; Sat Nov-7
    games MERGED).
  Eredivisie: round41/raw/xg_fotmob_eredivisie.json (103 completed matches
    through Sat Nov-7).
  Staleness rebuilt at runtime (last-match-date thresholds); expected ZERO
  stale clubs in the Sunday slate.

Held fixtures (marks only, NO new positions):
  #67 Le Mans-Monaco MW NO $150 @0.44 (Sun 16:15Z, market 6236736)
  #68 Brest-Lyon O2.5 Over $250 @0.51 (Sun 16:15Z, market 6239548)
  #63 ManUtd-Villa MW NO $150 @0.70 (Sun 16:30Z, market 6237007)

R41 news-kill recheck (revive ONLY if ask moved >=3c in our favor AND fresh
search shows news flipped; default dead):
  6241503 Rayo ML away   (R41 ask 0.22, vwap250 0.22, p_med 0.2908)
  6239948 Genoa-Milan BTTS yes (R41 ask 0.49, vwap250 0.4972, p_med 0.5696)
  6239569 Brentford TT O1.5 (R41 ask 0.35, vwap250 0.3544, p_med 0.4250)

Frozen gates (library 1a2760bc, selfcheck re-run this session pre-scan):
  net>=+5c after sports fee 0.05 (8c if under-risk), worst>=+4c, var<=6c,
  liq>=$5k, $250 walk fill, entry .10-.92, 50-50 haircut on net edge, news
  concordance (one focused search per serious candidate), scoreline
  concordance (r32), one position per fixture, spreads flagged-only.
Budget: THIS AGENT PROPOSES <=$200 TOTAL (coordinator arbitrates across 3
agents); MW stake $150, totals/BTTS stake $250 (a passing $250-class
candidate is reported but exceeds this agent's proposal cap -> coordinator
decision).
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import (  # noqa: E402
    fotmob,
    gates,
    league_strength,
    risk_policy,
    soccer_model,
    xg,
)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
HOME = "/home/ubuntu/paper-sim"
UNDERSTAT_LATEST = f"{HOME}/understat_latest.json"
UNDERSTAT_POINTER = f"{HOME}/understat_latest_pointer.json"
FOTMOB_CHAMP = f"{HOME}/round31/raw/xg_fotmob_championship.json"
ERED = f"{HOME}/round41/raw/xg_fotmob_eredivisie.json"
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"
OUTDIR = f"{HOME}/round43/raw"
OUT = f"{OUTDIR}/euro_day_scan.json"
EVENTS = f"{OUTDIR}/events_window_43a.json"
ESPN = f"{OUTDIR}/espn_fixtures_43a.json"
LO = "2026-11-08T05:30:00Z"
HI = "2026-11-08T17:59:59Z"
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")
TOTALS_ONLY = ("Championship", "Eredivisie")
BOARD_ONLY = ("Belgian Pro League", "Turkish Super Lig", "Primeira Liga",
              "Scottish Premiership")

NOW = datetime.now(timezone.utc)
NOW_S = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

LEAGUE_TAGS = {
    "epl": "EPL", "premier-league": "EPL",
    "efl-championship": "Championship", "championship": "Championship",
    "bundesliga": "Bundesliga", "la-liga": "La_liga", "sea": "Serie_A",
    "ligue-1": "Ligue_1", "ere": "Eredivisie",
    "bel1": "Belgian Pro League", "tur": "Turkish Super Lig",
    "primeira-liga": "Primeira Liga",
    "scottish-premiership": "Scottish Premiership",
}

HELD_IDS = {  # marks-only positions from the dispatch
    "67_le_mans_monaco_mw_no": 6236736,
    "68_brest_lyon_o25_over": 6239548,
    "63_manutd_villa_mw_no": 6237007,
}
HELD_PAIRS = [  # held fixtures: marks only, no new positions
    ("Le Mans", "Monaco"),
    ("Brest", "Lyon"),
    ("Manchester United", "Aston Villa"),
]

# R41 news-killed passers (recheck at fresh prices; revive rules in docstring)
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
}

# Dispatch slate for Gamma cross-check ("include anything missed")
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
]

STALENESS = {}   # built at runtime by build_staleness() after snapshot load
STALE_CLUBS = set()


def build_staleness(snapshot):
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
    return out


TEAM_ALIASES = {
    # --- EPL ---
    "leeds united": "Leeds", "leeds": "Leeds",
    "tottenham hotspur": "Tottenham", "tottenham": "Tottenham", "spurs": "Tottenham",
    "arsenal fc": "Arsenal", "arsenal": "Arsenal",
    "hull city fc": "Hull", "hull city": "Hull", "hull": "Hull",
    "fulham fc": "Fulham", "fulham": "Fulham",
    "newcastle united fc": "Newcastle United", "newcastle united": "Newcastle United",
    "newcastle": "Newcastle United",
    "nottingham forest fc": "Nottingham Forest", "nottingham forest": "Nottingham Forest",
    "nottm forest": "Nottingham Forest", "forest": "Nottingham Forest",
    "manchester city fc": "Manchester City", "manchester city": "Manchester City",
    "man city": "Manchester City",
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
    # --- Championship (kept from r38/41 wiring) ---
    "bristol city fc": "Bristol City", "bristol city": "Bristol City",
    "norwich city fc": "Norwich City", "norwich city": "Norwich City",
    "portsmouth fc": "Portsmouth", "portsmouth": "Portsmouth",
    "stoke city fc": "Stoke City", "stoke city": "Stoke City",
    "wrexham fc": "Wrexham", "wrexham afc": "Wrexham", "wrexham": "Wrexham",
    "wolverhampton wanderers fc": "Wolverhampton Wanderers",
    "wolverhampton wanderers": "Wolverhampton Wanderers",
    "wolverhampton": "Wolverhampton Wanderers", "wolves": "Wolverhampton Wanderers",
    "birmingham city fc": "Birmingham City", "birmingham city": "Birmingham City",
    "swansea city fc": "Swansea City", "swansea city": "Swansea City",
    "blackburn rovers fc": "Blackburn Rovers", "blackburn rovers": "Blackburn Rovers",
    "west ham united fc": "West Ham United", "west ham united": "West Ham United",
    "west ham": "West Ham United",
    "cardiff city fc": "Cardiff City", "cardiff city": "Cardiff City",
    "burnley fc": "Burnley", "burnley": "Burnley",
    "charlton athletic fc": "Charlton Athletic", "charlton athletic": "Charlton Athletic",
    "sheffield united fc": "Sheffield United", "sheffield united": "Sheffield United",
    "preston north end fc": "Preston North End", "preston north end": "Preston North End",
    "southampton fc": "Southampton", "southampton": "Southampton",
    "queens park rangers": "Queens Park Rangers", "qpr": "Queens Park Rangers",
    "lincoln city fc": "Lincoln City", "lincoln city": "Lincoln City",
    "watford fc": "Watford", "watford": "Watford",
    "middlelsbrough": "Middlesbrough", "middlesbrough fc": "Middlesbrough",
    "middlesbrough": "Middlesbrough", "boro": "Middlesbrough",
    "west bromwich albion fc": "West Bromwich Albion",
    "west bromwich albion": "West Bromwich Albion",
    "west brom": "West Bromwich Albion", "wba": "West Bromwich Albion",
    "millwall fc": "Millwall", "millwall": "Millwall",
    # --- Bundesliga ---
    "bayern munchen": "Bayern Munich", "fc bayern munchen": "Bayern Munich",
    "bayern": "Bayern Munich",
    "borussia dortmund": "Borussia Dortmund", "dortmund": "Borussia Dortmund",
    "rb leipzig": "RasenBallsport Leipzig", "leipzig": "RasenBallsport Leipzig",
    "sv 07 elversberg": "Elversberg", "elversberg": "Elversberg",
    "sc paderborn 07": "Paderborn", "paderborn": "Paderborn",
    "vfb stuttgart": "VfB Stuttgart", "stuttgart": "VfB Stuttgart",
    "werder bremen": "Werder Bremen", "sv werder bremen": "Werder Bremen",
    "bayer leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "koln": "FC Cologne", "fc koln": "FC Cologne",
    "1 fc koln": "FC Cologne",
    "bayer 04 leverkusen": "Bayer Leverkusen",
    "sc freiburg": "Freiburg", "freiburg": "Freiburg",
    "1 fc union berlin": "Union Berlin",
    "union berlin": "Union Berlin",
    "tsg 1899 hoffenheim": "Hoffenheim",
    "tsg hoffenheim": "Hoffenheim", "hoffenheim": "Hoffenheim",
    "fc schalke 04": "Schalke 04", "schalke 04": "Schalke 04",
    # --- La Liga ---
    "rc deportivo a coruna": "Deportivo La Coruna",
    "deportivo a coruna": "Deportivo La Coruna",
    "deportivo la coruna": "Deportivo La Coruna",
    "rcd espanyol de barcelona": "Espanyol", "espanyol": "Espanyol",
    "real madrid cf": "Real Madrid", "real madrid": "Real Madrid",
    "valencia cf": "Valencia", "athletic club": "Athletic Club",
    "athletic bilbao": "Athletic Club", "ca osasuna": "Osasuna", "osasuna": "Osasuna",
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
    # --- Serie A ---
    "as roma": "Roma", "roma": "Roma", "us lecce": "Lecce", "lecce": "Lecce",
    "cagliari calcio": "Cagliari", "frosinone calcio": "Frosinone",
    "torino fc": "Torino", "parma calcio 1913": "Parma Calcio 1913",
    "bologna fc 1909": "Bologna", "us sassuolo calcio": "Sassuolo",
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
    # --- Ligue 1 ---
    "paris saint-germain fc": "Paris Saint Germain",
    "paris saint germain": "Paris Saint Germain", "psg": "Paris Saint Germain",
    "es troyes ac": "Troyes", "troyes": "Troyes", "aj auxerre": "Auxerre",
    "paris fc": "Paris FC",
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
    # --- Eredivisie ---
    "telstar 1963": "Telstar", "telstar": "Telstar",
    "sbv excelsior": "Excelsior", "excelsior": "Excelsior",
    "afc ajax": "Ajax", "ajax": "Ajax", "ajax amsterdam": "Ajax",
    "az": "AZ Alkmaar", "az alkmaar": "AZ Alkmaar", "az alkmaar fc": "AZ Alkmaar",
    "sc cambuur-leeuwarden": "Cambuur", "sc cambuur leeuwarden": "Cambuur",
    "sc cambuur": "Cambuur", "cambuur": "Cambuur", "cambuur leeuwarden": "Cambuur",
    "psv": "PSV Eindhoven", "psv eindhoven": "PSV Eindhoven",
    "feyenoord": "Feyenoord", "feyenoord rotterdam": "Feyenoord",
    "sc heerenveen": "SC Heerenveen", "heerenveen": "SC Heerenveen",
    "fc twente": "FC Twente", "twente": "FC Twente",
    "fc groningen": "FC Groningen", "groningen": "FC Groningen",
    "fc utrecht": "FC Utrecht", "utrecht": "FC Utrecht",
    "nec": "NEC Nijmegen", "nec nijmegen": "NEC Nijmegen",
    "go ahead eagles": "Go Ahead Eagles",
    "ado den haag": "ADO Den Haag", "den haag": "ADO Den Haag",
    "sparta rotterdam": "Sparta Rotterdam", "sparta": "Sparta Rotterdam",
    "fortuna sittard": "Fortuna Sittard", "fortuna": "Fortuna Sittard",
    "pec zwolle": "PEC Zwolle", "willem ii": "Willem II",
}
CANON_DENY_EXACT = {"az", "nec", "ofi", "ski", "if", "go", "sk", "fk", "fc",
                    "ac", "sc"}


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None
            last = e
            time.sleep(1.5 + i)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    if last:
        raise last
    return None


def norm_ts(ts):
    s = str(ts or "").strip()
    if not s:
        return ""
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return s


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_name(s):
    s = strip_accents(str(s or "").lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in {
        "fc", "cf", "ac", "sc", "afc", "1", "the", "de", "club", "calcio",
        "rc", "ud", "us", "as", "sv", "vfl", "vfb", "tsv", "spvgg", "fussball",
        "ballspielverein", "rasenballsport", "borussia", "eintracht", "bayer",
        "vlsi", "1899", "09"}]
    return " ".join(toks).strip()


ALL_TITLES = {}
TITLE_LEAGUE = {}


def canon_team(name):
    n = norm_name(name)
    raw_l = strip_accents(str(name).strip().lower())
    alias = (TEAM_ALIASES.get(str(name).strip().lower())
             or TEAM_ALIASES.get(raw_l) or TEAM_ALIASES.get(n))
    if alias is not None and alias in TITLE_LEAGUE:
        return alias
    if not n or n in CANON_DENY_EXACT:
        return None
    for t in ALL_TITLES:
        if norm_name(t) == n:
            return t
    if len(n) >= 5:
        for t in ALL_TITLES:
            tn = norm_name(t)
            if tn and (tn in n or n in tn):
                return t
    return None


def fixture_key(a, b):
    return "-".join(sorted([norm_name(a).replace(" ", ""),
                            norm_name(b).replace(" ", "")]))


def parse_market_sides(m, home, away):
    """[(token_idx, kind, side_id, line, team_side)] covering BOTH sides."""
    q = str(m.get("q") or "")
    s = strip_accents(q.lower())
    g = strip_accents(str(m.get("group") or "").lower())
    blob = s + " " + g
    if re.search(r"(1st|2nd|first|second)\s*half", blob) or "halftime" in blob:
        return None
    if any(w in blob for w in ("corner", "card", "penalt", "odd or even",
                               "score first", "exact score", "leading")):
        return None
    outcomes = m.get("outcomes") or []
    line_f = m.get("line")

    def find_line(text):
        nums = re.findall(r"\d+\.5", text)
        if nums:
            return float(nums[0])
        if line_f not in (None, ""):
            try:
                return float(line_f)
            except Exception:
                return None
        return None

    def team_side_of(name):
        resolved = canon_team(name)
        if resolved == home:
            return "home"
        if resolved == away:
            return "away"
        n = norm_name(name)
        if not n or n in CANON_DENY_EXACT:
            return None
        if len(n) >= 5:
            for cand, side in ((home, "home"), (away, "away")):
                cn = norm_name(cand)
                if cn and (cn in n or n in cn):
                    return side
        return None

    if s.startswith("spread") or re.search(r"\(\s*[-+]?\d+\.5\s*\)", blob):
        tm = re.search(r"spread:\s*(.+?)\s*\(\s*([-+]?\d+\.5)\s*\)", s)
        if not tm:
            return None
        team = team_side_of(tm.group(1))
        line = float(tm.group(2))
        if team is None:
            return None
        sides = []
        team_tok = None
        for i, o in enumerate(outcomes):
            ol = str(o).strip().lower()
            ot = team_side_of(str(o))
            if ot == team and ol not in ("yes", "no"):
                team_tok = i
            elif ol == "yes":
                sides.append((i, "spread", "cover", line, team))
            elif ol == "no":
                sides.append((i, "spread", "nocover", line, team))
        if team_tok is not None:
            sides = [(team_tok, "spread", "cover", line, team)]
            for i in range(len(outcomes)):
                if i != team_tok:
                    sides.append((i, "spread", "nocover", line, team))
        return sides or None

    core = s.split(":", 1)[1].strip() if ":" in s else s

    if "both teams" in core or "btts" in g:
        sides = []
        for i, o in enumerate(outcomes):
            ol = str(o).lower()
            if ol in ("yes", "btts-yes"):
                sides.append((i, "btts", "yes", None, None))
            elif ol in ("no", "btts-no"):
                sides.append((i, "btts", "no", None, None))
        return sides or None

    if re.search(r"\bo/u\b|over/under", core) or ("over" in core and "under" in core) \
            or "score over" in core or "score under" in core:
        line = find_line(core)
        if line is None:
            return None
        pre = re.split(r"\bo/u\b|over/under|\bover\b|\bunder\b", core)[0].strip()
        team = team_side_of(pre)
        sides = []
        for i, o in enumerate(outcomes):
            ol = str(o).lower()
            if ol == "over" or (ol == "yes" and re.search(r"\bover\b", core)):
                sides.append((i, "team_total" if team else "total", "over", line, team))
            elif ol == "under" or (ol == "yes" and re.search(r"\bunder\b", core)):
                sides.append((i, "team_total" if team else "total", "under", line, team))
            elif ol == "no" and re.search(r"\bover\b", core):
                sides.append((i, "team_total" if team else "total", "under", line, team))
            elif ol == "no" and re.search(r"\bunder\b", core):
                sides.append((i, "team_total" if team else "total", "over", line, team))
        return sides or None

    if "draw" in core and "win" not in core:
        sides = []
        for i, o in enumerate(outcomes):
            ol = str(o).lower()
            if ol in ("yes", "draw"):
                sides.append((i, "ml", "draw", None, None))
            elif ol == "no":
                sides.append((i, "ml", "draw_no", None, None))
        return sides or None

    if re.search(r"win on|win \(", core) or ("match winner" in g):
        head = re.split(r"\bwin\b", core)[0].replace("will ", "").strip()
        team = team_side_of(head)
        if team is None:
            return None
        sides = []
        for i, o in enumerate(outcomes):
            ol = str(o).lower()
            if ol == "yes":
                sides.append((i, "ml", team, None, None))
            elif ol == "no":
                sides.append((i, "ml", team + "_no", None, None))
        return sides or None

    return None


BOOK_CACHE = {}


def fetch_book(m, token_idx):
    toks = m.get("tokens") or []
    if token_idx >= len(toks):
        return None
    tok = toks[token_idx]
    if tok in BOOK_CACHE:
        return BOOK_CACHE[tok]
    try:
        b = get(CLOB + "/book?token_id=" + tok)
        if b is None:
            BOOK_CACHE[tok] = None
            return None
        asks = [(float(l["price"]), float(l["size"])) for l in b.get("asks", [])]
        bids = [(float(l["price"]), float(l["size"])) for l in b.get("bids", [])]
        book = {"asks": asks, "bids": bids,
                "best_ask": min((p for p, _ in asks), default=None),
                "best_bid": max((p for p, _ in bids), default=None)}
    except Exception as e:
        print("book err", m.get("id"), repr(e), flush=True)
        book = None
    BOOK_CACHE[tok] = book
    time.sleep(0.2)
    return book


def model_quote(o, kind, side_id, line, team_side):
    if kind == "total":
        p = soccer_model.over_probability(o, line)
        return p if side_id == "over" else 1.0 - p
    if kind == "btts":
        return o.btts if side_id == "yes" else 1.0 - o.btts
    if kind == "team_total":
        p = soccer_model.team_total_over(o, team_side, line)
        return p if side_id == "over" else 1.0 - p
    if kind == "ml":
        if side_id == "home_no":
            return 1.0 - o.home_win
        if side_id == "away_no":
            return 1.0 - o.away_win
        if side_id == "draw_no":
            return 1.0 - o.draw
        return {"home": o.home_win, "away": o.away_win, "draw": o.draw}[side_id]
    if kind == "spread":
        p = soccer_model.cover_probability(o, team_side, line)
        return p if side_id == "cover" else 1.0 - p
    return None


def league_policy(kind, league, cross):
    """Dispatch-frozen league policy for round 43A."""
    if kind == "spread":
        return ("FLAGGED_ONLY", False,
                "spreads flagged-only (blowout-tail rule): counted, never entered")
    if kind == "ml":
        if league in TOTALS_ONLY:
            return ("INELIGIBLE", False,
                    "TOTALS-FAMILY-ONLY league (gate-E fail / first-run "
                    "caveat): no 1X2 entries in Championship or Eredivisie")
        if cross:
            return ("ELIGIBLE-DEPRIORITIZED", True,
                    "cross-league match_winner: requires bridge + worst>=+5c "
                    "via gates.check_cross_league_mw; sized $150 via "
                    "risk_policy CROSS_LEAGUE_ML_CLASS")
        return ("ELIGIBLE-DEPRIORITIZED", True,
                "domestic match_winner eligible-deprioritized ($150)")
    return ("ELIGIBLE", True, "allowed kind under frozen gates")


def fetch_held_marks():
    out = {}
    for key, mid in HELD_IDS.items():
        try:
            m = get(BASE + "/markets/%d" % mid)
        except Exception as e:
            out[key] = {"error": repr(e)}
            continue
        if not isinstance(m, dict):
            out[key] = {"error": "fetch failed"}
            continue
        rec = {"id": mid, "question": m.get("question"),
               "outcomes": m.get("outcomes"),
               "outcomePrices": m.get("outcomePrices"),
               "closed": m.get("closed"), "active": m.get("active"),
               "umaResolutionStatus": m.get("umaResolutionStatus"),
               "liquidityNum": m.get("liquidityNum"),
               "volumeNum": m.get("volumeNum"),
               "fetched_utc": datetime.now(timezone.utc).strftime(
                   "%Y-%m-%dT%H:%M:%SZ")}
        toks = json.loads(m.get("clobTokenIds") or "[]")
        for i, t in enumerate(toks[:2]):
            try:
                b = get(CLOB + "/book?token_id=" + t)
                if b is None:
                    continue
                bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids") or []]
                asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks") or []]
                rec.setdefault("books", []).append({
                    "token_idx": i,
                    "best_bid": max((p for p, _ in bids), default=None),
                    "best_ask": min((p for p, _ in asks), default=None),
                    "bid_depth_shares": round(sum(s for _, s in bids), 1),
                    "ask_depth_shares": round(sum(s for _, s in asks), 1)})
            except Exception as e:
                rec.setdefault("books", []).append({"token_idx": i, "error": repr(e)})
            time.sleep(0.3)
        out[key] = rec
        print("HELD", key, "closed=", rec.get("closed"),
              "prices=", rec.get("outcomePrices"),
              "books=", rec.get("books"), flush=True)
        time.sleep(0.3)
    return out


def r41_kill_recheck():
    """Fresh books for the 3 R41 news-killed passers; ask move >=3c in our
    favor is the price leg of the revive test (news leg done outside)."""
    out = {}
    for mid_s, base in R41_KILLS.items():
        mid = int(mid_s)
        m = get(BASE + "/markets/%d" % mid)
        if not isinstance(m, dict):
            out[mid_s] = {"error": "gamma fetch failed", **base}
            continue
        rec = {**base, "id": mid_s, "question": m.get("question"),
               "closed": m.get("closed"), "active": m.get("active"),
               "outcomePrices": m.get("outcomePrices"),
               "fetched_utc": datetime.now(timezone.utc).strftime(
                   "%Y-%m-%dT%H:%M:%SZ")}
        toks = json.loads(m.get("clobTokenIds") or "[]")
        books = []
        for i, t in enumerate(toks[:2]):
            b = get(CLOB + "/book?token_id=" + t)
            time.sleep(0.25)
            if b is None:
                continue
            bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids") or []]
            asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks") or []]
            books.append({"token_idx": i,
                          "best_bid": max((p for p, _ in bids), default=None),
                          "best_ask": min((p for p, _ in asks), default=None),
                          "ask_depth_shares": round(sum(s for _, s in asks), 1)})
        rec["books"] = books
        # our side token: away=1 (home/away out), btts yes=0, TT over=0
        idx = {"away": 1, "yes": 0, "over": 0}.get(base["our_side"], 0)
        bk = next((b for b in books if b["token_idx"] == idx), None)
        if bk and bk.get("best_ask") is not None:
            move = round(base["r41_ask"] - bk["best_ask"], 4)  # + = cheaper = favorable
            rec["fresh_ask_our_side"] = bk["best_ask"]
            rec["ask_move_favorable_c"] = round(100 * move, 1)
            rec["price_leg_revive_ok"] = bool(move >= 0.03)
        else:
            rec["fresh_ask_our_side"] = None
            rec["price_leg_revive_ok"] = False
        out[mid_s] = rec
        print("R41KILL", mid_s, base["label"], "fresh_ask=",
              rec.get("fresh_ask_our_side"), "move_c=",
              rec.get("ask_move_favorable_c"), "price_leg=",
              rec["price_leg_revive_ok"], flush=True)
    return out


def espn_match(kick, league, base, espn_rows):
    def team_overlap(r):
        for espn_name in (r["home"], r["away"]):
            if not espn_name:
                continue
            en = norm_name(espn_name)
            if en and en in norm_name(base):
                return True
        return False

    best_dt, best, best_agree = None, None, False
    for r in espn_rows:
        if not (r["kick"] and kick):
            continue
        if r["espn_league"] != league:
            continue
        try:
            dt = abs((datetime.fromisoformat(r["kick"].replace("Z", "+00:00"))
                      - datetime.fromisoformat(kick.replace("Z", "+00:00"))
                      ).total_seconds())
        except Exception:
            continue
        if dt > 3 * 3600:
            continue
        agree = team_overlap(r)
        if (best is None or (agree and not best_agree)
                or (agree == best_agree and dt < best_dt)):
            best_dt, best, best_agree = dt, r, agree
    if best is not None:
        return {**best, "teams_agree": best_agree}
    return None


def dispatch_crosscheck(fixtures):
    """Match the dispatch kickoff list against the Gamma-derived fixtures."""
    rows = []
    for lg, label, kick in DISPATCH_SLATE:
        want = set(norm_name(t) for t in label.split() if norm_name(t))
        hit = None
        for f in fixtures:
            try:
                dt = abs((datetime.fromisoformat(f["kickoff_utc"].replace("Z", "+00:00"))
                          - datetime.fromisoformat(kick.replace("Z", "+00:00"))
                          ).total_seconds())
            except Exception:
                continue
            if dt > 3 * 3600 or f["league"] != lg:
                continue
            got = set(norm_name(t) for t in re.split(r"\s+vs\.?\s+",
                                                     f["match"]) if norm_name(t))
            if want & got:
                hit = f
                break
        rows.append({
            "league": lg, "fixture": label, "kickoff_utc": kick,
            "found_on_gamma": bool(hit),
            "gamma_match": (hit["match"] if hit else None),
            "n_markets": (hit["n_markets"] if hit else 0),
            "held_fixture": (hit["held_fixture"] if hit else False),
            "post_kickoff_at_scan": (hit["post_kickoff_at_scan"] if hit else None),
            "espn_cross": ((hit or {}).get("espn_cross") or {}).get("teams_agree")
            if hit else None})
    return rows


def board_only_rows_for(grp, post_kick):
    """Prices-only rows for board-only leagues; CLOB best bid/ask for the
    top-6 liquidity markets when pre-kick."""
    rows, seen_mkt = [], set()
    markets = []
    for e in grp:
        for m in e["markets"]:
            if m["id"] in seen_mkt:
                continue
            seen_mkt.add(m["id"])
            markets.append(m)
    markets.sort(key=lambda m: -(float(m.get("liq") or 0)))
    top_ids = {m["id"] for m in markets[:6]}
    for m in markets:
        pr = m.get("prices") or []
        rec = {"id": m["id"], "q": m["q"], "group": m.get("group"),
               "outcomes": m.get("outcomes"),
               "gamma_prices": pr, "liq_gamma": m.get("liq"),
               "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk")}
        if (not post_kick) and m["id"] in top_ids:
            toks = m.get("tokens") or []
            for i in range(min(2, len(toks))):
                book = fetch_book(m, i)
                if book:
                    rec.setdefault("clob", []).append({
                        "token_idx": i,
                        "best_bid": book["best_bid"],
                        "best_ask": book["best_ask"]})
        rows.append(rec)
    return rows


def main():
    print("UTC scan start:", NOW_S, flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    # ---- snapshots via validated loaders (template Block 2) ----
    with open(UNDERSTAT_POINTER, "r", encoding="utf-8") as _ph:
        understat_pointer = json.load(_ph)
    print("understat pointer ->", understat_pointer.get("target"),
          "pointed_at", understat_pointer.get("pointed_at_utc"), flush=True)
    snapshot = dict(xg.load_xg_snapshot(UNDERSTAT_LATEST))
    for k, v in fotmob.load_fotmob_snapshot(FOTMOB_CHAMP).items():
        snapshot[k] = v
    for k, v in fotmob.load_fotmob_snapshot(ERED).items():
        snapshot[k] = v
    print("snapshot blocks:", sorted(snapshot.keys()), flush=True)
    for lg in BIG5:
        for t in (snapshot.get(f"{lg}_2026") or {}).get("teams", {}).values():
            if t.get("title"):
                ALL_TITLES[t["title"]] = lg
                TITLE_LEAGUE[t["title"]] = lg
    for lgkey, lg in (("Championship_2026", "Championship"),
                      ("Eredivisie_2026", "Eredivisie")):
        for t in (snapshot.get(lgkey) or {}).get("teams", {}).values():
            if t.get("title"):
                ALL_TITLES[t["title"]] = lg
                TITLE_LEAGUE[t["title"]] = lg
    print("registry titles:", len(TITLE_LEAGUE), flush=True)
    STALENESS.update(build_staleness(snapshot))
    STALE_CLUBS.update(STALENESS)
    print("runtime staleness flags:", len(STALENESS),
          sorted(STALENESS)[:10], flush=True)

    # ---- bridge ----
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)
    print("bridge loaded:", {k: round(v, 4) for k, v in kappa.items()}, flush=True)

    # ---- events ----
    events = json.load(open(EVENTS))
    print("events loaded:", len(events), flush=True)

    # ---- espn rows ----
    espn_rows = []
    espn_raw = json.load(open(ESPN))
    for date, day in espn_raw.items():
        for label, evs in day.items():
            for ev in (evs if isinstance(evs, list) else []):
                espn_rows.append({
                    "espn_league": label,
                    "home": (ev.get("teams") or {}).get("home", {}).get("name"),
                    "away": (ev.get("teams") or {}).get("away", {}).get("name"),
                    "kick": ev.get("date") or "",
                    "status": ev.get("status")})
    espn_rows.sort(key=lambda r: r["kick"])
    print("espn rows:", len(espn_rows), flush=True)

    # ---- classify + group ----
    groups = {}
    for e in events:
        lg = None
        for t in e.get("tags") or []:
            if t in LEAGUE_TAGS:
                lg = LEAGUE_TAGS[t]
                break
        if lg is None:
            continue
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        groups.setdefault((e["kick"], base, lg), []).append(e)
    print("league fixtures:", len(groups), flush=True)

    fixtures, matches, board, board_only_rows, unparsed_qs = [], [], [], [], []
    held_marks = fetch_held_marks()
    recheck = r41_kill_recheck()

    for key in sorted(groups, key=lambda k: (k[0], k[1])):
        kick, base, lg = key
        grp = groups[key]
        parts = re.split(r"\s+vs\.?\s+", base, maxsplit=1)
        home_raw = parts[0].strip() if parts else ""
        away_raw = parts[1].strip() if len(parts) > 1 else ""
        home = canon_team(home_raw)
        away = canon_team(away_raw)
        lgh = TITLE_LEAGUE.get(home) if home else None
        lga = TITLE_LEAGUE.get(away) if away else None
        if home and away and lgh and lga and lgh != lga:
            cross = True
        else:
            cross = False
        kick_dt = datetime.fromisoformat(kick.replace("Z", "+00:00"))
        post_kick = kick_dt <= NOW
        hours_to_kick = (kick_dt - NOW).total_seconds() / 3600.0
        raw_norms = {norm_name(x) for x in (home_raw, away_raw) if x}
        resolved = {x for x in (home, away) if x}
        held_here = any(
            ({norm_name(h), norm_name(a)} <= raw_norms)
            or ({h, a} <= resolved)
            for h, a in HELD_PAIRS)
        er = espn_match(kick, lg, base, espn_rows)

        fxrec = {
            "match": base, "league": lg, "kickoff_utc": kick,
            "post_kickoff_at_scan": post_kick,
            "hours_to_kick_at_scan": round(hours_to_kick, 2),
            "in_entry_window": (not post_kick) and kick <= HI,
            "held_fixture": held_here,
            "espn_cross": ({"league": er["espn_league"], "home": er["home"],
                            "away": er["away"], "kick": er["kick"],
                            "status": er["status"],
                            "teams_agree": er.get("teams_agree")} if er else None),
            "gamma_event_ids": sorted({e["id"] for e in grp}),
            "n_markets": sum(len(e["markets"]) for e in grp),
            "understat_home": home, "understat_away": away,
            "home_league": lgh, "away_league": lga,
            "cross_league_pair": cross,
            "coverage": ("modeled" if (home and away) else
                         "board-only (no model coverage)" if lg in BOARD_ONLY
                         else "model-void (club not in snapshot universe)"),
        }
        fixtures.append(fxrec)

        if lg in BOARD_ONLY:
            prow = board_only_rows_for(grp, post_kick)
            board_only_rows.append({
                "match": base, "league": lg, "kickoff_utc": kick,
                "post_kickoff_at_scan": post_kick,
                "policy": "BOARD-ONLY: prices reported, NO MODEL COVERAGE, no entry",
                "rows": prow})
            print("BOARD-ONLY %-44s %-20s kick=%s rows=%d" % (
                base, lg, kick, len(prow)), flush=True)
            continue

        if not (home and away):
            fxrec["coverage"] = "model-void (club not in snapshot universe)"
            print("MODEL-VOID %-44s (%s / %s)" % (base, home, away), flush=True)
            continue

        # ---- model ----
        if cross:
            variants = soccer_model.fixture_variants(
                snapshot, home, lgh, away, lga, bridge=kappa)
            method = "bridged 10-variant library path (kappa bridge)"
        else:
            variants = soccer_model.fixture_variants(
                snapshot, home, lgh, away, lga)
            method = ("library fixture_variants 10 sweeps, domestic %s" % lgh)
        if variants is None:
            fxrec["coverage"] = "model-void (variants None: missing blocks/teams)"
            print("MODEL-VOID %s: variants None" % base, flush=True)
            continue
        vs = [{"lambdas": (v.lambdas[0], v.lambdas[1]), "outputs": v.outputs,
               "spec": v.spec.name} for v in variants]
        lam_h = soccer_model.median([v["lambdas"][0] for v in vs])
        lam_a = soccer_model.median([v["lambdas"][1] for v in vs])
        p1x2 = {
            "H": soccer_model.median([v["outputs"].home_win for v in vs]),
            "D": soccer_model.median([v["outputs"].draw for v in vs]),
            "A": soccer_model.median([v["outputs"].away_win for v in vs]),
        }
        form_h = xg.recent_form(snapshot, home) if lgh in BIG5 else None
        form_a = xg.recent_form(snapshot, away) if lga in BIG5 else None
        stale_here = sorted({s for s in (home, away) if s in STALE_CLUBS})
        matches.append({
            "match": base, "league": lg, "cross_league": cross,
            "kickoff_utc": kick, "post_kickoff_at_scan": post_kick,
            "held_fixture": held_here,
            "home_league": lgh, "away_league": lga,
            "gamma_event_ids": sorted({e["id"] for e in grp}),
            "lambda_home": round(lam_h, 3), "lambda_away": round(lam_a, 3),
            "lambda_total": round(lam_h + lam_a, 3),
            "p1x2_med": {k: round(v, 4) for k, v in p1x2.items()},
            "stale_clubs": stale_here,
            "staleness": {s: STALENESS[s] for s in stale_here},
            "method": method,
            "bridge_factor": (round(league_strength.bridge_factor(kappa, lgh, lga), 4)
                              if cross else None),
        })
        o25_combined = ((form_h.over_2_5_hits if form_h else 0)
                        + (form_a.over_2_5_hits if form_a else 0))
        seen_mkt = set()
        rows_n = 0
        for e in grp:
            for m in e["markets"]:
                if m["id"] in seen_mkt:
                    continue
                seen_mkt.add(m["id"])
                side_specs = parse_market_sides(m, home, away)
                if side_specs is None:
                    if m.get("q"):
                        unparsed_qs.append(m["q"])
                    continue
                for token_idx, kind, side_id, line, team_side in side_specs:
                    qs = []
                    for v in vs:
                        qv = model_quote(v["outputs"], kind, side_id, line, team_side)
                        if qv is None:
                            qs = None
                            break
                        qs.append(qv)
                    if not qs:
                        continue
                    liq = float(m.get("liq") or 0)
                    p_med = soccer_model.median(qs)
                    gamma_ask = None
                    try:
                        pr = m.get("prices") or []
                        if token_idx < len(pr):
                            gamma_ask = float(pr[token_idx])
                    except Exception:
                        gamma_ask = None

                    if post_kick or held_here or (not fxrec["in_entry_window"]):
                        # report-only row: no CLOB walk, no gate evaluation
                        board.append({
                            "match": base, "league": lg, "kind": kind,
                            "side": side_id, "line": line, "id": m["id"],
                            "q": m["q"], "report_only": True,
                            "report_reason": (
                                "HELD-FIXTURE (marks only, no new positions)"
                                if held_here else
                                "POST-KICKOFF at scan (board historical)"
                                if post_kick else "outside entry window"),
                            "p_med": round(p_med, 4),
                            "p_min": round(min(qs), 4), "p_max": round(max(qs), 4),
                            "var_spread": round(max(qs) - min(qs), 4),
                            "gamma_price": gamma_ask,
                            "liq_gamma": liq,
                            "stale_clubs": stale_here,
                        })
                        rows_n += 1
                        continue

                    book = fetch_book(m, token_idx)
                    if book is None:
                        continue
                    ur, ur_reason = gates.under_risk_check(
                        kind=kind,
                        side=side_id.split("_no")[0] if side_id.endswith("_no") else side_id,
                        o25_hits=o25_combined, lambda_total=lam_h + lam_a,
                        lambda_home=lam_h, lambda_away=lam_a,
                        line=line if line else 2.5)
                    quote = {"model_median": p_med, "qs_variants": tuple(qs)}
                    report = gates.evaluate_candidate(
                        quote, book["asks"], gamma_liquidity=liq, under_risk=ur,
                        fee_rate=gates.FEE_RATE_SPORTS)
                    pol, pol_eligible, pol_reason = league_policy(kind, lg, cross)
                    lib_pol = gates.suspension_policy(kind, cross_league=cross)
                    exit_walk = gates.walk_book(
                        [(p, s) for p, s in book["bids"]], side="bid")
                    row = {
                        "match": base, "league": lg, "cross_league": cross,
                        "kickoff_utc": kick,
                        "hours_to_kick_at_scan": round(hours_to_kick, 2),
                        "q": m["q"], "kind": kind, "side": side_id,
                        "line": line, "team_side": team_side, "id": m["id"],
                        "policy": pol, "policy_eligible": pol_eligible,
                        "policy_reason": pol_reason,
                        "library_policy": lib_pol.policy,
                        "library_policy_reason": lib_pol.reason,
                        "p_med": round(p_med, 4),
                        "p_min": round(min(qs), 4), "p_max": round(max(qs), 4),
                        "n_variants": len(qs),
                        "var_spread": report.variant_spread,
                        "book_best_bid": book["best_bid"],
                        "book_best_ask": book["best_ask"],
                        "liq_gamma": liq,
                        "exec_ask_vwap250": report.walk.vwap,
                        "fill_250": report.walk.filled,
                        "depth_2c": report.walk.depth_near2c,
                        "exit_bid": book["best_bid"],
                        "exit_bid_vwap250": exit_walk.vwap,
                        "exit_bid_depth_2c": exit_walk.depth_near2c,
                        "edge_vs_ask": (round(p_med - book["best_ask"], 4)
                                        if book["best_ask"] is not None else None),
                        "exec_edge_gross": report.exec_edge_gross,
                        "fee_per_share": (round(gates.fee_cost(
                            report.walk.vwap, gates.FEE_RATE_SPORTS), 4)
                            if report.walk.vwap is not None else None),
                        "exec_edge": report.exec_edge,
                        "worst_variant_edge": report.worst_variant_edge,
                        "haircut": report.haircut,
                        "exec_edge_haircut": report.exec_edge_haircut,
                        "under_risk": ur, "under_risk_reason": ur_reason,
                        "stale_clubs": stale_here,
                        "checks": {k: bool(v) for k, v in report.checks.items()},
                        "passed_numeric": all(
                            v for k, v in report.checks.items()
                            if k != "news_concordant"),
                    }
                    # cross-league MW enforcement (DELIVERY_PLAN section 72)
                    if cross and kind == "ml":
                        wve = report.worst_variant_edge
                        if wve is None or not (wve == wve) or abs(wve) == float("inf"):
                            row["cross_league_mw_check"] = {
                                "error": "non-finite worst_variant_edge"}
                            row["passed_numeric"] = False
                        else:
                            dec = gates.check_cross_league_mw(
                                "ml", worst_variant_edge=wve,
                                cross_league=True, bridge_present=True)
                            tier = risk_policy.sizing_tier(
                                market_class=risk_policy.CROSS_LEAGUE_ML_CLASS)
                            row["cross_league_mw_check"] = {
                                "passed": dec.passed, "failed": list(dec.failed),
                                "worst_variant_edge": round(wve, 4),
                                "sizing_class": risk_policy.CROSS_LEAGUE_ML_CLASS,
                                "sizing_tier": tier.tier,
                                "sizing_notional": tier.max_notional,
                                "sizing_reason": tier.reason}
                            if not dec.passed:
                                row["passed_numeric"] = False
                    flags = []
                    stake = 250
                    if kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if kind == "ml":
                        stake = 150
                        flags.append("MW eligible-deprioritized; $150")
                    if lg in TOTALS_ONLY and kind != "ml" and kind != "spread":
                        flags.append("TOTALS-FAMILY league (allowed kinds only)")
                    if stale_here:
                        flags.append("STALE-XG: %s (%s)" % (
                            ", ".join(stale_here),
                            "; ".join(STALENESS[c]["detail"]
                                      for c in stale_here if c in STALENESS)))
                    if held_here:
                        flags.append("HELD-FIXTURE (no new positions)")
                    if row["passed_numeric"] and pol_eligible:
                        flags.append("NUMERIC-PASS (pending news-concordance)")
                    if hours_to_kick < 2.0:
                        flags.append(
                            "T-%.1fh: kicks <2h from scan -> REQUIRES lineup "
                            "confirmation in news check or dies" % hours_to_kick)
                    elif hours_to_kick <= 10.0:
                        flags.append(
                            "T-%.1fh: T-2h recheck condition before entry"
                            % hours_to_kick)
                    if str(m["id"]) in R41_KILLS:
                        flags.append("R41-NEWS-KILL-RECHECK (revive needs "
                                     ">=3c favorable ask move AND news flip)")
                    row["stake_usd"] = stake
                    row["entry_flags"] = flags
                    row["enterable"] = bool(
                        row["passed_numeric"] and pol_eligible and not any(
                            f.startswith(("BANNED", "SPREADS", "HELD"))
                            for f in flags))
                    board.append(row)
                    rows_n += 1
        print("MODELED %-44s %-12s kick=%s cross=%s rows=%d stale=%s" % (
            base, lg, kick, cross, rows_n, ",".join(stale_here) or "-"),
            flush=True)

    board.sort(key=lambda r: (-(r["exec_edge_haircut"] if r.get("exec_edge_haircut")
                                is not None else -9), r.get("match", "")))
    out = {
        "scan": "soccer-euro-day-window", "round": 43, "sub_scan": "euro_day_43A",
        "paper_only": True,
        "generated_utc": NOW_S,
        "window_utc": {"lo": LO, "hi": HI},
        "dispatch_note": (
            "ROUND-43A Europe Sunday DAY window scan (05:30Z-17:59Z Nov-8); "
            "scan executed with early slate post-kickoff (board historical) "
            "and afternoon slate T-0.3h..T-4.3h; held #67 Le Mans-Monaco / "
            "#68 Brest-Lyon O2.5 / #63 ManUtd-Villa marks fetched separately; "
            "R41 3 news-killed passers re-checked at fresh prices; untagged "
            "leagues are raw-board-only; PAPER ONLY, no DB writes, no orders"),
        "provenance": {
            "understat_pointer": understat_pointer,
            "championship_snapshot": {
                "path": FOTMOB_CHAMP, "fresh_through_utc": "2026-11-03",
                "note": ("Championship Sunday games checked via tag sweep; "
                         "snapshot wired for coverage if any exist")},
            "eredivisie_snapshot": {
                "path": ERED,
                "meta": json.load(open(ERED + ".meta.json")),
                "fresh_through_utc": ("2026-11-07 20:00Z (r41 refetch, 103 "
                                      "matches 2026/27; REUSED this round, "
                                      "not re-refreshed per dispatch)")},
            "library_commit": "1a2760bc",
            "selfcheck": "PASS 10/10 (re-run this session pre-scan "
                         "2026-11-08T13:40Z)",
            "big5_refresh": {
                "merged": "round41/raw/xg_fotmob_big5_merged.json",
                "detail": ("REUSED unchanged from r41 (pointer untouched): "
                           "round25 Understat through Oct-31 + FotMob Nov-"
                           "1..Nov-8 backfill; Sat Nov-7 Big-5 games MERGED; "
                           "zero staleness per r41 runtime check, re-verified "
                           "at runtime this scan")},
            "kappa": {k: round(v, 6) for k, v in kappa.items()},
        },
        "gates": dict(gates.GATES, notes=(
            "NET-EDGE BARS: exec>=+5c net of sports fee 0.05*p*(1-p) at walked "
            "price (8c net if under-risk); worst>=+4c gross; var<=6c; liq>=5k; "
            "fill_250; entry .10-.92; haircut on NET edge; news-concordance at "
            "candidate stage; scoreline-concordance r32; one position per "
            "fixture; spreads flagged-only; Championship/Eredivisie 1X2 "
            "INELIGIBLE (totals family only); cross-league MW via "
            "check_cross_league_mw + CROSS_LEAGUE_ML_CLASS $150")),
        "budget": {"max_new_entries_usd_this_agent": 200,
                   "note": ("ROUND-43A dispatch: this agent proposes <=$200 "
                            "total; coordinator arbitrates across 3 agents; "
                            "soccer pool $3,000 @ $1,700 headroom incl. "
                            "$1,100 UCL/UEL reserve (unchanged: r42 entered "
                            "nothing)")},
        "held_positions": held_marks,
        "r41_kill_recheck": recheck,
        "dispatch_slate_crosscheck": dispatch_crosscheck(fixtures),
        "fixtures": fixtures,
        "matches": matches,
        "board_only": board_only_rows,
        "board_rows": len(board), "board": board,
        "unparsed_questions": sorted(set(unparsed_qs)),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nboard rows:", len(board), "matches:", len(matches),
          "board-only fixtures:", len(board_only_rows), flush=True)
    print("saved", OUT, flush=True)

    pass_rows = [r for r in board if r.get("passed_numeric")
                 and r.get("policy_eligible") and not r.get("report_only")]
    print("\nNUMERIC PASSERS (eligible kinds, pre-kick, not held):", len(pass_rows))
    for r in pass_rows[:40]:
        print("  PASS %-42s %-12s %-10s %-9s line=%-4s net=+%5.1fc worst=+%5.1fc "
              "var=%5.2fc liq=$%7.0f ask=%s p_med=%.3f T-%.1fh %s" % (
                  r["match"][:42], r["league"], r["kind"], r["side"], r["line"],
                  100 * (r["exec_edge_haircut"] or 0),
                  100 * (r["worst_variant_edge"] or 0),
                  100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
                  r["exec_ask_vwap250"], r["p_med"], r["hours_to_kick_at_scan"],
                  ";".join(r["entry_flags"])[:100]))

    print("\nTOP-30 by haircut net edge (gated rows only):")
    gated = [r for r in board if not r.get("report_only")
             and r.get("exec_edge_haircut") is not None]
    for r in gated[:30]:
        print("  NET %+6.1fc (gross %+6.1fc fee %.2fc) worst %+6.1fc var %5.2fc "
              "| %-40s | %-12s %-10s %-9s | p_med %.3f ask %s liq $%.0f T-%.1fh" % (
                  100 * (r["exec_edge_haircut"] or -9),
                  100 * (r["exec_edge_gross"] if r["exec_edge_gross"] is not None else -9),
                  100 * (r["fee_per_share"] or 0),
                  100 * (r["worst_variant_edge"] if r["worst_variant_edge"] is not None else -9),
                  100 * (r["var_spread"] or 0), r["match"][:40], r["league"],
                  r["kind"], r["side"], r["p_med"], r["exec_ask_vwap250"],
                  r["liq_gamma"] or 0, r["hours_to_kick_at_scan"]))


if __name__ == "__main__":
    main()
