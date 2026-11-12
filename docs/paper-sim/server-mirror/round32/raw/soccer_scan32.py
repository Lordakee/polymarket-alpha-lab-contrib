"""Round-32 SOCCER scan: WEEKEND EARLY-ENTRY Big-5 domestic slate (paper-only).

Window (task brief): Nov 7-9 "Fri-Sun" label; actual server calendar has
Nov 4 = Wednesday, so the weekend slate is FRI Nov 6 .. SUN Nov 8 (ESPN
confirms zero Big-5 games Nov 9-10; international break follows).
48 fixtures: EPL R11 (10), Serie A R12 (10), La Liga J12 (10),
Bundesliga MD9 (9), Ligue 1 R12 (9). Early entry NOW: all kickoffs are
2.4-4.5 days out -> XIs unconfirmed -> lineup_confirmation=0 -> $150
tier (risk_policy.EARLY_ENTRY), max 4 candidates, weekend budget $1000.

Degraded mode (brief-sanctioned): Understat NOT recovered (cron 08:30Z
JSONDecodeError; r28 unpublished; FotMob gate-E VALIDATION-FAILED) ->
xG base = round25 snapshot, fresh through Sat Oct 31 (Nov 1-3 slate of
~30 matches missing from ratings).

Modeling: all 48 fixtures are DOMESTIC same-league pairs -> canonical
library fixture_variants 10-variant path (worst>=+4c). Any UCL/UEL
cross-league pair found in the discovery window (expected none; MD4 was
Nov 3-5, MD5 is Nov 25) -> WP-P2a bridge path with the fitted kappa
report (totals/BTTS/TT only, worst>=+5c double scrutiny, MW banned).

Library: polymarket_alpha_lab.papersim @ bb100f4f (WP-P2a bridge),
selfcheck 10/10 PASS re-run this session.
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import (  # noqa: E402
    gates, league_strength, risk_policy, soccer_model, xg)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
R28_SNAP = "/home/ubuntu/paper-sim/round28/raw/xg_understat_28.json"
R25 = "/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json"
CRON_STATUS = "/home/ubuntu/paper-sim/round28/raw/understat_recovery_status.json"
XG_PATH = R28_SNAP if os.path.exists(R28_SNAP) else R25
R28_PUBLISHED = os.path.exists(R28_SNAP)
KAPPA_REPORT = "/home/ubuntu/paper-sim/round31/raw/league_strength_kappa.json"
cron_state = json.load(open(CRON_STATUS)) if os.path.exists(CRON_STATUS) else None

OUT = "/home/ubuntu/paper-sim/round32/raw/soccer_scan.json"
BOARD_OUT = "/home/ubuntu/paper-sim/round32/raw/odds_board_32.json"
EVENTS_OUT = "/home/ubuntu/paper-sim/round32/raw/events_window_32.json"

# kickoff range for the weekend slate (all 48 games)
DISC_LO = "2026-11-06T00:00:00Z"
DISC_HI = "2026-11-09T00:00:00Z"
LO = "2026-11-04T08:30:00Z"   # entry-placement window: scan time
HI = "2026-11-06T18:00:00Z"   # .. before first kickoff (Fri 19:30Z)

BIG5 = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]

COMP_OF_TAG = {
    "ucl": "UCL", "champions-league": "UCL", "uefa-champions-league": "UCL",
    "europa-league": "UEL", "uel": "UEL", "uefa-europa-league": "UEL",
    "conference-league": "UECL", "uecl": "UECL",
    "epl": "EPL_DOM", "premier-league": "EPL_DOM",
    "la-liga": "LIGA_DOM", "laliga": "LIGA_DOM",
    "serie-a": "SERIEA_DOM", "sea": "SERIEA_DOM",
    "ligue-1": "LIGUE1_DOM", "bundesliga": "BUNDES_DOM",
    "championship": "ENG2", "efl-championship": "ENG2",
    "efl-cup": "EFL_CUP", "carabao-cup": "EFL_CUP", "carabao": "EFL_CUP",
    "mls": "MLS", "mls-playoffs": "MLS",
    "serie-a-brasil": "BRA", "brasileirao": "BRA",
    "liga-mx": "MEX", "primera-division-argentina": "ARG",
}
UCL_UEL_TAGS = {"ucl", "champions-league", "uefa-champions-league",
                "europa-league", "uel", "uefa-europa-league",
                "conference-league", "uecl"}
CUP_TAGS = {"efl-cup", "carabao-cup", "carabao", "copa-del-rey",
            "coupe-de-france", "dfb-pokal"}

TEAM_ALIASES = {
    "bayern munich": "Bayern Munich", "bayern": "Bayern Munich",
    "fc bayern munique": "Bayern Munich", "bayern munique": "Bayern Munich",
    "bayern munchen": "Bayern Munich", "fc bayern munchen": "Bayern Munich",
    "borussia monchengladbach": "Borussia M.Gladbach",
    "borussia mgladbach": "Borussia M.Gladbach",
    "borussia monchen gladbach": "Borussia M.Gladbach",
    "gladbach": "Borussia M.Gladbach",
    "atletico madrid": "Atletico Madrid", "atletico": "Atletico Madrid",
    "club atletico de madrid": "Atletico Madrid",
    "aston villa": "Aston Villa",
    "barcelona": "Barcelona", "fc barcelona": "Barcelona",
    "inter milan": "Inter", "internazionale": "Inter", "inter": "Inter",
    "fc internazionale milano": "Inter",
    "stuttgart": "VfB Stuttgart", "vfb stuttgart": "VfB Stuttgart",
    "lille": "Lille", "losc lille": "Lille", "losc": "Lille",
    "bayer leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "bayer 04 leverkusen": "Bayer Leverkusen",
    "rb leipzig": "RasenBallsport Leipzig", "leipzig": "RasenBallsport Leipzig",
    "rasenballsport leipzig": "RasenBallsport Leipzig",
    "manchester city": "Manchester City", "man city": "Manchester City",
    "manchester united": "Manchester United", "man united": "Manchester United",
    "psg": "Paris Saint Germain", "paris saint germain": "Paris Saint Germain",
    "paris sg": "Paris Saint Germain", "paris-saint-germain": "Paris Saint Germain",
    "paris saint-germain": "Paris Saint Germain",
    "ac milan": "AC Milan", "milan": "AC Milan",
    "real madrid": "Real Madrid", "real": "Real Madrid",
    "borussia dortmund": "Borussia Dortmund", "dortmund": "Borussia Dortmund",
    "as monaco": "Monaco", "monaco": "Monaco",
    "olympique lyonnais": "Lyon", "lyon": "Lyon", "ol lyon": "Lyon",
    "olympique de marseille": "Marseille", "olympique marseille": "Marseille",
    "marseille": "Marseille",
    "atalanta bc": "Atalanta", "atalanta": "Atalanta",
    "bologna": "Bologna", "fc bologna": "Bologna",
    "brentford": "Brentford", "brighton": "Brighton",
    "brighton hove albion": "Brighton", "brighton and hove albion": "Brighton",
    "brighton hove albion fc": "Brighton",
    "crystal palace": "Crystal Palace", "everton": "Everton", "fulham": "Fulham",
    "tottenham hotspur": "Tottenham", "tottenham": "Tottenham",
    "nottingham forest": "Nottingham Forest",
    "newcastle united": "Newcastle United", "newcastle": "Newcastle United",
    "villarreal": "Villarreal",
    "real betis": "Real Betis", "betis": "Real Betis",
    "real sociedad": "Real Sociedad", "sevilla": "Sevilla",
    "athletic bilbao": "Athletic Club", "athletic club": "Athletic Club",
    "athletic club de bilbao": "Athletic Club",
    "celta vigo": "Celta Vigo", "celta": "Celta Vigo",
    "eintracht frankfurt": "Eintracht Frankfurt",
    "parma calcio 1913": "Parma Calcio 1913", "parma": "Parma Calcio 1913",
    "us sassuolo calcio": "Sassuolo", "sassuolo": "Sassuolo",
    "acf fiorentina": "Fiorentina", "fiorentina": "Fiorentina",
    "rc deportivo a coruna": "Deportivo La Coruna",
    "deportivo la coruna": "Deportivo La Coruna",
    "deportivo": "Deportivo La Coruna",
    "stade brestois 29": "Brest", "stade brestois": "Brest",
    "paris fc": "Paris FC", "roma": "Roma", "as roma": "Roma",
    "como": "Como", "como 1907": "Como",
    "lens": "Lens", "racing club de lens": "Lens", "rc lens": "Lens",
    "hoffenheim": "Hoffenheim", "tsg hoffenheim": "Hoffenheim",
    "leeds united": "Leeds", "leeds": "Leeds",
    "coventry city": "Coventry", "coventry": "Coventry",
    "hull city": "Hull", "hull": "Hull",
    "ipswich town": "Ipswich", "ipswich": "Ipswich",
    "sunderland afc": "Sunderland", "sunderland": "Sunderland",
    "stade rennais": "Rennes", "rennes": "Rennes",
    "stade rennais fc": "Rennes",
    "hamburg sv": "Hamburger SV", "hamburger sv": "Hamburger SV",
    "hamburg": "Hamburger SV",
    "fc cologne": "FC Cologne", "cologne": "FC Cologne",
    "1 fc cologne": "FC Cologne", "fc koln": "FC Cologne",
    "sc paderborn 07": "Paderborn", "paderborn": "Paderborn",
    "sc paderborn": "Paderborn",
    "sv elversberg": "Elversberg", "elversberg": "Elversberg",
    "werder bremen": "Werder Bremen",
    "sv werder bremen": "Werder Bremen",
    "mainz": "Mainz 05", "mainz 05": "Mainz 05", "fsv mainz 05": "Mainz 05",
    "1 fsv mainz 05": "Mainz 05",
    "fc augsburg": "Augsburg", "augsburg": "Augsburg",
    "sc freiburg": "Freiburg", "freiburg": "Freiburg",
    "1 fc union berlin": "Union Berlin", "fc union berlin": "Union Berlin",
    "union berlin": "Union Berlin",
    "racing santander": "Racing Santander",
    "real racing club santander": "Racing Santander",
    "malaga": "Malaga", "cd malaga": "Malaga",
    "rayo vallecano": "Rayo Vallecano", "rayo": "Rayo Vallecano",
    "alaves": "Alaves", "deportivo alaves": "Alaves",
    "espanyol": "Espanyol", "rcd espanyol": "Espanyol",
    "getafe": "Getafe", "elche": "Elche", "elche cf": "Elche",
    "osasuna": "Osasuna", "ca osasuna": "Osasuna",
    "sevilla fc": "Sevilla",
    "valencia cf": "Valencia", "valencia": "Valencia",
    "aj auxerre": "Auxerre", "auxerre": "Auxerre",
    "le havre ac": "Le Havre", "le havre": "Le Havre",
    "le mans": "Le Mans", "le mans fc": "Le Mans",
    "estac troyes": "Troyes", "troyes": "Troyes", "es troyes ac": "Troyes",
    "lorient": "Lorient", "fc lorient": "Lorient",
    "rc strasbourg": "Strasbourg", "strasbourg": "Strasbourg",
    "rc strasbourg alsace": "Strasbourg",
    "toulouse": "Toulouse", "toulouse fc": "Toulouse",
    "ogc nice": "Nice", "nice": "Nice",
    "angers": "Angers", "angers sco": "Angers",
    "frosinone": "Frosinone", "frosinone calcio": "Frosinone",
    "venezia": "Venezia", "venezia fc": "Venezia",
    "cagliari": "Cagliari", "cagliari calcio": "Cagliari",
    "torino": "Torino", "torino fc": "Torino",
    "lecce": "Lecce", "us lecce": "Lecce",
    "genoa": "Genoa", "genoa cfc": "Genoa",
    "monza": "Monza", "ac monza": "Monza",
    "juventus": "Juventus", "juve": "Juventus",
    "ss lazio": "Lazio", "lazio": "Lazio",
    "ssc napoli": "Napoli", "napoli": "Napoli",
    "arsenal": "Arsenal", "chelsea": "Chelsea", "liverpool": "Liverpool",
    "west ham united": "West Ham", "west ham": "West Ham",
    "wolverhampton wanderers": "Wolves", "wolves": "Wolves",
    "afc bournemouth": "Bournemouth", "bournemouth": "Bournemouth",
    "bournemouth": "Bournemouth",
}


def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2.0 + 2 * i)
    raise last


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
    except Exception:  # noqa: BLE001
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
        "07", "04", "05"}]
    return " ".join(toks).strip()


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return []
    return raw or []


def sweep(order, extra_params, max_offset=1000):
    out = []
    offset = 0
    while True:
        params = {"limit": 100, "active": "true", "closed": "false",
                  "order": order, "ascending": "false", "offset": offset}
        params.update(extra_params)
        resp = get(BASE + "/events/pagination?" + urllib.parse.urlencode(params))
        batch = resp.get("data") if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100:
            return out
        offset += 100
        if offset >= max_offset:
            return out
        time.sleep(1.0)


def slim_event(e):
    eid = str(e.get("id"))
    tags = [t.get("slug") for t in (e.get("tags") or []) if t.get("slug")]
    slim = {"id": eid, "title": e.get("title"), "slug": e.get("slug"),
            "tags": tags, "liq": e.get("liquidityNum"),
            "vol24": e.get("volume24hr"), "markets": []}
    for m in e.get("markets") or []:
        if m.get("closed"):
            continue
        slim["markets"].append({
            "id": str(m.get("id")), "q": m.get("question"),
            "slug": m.get("slug"), "group": m.get("groupItemTitle"),
            "type": m.get("marketType"),
            "outcomes": parse_listy(m.get("outcomes")),
            "prices": parse_listy(m.get("outcomePrices")),
            "tokens": parse_listy(m.get("clobTokenIds")),
            "line": m.get("line") or m.get("handicap"),
            "gameStartTime": norm_ts(m.get("gameStartTime")),
            "liq": m.get("liquidityNum"), "vol24": m.get("volume24hr"),
            "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
            "spread": m.get("spread"), "active": m.get("active")})
    kos = [m["gameStartTime"] for m in slim["markets"] if m["gameStartTime"]]
    slim["kick"] = min(kos) if kos else ""
    return slim


def in_range(ev, lo, hi):
    kos = [m["gameStartTime"] for m in ev["markets"] if m["gameStartTime"]]
    return any(lo <= k <= hi for k in kos)


def fetch_window(lo, hi, sweeps):
    seen = {}
    for label, order, extra in sweeps:
        try:
            evs = sweep(order, extra)
        except Exception as e:  # noqa: BLE001
            print("sweep", label, "FAILED", repr(e), flush=True)
            continue
        n = 0
        for e in evs:
            try:
                slim = slim_event(e)
            except Exception:  # noqa: BLE001
                continue
            if not in_range(slim, lo, hi):
                sd = norm_ts(e.get("startDate"))
                if not (sd and lo <= sd <= hi and slim["markets"]):
                    continue
            n += 1
            eid = slim["id"]
            if eid not in seen:
                seen[eid] = slim
        print("sweep %-22s total=%4d in_window=%d unique=%d" % (
            label, len(evs), n, len(seen)), flush=True)
        time.sleep(1.0)
    return seen


ALL_TITLES = {}
TITLE_LEAGUE = {}


def canon_team(name):
    n = norm_name(name)
    if not n:
        return None
    alias = TEAM_ALIASES.get(str(name).strip().lower()) or TEAM_ALIASES.get(n)
    if alias is not None and alias in TITLE_LEAGUE:
        return alias
    for t in ALL_TITLES:
        if norm_name(t) == n:
            return t
    for t in ALL_TITLES:
        tn = norm_name(t)
        if tn and (tn in n or n in tn):
            return t
    return None


def comp_of(tags, home_lg, away_lg):
    tset = set(tags)
    for t in tset & UCL_UEL_TAGS:
        return COMP_OF_TAG[t]
    for t in tset & CUP_TAGS:
        return COMP_OF_TAG[t]
    if home_lg and away_lg and home_lg != away_lg:
        return "CROSS(other)"
    for t in tset:
        if t in COMP_OF_TAG:
            return COMP_OF_TAG[t]
    return "OTHER"


def fixture_key(home, away):
    return "-".join(sorted([norm_name(home).replace(" ", ""),
                            norm_name(away).replace(" ", "")]))


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
        asks = [(float(l["price"]), float(l["size"])) for l in b.get("asks", [])]
        bids = [(float(l["price"]), float(l["size"])) for l in b.get("bids", [])]
        book = {"asks": asks, "bids": bids,
                "best_ask": min((p for p, _ in asks), default=None),
                "best_bid": max((p for p, _ in bids), default=None)}
    except Exception as e:  # noqa: BLE001
        print("book err", m.get("id"), repr(e), flush=True)
        book = None
    BOOK_CACHE[tok] = book
    time.sleep(0.25)
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


def parse_market_sides(m, home, away):
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
            except Exception:  # noqa: BLE001
                return None
        return None

    def team_side_of(name):
        resolved = canon_team(name)
        if resolved == home:
            return "home"
        if resolved == away:
            return "away"
        n = norm_name(name)
        if not n:
            return None
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


def understat_probe():
    try:
        r = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{time_total}s",
             "--max-time", "12", "https://understat.com/league/EPL/2026"],
            capture_output=True, text=True, timeout=20)
        return {"ok": r.returncode == 0 and r.stdout[:3] == "200",
                "detail": (r.stdout or r.stderr).strip()[:120]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": repr(e)[:120]}


def section_of(kick):
    if kick < "2026-11-07T00:00:00Z":
        return "fri_nov6"
    if kick < "2026-11-08T00:00:00Z":
        return "sat_nov7"
    return "sun_nov8"


def main():
    now = datetime.now(timezone.utc)
    print("UTC now:", now.isoformat(), flush=True)
    probe = understat_probe()
    print("understat probe:", probe, flush=True)
    print("DEGRADED MODE: XG base =", XG_PATH,
          "| r28 cron snapshot published:", R28_PUBLISHED,
          "| cron status:", cron_state, flush=True)
    snapshot = xg.load_xg_snapshot(XG_PATH)
    for lg in BIG5:
        block = snapshot.get(f"{lg}_2026") or {}
        for t in (block.get("teams") or {}).values():
            title = t.get("title")
            if title:
                ALL_TITLES[title] = lg
                TITLE_LEAGUE[title] = lg
    print("Big-5 titles loaded:", len(ALL_TITLES), flush=True)

    bridge = None
    if os.path.exists(KAPPA_REPORT):
        table = league_strength.load_kappa_report(KAPPA_REPORT)
        bridge = table.kappa
        print("kappa bridge loaded:", dict(bridge), flush=True)

    sweeps = [
        ("date-volume", "volume24hr", {"start_date_min": DISC_LO,
                                       "start_date_max": DISC_HI}),
        ("date-liquidity", "liquidity", {"start_date_min": DISC_LO,
                                         "start_date_max": DISC_HI}),
        ("tag-soccer", "volume24hr", {"tag_slug": "soccer"}),
        ("tag-ucl", "volume24hr", {"tag_slug": "ucl"}),
        ("tag-champions", "volume24hr", {"tag_slug": "champions-league"}),
        ("tag-uefa-cl", "volume24hr", {"tag_slug": "uefa-champions-league"}),
        ("tag-europa", "volume24hr", {"tag_slug": "europa-league"}),
        ("tag-uel", "volume24hr", {"tag_slug": "uel"}),
        ("tag-uecl", "volume24hr", {"tag_slug": "conference-league"}),
        ("tag-epl", "volume24hr", {"tag_slug": "epl"}),
        ("tag-laliga", "volume24hr", {"tag_slug": "laliga"}),
        ("tag-serie-a", "volume24hr", {"tag_slug": "serie-a"}),
        ("tag-ligue-1", "volume24hr", {"tag_slug": "ligue-1"}),
        ("tag-bundesliga", "volume24hr", {"tag_slug": "bundesliga"}),
    ]
    seen = fetch_window(DISC_LO, DISC_HI, sweeps)
    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(EVENTS_OUT, "w"), indent=1)
    print("unique soccer events in discovery range:", len(events), flush=True)

    fixtures = []
    for e in events:
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        home_raw = parts[0].strip() if parts else ""
        away_raw = parts[1].strip() if len(parts) > 1 else ""
        home = canon_team(home_raw)
        away = canon_team(away_raw)
        lgh = TITLE_LEAGUE.get(home) if home else None
        lga = TITLE_LEAGUE.get(away) if away else None
        comp = comp_of(e["tags"], lgh, lga)
        kick = e["kick"]
        fixtures.append({
            "event_id": e["id"], "title": e["title"], "kickoff_utc": kick,
            "comp": comp, "tags": e["tags"],
            "section": section_of(kick), "in_entry_window": True,
            "modelable": bool(home and away),
            "modelability_class": (
                "domestic-pair" if home and away and lgh == lga else
                "cross-league" if home and away else "no-data"),
            "same_league": bool(home and away and lgh == lga),
            "understat_home": home, "understat_away": away,
            "home_league": lgh, "away_league": lga,
            "liq_event": e.get("liq"), "vol24": e.get("vol24"),
            "n_markets": len(e["markets"]),
        })
    base_fixtures = {}
    for f in fixtures:
        base_fixtures.setdefault(f["kickoff_utc"] + "|" + re.split(
            r"\s+-\s+", f["title"], maxsplit=1)[0], f)
    uniq = sorted(base_fixtures.values(), key=lambda x: x["kickoff_utc"])
    print("\n%d unique fixtures:" % len(uniq), flush=True)
    for f in uniq:
        print("%-12s %-11s %-28s vs %-26s kick=%s class=%s" % (
            f["comp"], f["section"], str(f["understat_home"]),
            str(f["understat_away"]), f["kickoff_utc"],
            f["modelability_class"]), flush=True)

    matches, board, unparsed_qs, no_market = [], [], [], []
    groups = {}
    for fx, e in zip(fixtures, events):
        if not fx["modelable"]:
            continue
        key = (fx["understat_home"], fx["understat_away"], fx["kickoff_utc"],
               fx["comp"], fx["title"])
        groups.setdefault(key, {"fx": fx, "events": []})["events"].append(e)

    for key in sorted(groups, key=lambda k: groups[k]["fx"]["kickoff_utc"]):
        grp = groups[key]
        fx = grp["fx"]
        e0 = min(grp["events"], key=lambda e: len(e.get("title") or ""))
        base_title = re.split(r"\s+-\s+", e0.get("title") or "", maxsplit=1)[0]
        home, away = fx["understat_home"], fx["understat_away"]
        lgh, lga = fx["home_league"], fx["away_league"]
        cross = bool(lgh and lga and lgh != lga)
        n_mk = sum(len(e["markets"]) for e in grp["events"])
        if n_mk == 0:
            no_market.append({"match": base_title, "kick": fx["kickoff_utc"],
                              "note": "no open markets on gamma"})
            continue

        if cross:
            if bridge is None:
                fx["modelable"] = False
                fx["model_note"] = "cross-league without bridge table"
                continue
            variants = soccer_model.fixture_variants(
                snapshot, home, lgh, away, lga, bridge=bridge)
            method = ("WP-P2a BRIDGED cross-league path (10 sweeps x kappa "
                      "report, clamped 1.25x); MW/spread BANNED; "
                      "worst>=+5c double scrutiny")
        else:
            variants = soccer_model.fixture_variants(snapshot, home, lgh, away, lga)
            method = "library fixture_variants (10 sweeps, domestic)"
        if variants is None:
            fx["modelable"] = False
            fx["model_note"] = "variants returned None"
            continue
        vs = [{"lambdas": (v.lambdas[0], v.lambdas[1]),
               "outputs": v.outputs,
               "spec": getattr(v.spec, "name", "?")} for v in variants]
        lam_h = soccer_model.median([v["lambdas"][0] for v in vs])
        lam_a = soccer_model.median([v["lambdas"][1] for v in vs])
        p1x2 = {
            "H": soccer_model.median([v["outputs"].home_win for v in vs]),
            "D": soccer_model.median([v["outputs"].draw for v in vs]),
            "A": soccer_model.median([v["outputs"].away_win for v in vs]),
        }
        form_h = xg.recent_form(snapshot, home)
        form_a = xg.recent_form(snapshot, away)
        fkey = fixture_key(home, away)
        matches.append({
            "match": base_title, "comp": fx["comp"], "cross_league": cross,
            "bridged": cross,
            "section": fx["section"], "in_entry_window": True,
            "home_league": lgh, "away_league": lga,
            "fixture_key": fkey,
            "gamma_event_ids": sorted({e["id"] for e in grp["events"]}),
            "kickoff_utc": fx["kickoff_utc"],
            "lambda_home": round(lam_h, 3),
            "lambda_total": round(lam_h + lam_a, 3),
            "lambda_away": round(lam_a, 3),
            "p1x2_med_report_only": {k: round(v, 4) for k, v in p1x2.items()},
            "p1x2_note": ("REPORT-ONLY (MW banned cross-league)" if cross
                          else "eligible-but-deprioritized"),
            "form_home_last5": {"gp": form_h.games, "gf": form_h.goals_for,
                                "ga": form_h.goals_against,
                                "xg_for": round(form_h.xg_per_game * form_h.games, 2),
                                "o25_hits": form_h.over_2_5_hits,
                                "btts_hits": form_h.btts_hits} if form_h else None,
            "form_away_last5": {"gp": form_a.games, "gf": form_a.goals_for,
                                "ga": form_a.goals_against,
                                "xg_for": round(form_a.xg_per_game * form_a.games, 2),
                                "o25_hits": form_a.over_2_5_hits,
                                "btts_hits": form_a.btts_hits} if form_a else None,
            "method": method,
        })
        o25_combined = ((form_h.over_2_5_hits if form_h else 0)
                        + (form_a.over_2_5_hits if form_a else 0))
        seen_mkt = set()
        mk_count = {"ml": 0, "total": 0, "team_total": 0, "btts": 0, "spread": 0}
        for e in grp["events"]:
            for m in e["markets"]:
                if m["id"] in seen_mkt:
                    continue
                seen_mkt.add(m["id"])
                side_specs = parse_market_sides(m, home, away)
                if side_specs is None:
                    if m.get("q"):
                        unparsed_qs.append(m["q"])
                    continue
                mk_count[side_specs[0][1]] = mk_count.get(side_specs[0][1], 0) + 1
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
                    book = fetch_book(m, token_idx)
                    if book is None:
                        continue
                    liq = float(m.get("liq") or 0)
                    quote = {"model_median": soccer_model.median(qs),
                             "qs_variants": tuple(qs)}
                    ur, ur_reason = gates.under_risk_check(
                        kind=kind,
                        side=side_id.split("_no")[0] if side_id.endswith("_no") else side_id,
                        o25_hits=o25_combined,
                        lambda_total=lam_h + lam_a, lambda_home=lam_h,
                        lambda_away=lam_a, line=line if line else 2.5)
                    report = gates.evaluate_candidate(
                        quote, book["asks"], gamma_liquidity=liq, under_risk=ur)
                    pol = gates.suspension_policy(kind, cross_league=cross)
                    exit_walk = gates.walk_book(
                        [(p, s) for p, s in book["bids"]], side="bid")
                    row = {
                        "match": base_title, "comp": fx["comp"],
                        "cross_league": cross, "fixture_key": fkey,
                        "section": fx["section"], "in_entry_window": True,
                        "q": m["q"], "kind": kind, "side": side_id,
                        "line": line, "team_side": team_side,
                        "id": m["id"], "policy": pol.policy,
                        "p_med": round(quote["model_median"], 4),
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
                        "edge_vs_ask": (round(quote["model_median"] - book["best_ask"], 4)
                                        if book["best_ask"] is not None else None),
                        "exec_edge": report.exec_edge,
                        "worst_variant_edge": report.worst_variant_edge,
                        "haircut": report.haircut,
                        "exec_edge_haircut": report.exec_edge_haircut,
                        "under_risk": ur, "under_risk_reason": ur_reason,
                        "checks": {k: bool(v) for k, v in report.checks.items()},
                        "passed_numeric": all(
                            v for k, v in report.checks.items()
                            if k != "news_concordant"),
                    }
                    if cross and row["passed_numeric"]:
                        worst = report.worst_variant_edge
                        if worst is None or worst < 0.05 - 5e-4:
                            row["passed_numeric"] = False
                            row["cross_league_5c_worst"] = False
                        else:
                            row["cross_league_5c_worst"] = True
                    hours_to_kick = max(1, round((
                        datetime.fromisoformat(
                            fx["kickoff_utc"].replace("Z", "+00:00"))
                        - now).total_seconds() / 3600))
                    flags = ["EARLY-ENTRY: kickoff %dh after scan; XIs "
                             "unconfirmed -> $150 tier" % hours_to_kick]
                    if cross and kind in ("ml", "spread"):
                        flags.append("BANNED-CROSS-LEAGUE-MW/spread (FIXES 5-6)")
                    if not cross and kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if not cross and kind == "ml":
                        flags.append("MATCH-WINNER domestic: eligible-but-deprioritized")
                    if row["passed_numeric"] and not any(
                            f.startswith(("BANNED", "SPREADS")) for f in flags):
                        flags.append("NUMERIC-PASS (pending news-concordance)")
                    row["entry_flags"] = flags
                    row["enterable"] = bool(
                        row["passed_numeric"] and not any(
                            f.startswith(("BANNED", "SPREADS")) for f in flags))
                    board.append(row)
        print("fixture %s [%s cross=%s kick=%s]: markets %s rows=%d" % (
            base_title, fx["comp"], cross, fx["kickoff_utc"], mk_count,
            sum(1 for r in board if r["fixture_key"] == fkey)), flush=True)

    board.sort(key=lambda r: (-(r["exec_edge"] if r["exec_edge"] is not None else -9),
                              r["match"]))
    out = {
        "scan": "soccer", "round": 32,
        "sub_scan": ("WEEKEND EARLY-ENTRY Big-5 domestic slate; kickoff window "
                     "Fri Nov-6 19:30Z .. Sun Nov-8 20:00Z (48 fixtures; "
                     "brief label Nov 7-9 Fri-Sun vs server calendar Nov-4="
                     "Wednesday - actual slate is Fri Nov-6..Sun Nov-8, zero "
                     "games Nov 9-10)"),
        "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("entry-placement window (early entry, scan "
                                "time -> before first kickoff); all kickoffs "
                                "2.4-4.5 days out -> $150 early-entry tier")},
        "discovery_range_utc": {"lo": DISC_LO, "hi": DISC_HI},
        "degraded_mode": {
            "active": True,
            "reason": "Understat upstream not recovered",
            "xg_base": XG_PATH,
            "xg_base_fresh_through_utc": "2026-10-31",
            "staleness": ("Nov 1-3 slates missing (~30 matches: EPL R10 "
                          "remainder, Serie A/Bundesliga/Ligue 1 weekend, "
                          "UCL MD4 - ratings exclude them)"),
            "r28_cron_snapshot_published": R28_PUBLISHED,
            "cron_status_at_run": cron_state,
            "http_probe_at_run": probe,
            "fotmob_status": ("VALIDATION-FAILED gate E (round31) - not an "
                              "approved xG substitute"),
        },
        "method": ("Gamma date-window + tag discovery (domestic league tags + "
                   "ucl/uel/uecl tags to prove absence) -> soccer events; all "
                   "domestic Big-5 pairs via canonical fixture_variants (10 "
                   "variants, worst>=+4c); any cross-league pair via WP-P2a "
                   "bridge (kappa report, clamped 1.25x, worst>=+5c, MW/spread "
                   "banned); full odds board both token sides; CLOB $250 "
                   "ask-VWAP walk; frozen gates; early-entry $150 tier "
                   "(lineup_confirmation=0)"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "bb100f4f", "selfcheck": "10/10 PASS",
                    "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src"},
        "gates": dict(gates.GATES, notes=(
            "domestic: worst>=+4c; cross-league: MW banned, worst>=+5c; both: "
            "exec>=+5c after 50-50 haircut, var<=6c, liq>=5k, fill_250, entry "
            ".10-.92, under-risk 8c screen; news-concordance at candidate "
            "stage; spreads flagged-only; domestic MW eligible-deprioritized")),
        "sizing": {"tier": "EARLY_ENTRY", "lineup_confirmation": 0.0,
                   "notional_usd": risk_policy.tier_notional(
                       risk_policy.sizing_tier(
                           lineup_confirmation=0.0), lineup_confirmation=0.0),
                   "max_new_positions": 4, "weekend_budget_usd": 1000},
        "bankroll_usd": 12998.34,
        "cash_usd": 11062.69,
        "open_positions": ("5 (ledger 2026-11-04 08:21Z, deployed $1,935.65; "
                           "no open soccer positions -> no held-fixture or "
                           "team-cap conflicts)"),
        "fixtures": fixtures, "matches": matches, "no_market": no_market,
        "board_rows": len(board), "board": board,
        "unparsed_questions": sorted(set(unparsed_qs)),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    json.dump({
        "generated_utc": out["generated_utc"], "window_utc": out["window_utc"],
        "matches": matches, "board": board,
        "unparsed_questions": out["unparsed_questions"],
    }, open(BOARD_OUT, "w"), indent=1)
    print("\nboard rows:", len(board), "matches:", len(matches),
          "fixtures w/o markets:", len(no_market), flush=True)
    print("saved", OUT, "and", BOARD_OUT, flush=True)
    pass_rows = [r for r in board if r["passed_numeric"]]
    print("numeric passers:", len(pass_rows), flush=True)
    for r in pass_rows[:20]:
        print("  PASS %s | %s %s line=%s exec=+%dc worst=+%dc var=%.1fc liq=$%d %s" % (
            r["match"], r["kind"], r["side"], r["line"],
            round(100 * (r["exec_edge_haircut"] or 0)),
            round(100 * (r["worst_variant_edge"] or 0)),
            100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
            ";".join(r["entry_flags"][:1])), flush=True)
    print("\nTOP-20 by exec_edge:")
    for r in board[:20]:
        print("  %+6.1fc worst %+6.1fc var %5.1fc | %-44s | %s %s %s | p_med %.3f ask %.3f liq $%.0f | %s" % (
            100 * (r["exec_edge"] if r["exec_edge"] is not None else -9),
            100 * (r["worst_variant_edge"] if r["worst_variant_edge"] is not None else -9),
            100 * (r["var_spread"] or 0), r["match"][:44], r["kind"], r["side"],
            r["line"], r["p_med"], r["exec_ask_vwap250"] or 0,
            r["liq_gamma"] or 0, r["section"]), flush=True)


if __name__ == "__main__":
    main()
