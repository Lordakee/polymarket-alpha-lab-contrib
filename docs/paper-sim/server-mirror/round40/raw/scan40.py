"""ROUND-40 scan (paper-only): 12h soccer window 2026-11-07T13:50Z..2026-11-08T01:50Z.

Coverage (dispatch):
  Big-5 (EPL, Bundesliga, La_liga, Serie_A, Ligue_1): FULL market families,
    match_winner eligible-deprioritized $150.
  Championship + Eredivisie: TOTALS FAMILY ONLY (O/U, BTTS, team totals);
    1X2 ineligible (gate-E fail / first-run caveat) per frozen model rules.
  Belgian/Turkish/Portuguese/Scottish: board-only, prices reported, no entry.
  Cross-league MW: wired through gates.check_cross_league_mw (bridge_present +
    worst>=+5c) and sized via risk_policy sizing_tier(CROSS_LEAGUE_ML_CLASS)
    per DELIVERY_PLAN section 72 (mandatory wiring; no cross pairs expected
    this window).

xG bases:
  Big-5: ~/paper-sim/understat_latest.json pointer -> round36 FotMob merge,
    fresh through Nov-2 (no Big-5 league games Nov 3-5 per r38 verification).
  Championship: round31/raw/xg_fotmob_championship.json through Nov-3;
    Nov-4 midweek round missing -> 6 clubs 1-game stale (Cardiff, West Ham,
    Wrexham, Middlesbrough, Bristol City, Wolves).
  Eredivisie: round39/raw/xg_fotmob_eredivisie.json through Nov-6 19:00Z
    (fresh; meta fetched_utc 2026-11-07T07:08:12Z).

Timing: scan executes mid-window (~15:45Z+). Fixtures kicking <= board time
are POST-KICKOFF: modeled 1X2 for the report table only, Gamma prices, no
CLOB walks, no gates, no entry. Held fixtures (#64 Mainz-Bayern kicked,
#65 Osasuna-Athletic 17:30Z, #66 Valencia-RealMadrid 20:00Z) are marks-only
(monitored, no new positions on those fixtures).

Frozen gates (library 1a2760bc, selfcheck re-run this session): net>=+5c
after sports fee 0.05, worst>=+4c, var<=6c, liq>=$5k, $250 walk fill,
entry .10-.92, 50-50 haircut on net edge, news concordance, scoreline
concordance (r32), one position per fixture, spreads flagged-only.
Entry timing: <2h to kickoff needs lineup confirmation in the news check;
2-10h out gets a T-2h recheck condition.
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
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
ERED = f"{HOME}/round39/raw/xg_fotmob_eredivisie.json"
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"
OUTDIR = f"{HOME}/round40/raw"
OUT = f"{OUTDIR}/scan.json"
EVENTS = f"{OUTDIR}/events_window_40.json"
ESPN = f"{OUTDIR}/espn_fixtures_40.json"
LO = "2026-11-07T13:50:00Z"
HI = "2026-11-08T01:50:00Z"
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
    "64_mainz_bayern_btts_yes": 6176123,
    "65_osasuna_tt_o05": 6180838,
    "66_valencia_rm_u35": 6180689,
}
HELD_PAIRS = [  # held fixtures: marks only, no new positions
    ("Mainz 05", "Bayern Munich"),
    ("Osasuna", "Athletic Club"),
    ("Valencia", "Real Madrid"),
]

STALENESS = {
    "Cardiff City": {"missing": 1, "detail": "Nov-4 H v West Ham not in snapshot (snapshot thru Nov-3)"},
    "West Ham United": {"missing": 1, "detail": "Nov-4 A at Cardiff not in snapshot"},
    "Wrexham": {"missing": 1, "detail": "Nov-4 H v Middlesbrough not in snapshot"},
    "Middlesbrough": {"missing": 1, "detail": "Nov-4 A at Wrexham not in snapshot"},
    "Bristol City": {"missing": 1, "detail": "Nov-4 H v Wolverhampton not in snapshot"},
    "Wolverhampton Wanderers": {"missing": 1, "detail": "Nov-4 A at Bristol City not in snapshot"},
}
STALE_CLUBS = set(STALENESS)

TEAM_ALIASES = {
    # --- EPL (r38 slate set) ---
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
    # --- Championship (r38 set) ---
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
    # --- La Liga ---
    "rc deportivo a coruna": "Deportivo La Coruna",
    "deportivo a coruna": "Deportivo La Coruna",
    "deportivo la coruna": "Deportivo La Coruna",
    "rcd espanyol de barcelona": "Espanyol", "espanyol": "Espanyol",
    "real madrid cf": "Real Madrid", "real madrid": "Real Madrid",
    "valencia cf": "Valencia", "athletic club": "Athletic Club",
    "athletic bilbao": "Athletic Club", "ca osasuna": "Osasuna", "osasuna": "Osasuna",
    # --- Serie A ---
    "as roma": "Roma", "roma": "Roma", "us lecce": "Lecce", "lecce": "Lecce",
    "cagliari calcio": "Cagliari", "frosinone calcio": "Frosinone",
    "torino fc": "Torino", "parma calcio 1913": "Parma Calcio 1913",
    "bologna fc 1909": "Bologna", "us sassuolo calcio": "Sassuolo",
    # --- Ligue 1 ---
    "paris saint-germain fc": "Paris Saint Germain",
    "paris saint germain": "Paris Saint Germain", "psg": "Paris Saint Germain",
    "es troyes ac": "Troyes", "troyes": "Troyes", "aj auxerre": "Auxerre",
    "paris fc": "Paris FC",
    # --- Eredivisie (r39 set) ---
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
    if not n or n in CANON_DENY_EXACT:
        return None
    raw_l = strip_accents(str(name).strip().lower())
    alias = (TEAM_ALIASES.get(str(name).strip().lower())
             or TEAM_ALIASES.get(raw_l) or TEAM_ALIASES.get(n))
    if alias is not None and alias in TITLE_LEAGUE:
        return alias
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
    """Dispatch-frozen league policy for round 40."""
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
        # league agreement check (cross-league if both modeled but different)
        if home and away and lgh and lga and lgh != lga:
            cross = True
        elif home and away and lgh and lga:
            cross = False
        else:
            cross = False
        kick_dt = datetime.fromisoformat(kick.replace("Z", "+00:00"))
        post_kick = kick_dt <= NOW
        hours_to_kick = (kick_dt - NOW).total_seconds() / 3600.0
        fkey = fixture_key(home_raw, away_raw)
        held_here = any(
            {norm_name(h), norm_name(a)} <=
            {norm_name(home_raw), norm_name(away_raw)}
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
                        oc = m.get("outcomes") or []
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
                        flags.append(
                            "STALE-XG: %s (Nov-4 midweek round missing; 1 league "
                            "game each)" % ", ".join(stale_here))
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
        "scan": "soccer-12h-window", "round": 40,
        "paper_only": True,
        "generated_utc": NOW_S,
        "window_utc": {"lo": LO, "hi": HI},
        "dispatch_note": (
            "ROUND-40 12h window scan; scan executed mid-window (~15:50Z), "
            "fixtures kicking <= scan time are post-kickoff (report-only "
            "boards); held #64/#65/#66 marks fetched separately; PAPER ONLY, "
            "no DB writes, no real orders"),
        "provenance": {
            "understat_pointer": understat_pointer,
            "championship_snapshot": {
                "path": FOTMOB_CHAMP, "fresh_through_utc": "2026-11-03",
                "nov4_round_missing": ("Cardiff-West Ham, Wrexham-Middlesbrough, "
                                       "Bristol City-Wolves NOT in snapshot -> 6 "
                                       "clubs 1-game stale")},
            "eredivisie_snapshot": {
                "path": ERED,
                "meta": json.load(open(ERED + ".meta.json")),
                "fresh_through_utc": "2026-11-06 19:00Z (100 matches 2026/27)"},
            "library_commit": "1a2760bc",
            "selfcheck": "PASS 10/10 (re-run this session pre-scan)",
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
        "budget": {"max_new_entries_usd": 600,
                   "soccer_pool_usd": 3000, "headroom_usd": 1700,
                   "ucl_uel_reserve_usd": 1100},
        "held_positions": held_marks,
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


if __name__ == "__main__":
    main()
