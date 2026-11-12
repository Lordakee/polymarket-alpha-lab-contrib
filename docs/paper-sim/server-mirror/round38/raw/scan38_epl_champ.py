"""Round-38A WEEKEND scan (paper-only): full EPL + Championship slate,
Nov-7 (Sat) and Nov-8 (Sun), fee-aware, both-directions odds board.

Slate (ESPN verified 2026-11-06 ~11:0xZ):
  EPL Sat Nov-7 (4):  12:30Z Leeds-Tottenham, 15:00Z Arsenal-Hull,
                      15:00Z Fulham-Newcastle, 17:30Z Forest-Man City
  EPL Sun Nov-8 (5):  14:00Z Brighton-Brentford, 14:00Z Palace-Liverpool,
                      14:00Z Ipswich-Bournemouth, 14:00Z Sunderland-Chelsea,
                      16:30Z Man Utd-Aston Villa
  Championship Sat Nov-7 (11): 12:30Z Bristol-Norwich, Portsmouth-Stoke,
                      Wrexham-Wolves; 15:00Z Birmingham-Swansea,
                      Blackburn-West Ham, Cardiff-Burnley, Charlton-Sheff Utd,
                      Preston-Southampton, QPR-Lincoln, Watford-Middlesbrough,
                      West Brom-Millwall
  Championship Sun Nov-8: NONE (ESPN eng.2 20261108 = 0 games)

Total 20 fixtures (brief said 15; enumeration found 20 - all modeled).

xG BASES:
  Big-5/EPL: ~/paper-sim/understat_latest.json -> pointer
    round36/raw/xg_fotmob_big5_merged.json (Understat Oct-31 + FotMob
    Nov-1/2 merged). All 18 EPL slate clubs verified: last league game
    Oct-31/Nov-1/Nov-2 IN snapshot; no EPL games Nov-3..5 (intl break;
    ESPN eng.1 20261103/04/05 = 0 games) -> EPL FULLY FRESH.
  Championship: round31/raw/xg_fotmob_championship.json through Nov-3.
    All 9 Nov-3 midweek games verified IN (results cross-checked vs ESPN).
    Nov-4 midweek round NOT in snapshot: Cardiff-West Ham,
    Wrexham-Middlesbrough, Bristol City-Wolves -> SIX clubs stale by
    exactly 1 league game (~1/12 of history): Cardiff City, West Ham,
    Wrexham, Middlesbrough, Bristol City, Wolverhampton.

HELD: #62 Alaves TT O0.5 $250 @ 0.6277 kicks Nov-6 20:00Z (tonight,
DIFFERENT slate) - no overlay on any weekend fixture. Bankroll per
coordinator brief: $13,409 / cash $11,923 / 5 open.

FEE-AWARE GATES (library 5bdae2e3): evaluate_candidate(fee_rate=
FEE_RATE_SPORTS=0.05); +5c exec bar is NET of fees (8c if under-risk);
haircut acts on NET edge; worst_variant_edge stays gross.

Budget: weekend total across ALL agents <= $1,500; this sub-scan's
share: max 3 candidates x $250 (match_winner type $150).
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
    fotmob,
    gates,
    league_strength,
    soccer_model,
    xg,
)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HOME = "/home/ubuntu/paper-sim"
UNDERSTAT_LATEST = f"{HOME}/understat_latest.json"
UNDERSTAT_POINTER = f"{HOME}/understat_latest_pointer.json"
FOTMOB = f"{HOME}/round31/raw/xg_fotmob_championship.json"
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"
OUTDIR = f"{HOME}/round38/raw"
OUT = f"{OUTDIR}/epl_champ_scan.json"
LO = "2026-11-06T11:00:00Z"          # entry window opens at scan time
HI = "2026-11-08T23:59:59Z"          # all weekend kickoffs inside window
DISC_LO = "2026-11-07T00:00:00Z"
DISC_HI = "2026-11-08T23:59:59Z"
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")

ESPN_LEAGUES = {"eng.1": "EPL", "eng.2": "Championship"}
ESPN_DATES = ("20261107", "20261108")

HELD_POSITIONS = {}   # #62 Alaves-Sevilla kicks Nov-6 20:00Z, not this slate

# Per-club xG staleness, verified this session against snapshot per-club
# history + ESPN scoreboard (eng.1/eng.2, 20261031..20261105).
STALENESS = {
    # --- Championship: Nov-4 midweek round missing (snapshot thru Nov-3) ---
    "Cardiff City": {"missing": 1, "detail": "Nov-4 H v West Ham not in snapshot (snapshot thru Nov-3)", "bias": "1 of ~12 league games missing; slight"},
    "West Ham United": {"missing": 1, "detail": "Nov-4 A at Cardiff not in snapshot", "bias": "1 of ~12 league games missing; slight"},
    "Wrexham": {"missing": 1, "detail": "Nov-4 H v Middlesbrough not in snapshot", "bias": "1 of ~12 league games missing; slight"},
    "Middlesbrough": {"missing": 1, "detail": "Nov-4 A at Wrexham not in snapshot", "bias": "1 of ~12 league games missing; slight"},
    "Bristol City": {"missing": 1, "detail": "Nov-4 H v Wolverhampton not in snapshot", "bias": "1 of ~12 league games missing; slight"},
    "Wolverhampton Wanderers": {"missing": 1, "detail": "Nov-4 A at Bristol City not in snapshot", "bias": "1 of ~12 league games missing; slight"},
}
STALE_CLUBS = {t for t, s in STALENESS.items() if s["missing"]}
# affected Saturday fixtures: Bristol-Norwich (Bristol), Wrexham-Wolves (both),
# Cardiff-Burnley (Cardiff), Blackburn-West Ham (West Ham),
# Watford-Middlesbrough (Middlesbrough).

TEAM_ALIASES = {
    # EPL slate
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
    "brighton and hove albion fc": "Brighton", "brighton and hove albion": "Brighton",
    "brighton hove albion": "Brighton", "brighton hove albion fc": "Brighton",
    "brighton": "Brighton",
    "brentford fc": "Brentford", "brentford": "Brentford",
    "crystal palace fc": "Crystal Palace", "crystal palace": "Crystal Palace",
    "liverpool fc": "Liverpool", "liverpool": "Liverpool",
    "ipswich town fc": "Ipswich", "ipswich town": "Ipswich", "ipswich": "Ipswich",
    "afc bournemouth": "Bournemouth", "bournemouth fc": "Bournemouth",
    "bournemouth": "Bournemouth",
    "sunderland afc": "Sunderland", "sunderland": "Sunderland",
    "chelsea fc": "Chelsea", "chelsea": "Chelsea",
    "manchester united fc": "Manchester United", "manchester united": "Manchester United",
    "man utd": "Manchester United", "manchester utd": "Manchester United",
    "aston villa fc": "Aston Villa", "aston villa": "Aston Villa",
    # Championship slate
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
}
CANON_DENY_EXACT = {"az", "nec", "ofi", "ski", "if", "go", "sk", "fk", "fc", "ac", "sc"}


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
        "vlsi", "1899", "09"}]
    return " ".join(toks).strip()


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return []
    return raw or []


def sweep(order, extra_params, max_offset=1000):
    out, offset = [], 0
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
            if slim["id"] not in seen:
                seen[slim["id"]] = slim
        print("sweep %-22s total=%4d in_window=%d unique=%d" % (
            label, len(evs), n, len(seen)), flush=True)
        time.sleep(1.0)
    return seen


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


def comp_of(tags, home_lg, away_lg):
    tset = set(tags)
    for t in tset:
        if t in ("championship", "efl-championship"):
            return "ENG2"
    for t in tset:
        if t in ("epl",):
            return "EPL"
    if home_lg and away_lg:
        if home_lg == away_lg:
            return "EPL" if home_lg == "EPL" else "ENG2"
        return "CROSS(other)"
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


def understat_probe():
    try:
        r = subprocess.run(
            ["curl", "-sS", "-w", "%{http_code}", "--max-time", "12",
             "https://understat.com/league/EPL/2026"],
            capture_output=True, text=True, timeout=20)
        body = (r.stdout or "")
        code = body[-3:] if len(body) >= 3 and body[-3:].isdigit() else ""
        ok = (r.returncode == 0 and code == "200"
              and "teamsData" in body and "errors.css" not in body)
        detail = code + (" maintenance/error page (no teamsData)"
                         if code == "200" and not ok else "")
        return {"ok": ok, "detail": detail[:120]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": repr(e)[:120]}


def section_of(kick):
    if kick < "2026-11-07T00:00:00Z":
        return "pre_window"
    if kick <= "2026-11-07T23:59:59Z":
        return "sat_nov7"
    if kick <= "2026-11-08T23:59:59Z":
        return "sun_nov8"
    return "out_of_range"


def scan_policy(kind, cross):
    if kind == "spread":
        return ("FLAGGED_ONLY", False,
                "spreads flagged-only (blowout-tail rule): counted, never entered")
    if kind == "ml":
        return ("ELIGIBLE-DEPRIORITIZED", True,
                "domestic MW eligible-deprioritized ($150); Championship 1X2 "
                "limitation (WP-P3 gate E) documented where applicable")
    return ("ELIGIBLE", True, "allowed kind under tightened gates")


def espn_fixtures():
    out = {}
    for date in ESPN_DATES:
        day = {}
        for code, label in ESPN_LEAGUES.items():
            try:
                d = get(f"{ESPN}/{code}/scoreboard?dates={date}")
                evs = []
                for ev in d.get("events") or []:
                    comp = (ev.get("competitions") or [{}])[0]
                    teams = {}
                    for c in comp.get("competitors") or []:
                        t = c.get("team") or {}
                        teams["home" if c.get("homeAway") == "home" else "away"] = {
                            "name": t.get("displayName"), "abbr": t.get("abbreviation")}
                    evs.append({"date": ev.get("date"), "name": ev.get("name"),
                                "venue": (comp.get("venue") or {}).get("fullName"),
                                "teams": teams,
                                "status": (ev.get("status") or {}).get("type", {}).get("description")})
                day[label] = evs
            except Exception as e:  # noqa: BLE001
                day[label] = {"error": repr(e)}
        out[date] = day
    return out


def main():
    now = datetime.now(timezone.utc)
    print("UTC now:", now.isoformat(), flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    espn = espn_fixtures()
    json.dump(espn, open(f"{OUTDIR}/espn_fixtures_r38_epl_champ.json", "w"), indent=1)
    n_fixture = 0
    for date, day in espn.items():
        print("\nESPN %s:" % date, flush=True)
        for lg, evs in day.items():
            for ev in (evs if isinstance(evs, list) else []):
                th = ev["teams"].get("home", {}).get("name")
                ta = ev["teams"].get("away", {}).get("name")
                kick = ev.get("date") or ""
                n_fixture += 1
                print("  %-13s %-28s vs %-28s %s @ %s" % (
                    lg, str(ta), str(th), kick, ev.get("venue")), flush=True)
    print("\nESPN fixture count: %d (EPL Sat 4 + Sun 5; Championship Sat 11 + Sun 0 = 20)"
          % n_fixture, flush=True)

    # ---- bridge (provenance only; all pairs domestic this slate) ----
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)
    print("\nBRIDGE LOADED (provenance only; no cross pairs this slate):",
          KAPPA_PATH, flush=True)

    # ---- snapshots via validated loaders ----
    with open(UNDERSTAT_POINTER, "r", encoding="utf-8") as _ph:
        understat_pointer = json.load(_ph)
    print("understat latest pointer ->", understat_pointer.get("target"),
          "pointed_at", understat_pointer.get("pointed_at_utc"), flush=True)
    snapshot = dict(xg.load_xg_snapshot(UNDERSTAT_LATEST))
    fot_payload = fotmob.load_fotmob_snapshot(FOTMOB)
    for k, v in fot_payload.items():
        snapshot[k] = v
    print("snapshot blocks:", sorted(snapshot.keys()), flush=True)
    for lg in BIG5:
        block = snapshot.get(f"{lg}_2026") or {}
        for t in (block.get("teams") or {}).values():
            title = t.get("title")
            if title:
                ALL_TITLES[title] = lg
                TITLE_LEAGUE[title] = lg
    for t in snapshot["Championship_2026"]["teams"].values():
        title = t.get("title")
        if title:
            ALL_TITLES[title] = "Championship"
            TITLE_LEAGUE[title] = "Championship"
    print("registry titles: Big-5 %d + Championship %d" % (
        sum(1 for v in TITLE_LEAGUE.values() if v != "Championship"),
        sum(1 for v in TITLE_LEAGUE.values() if v == "Championship")), flush=True)

    probe = understat_probe()
    print("understat probe:", probe, flush=True)

    # ---- discovery ----
    sweeps = [
        ("date-volume", "volume24hr", {"start_date_min": DISC_LO,
                                       "start_date_max": DISC_HI}),
        ("date-liquidity", "liquidity", {"start_date_min": DISC_LO,
                                         "start_date_max": DISC_HI}),
        ("tag-soccer", "volume24hr", {"tag_slug": "soccer"}),
        ("tag-championship", "volume24hr", {"tag_slug": "championship"}),
        ("tag-efl-champ", "volume24hr", {"tag_slug": "efl-championship"}),
        ("tag-epl", "volume24hr", {"tag_slug": "epl"}),
    ]
    seen = fetch_window(DISC_LO, DISC_HI, sweeps)
    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(f"{OUTDIR}/events_window_38_epl_champ.json", "w"), indent=1)
    print("unique soccer events in discovery range:", len(events), flush=True)

    # ---- classify ----
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
            "section": section_of(kick), "in_entry_window": kick <= HI,
            "modelable": bool(home and away),
            "modelability_class": (
                "domestic-pair" if home and away and lgh == lga else
                "cross-league-bridged" if home and away else
                "model-void-club-or-league-not-in-snapshot"),
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
    print("\nFIXTURE INVENTORY (unique primary fixtures):", flush=True)
    for f in sorted(base_fixtures.values(), key=lambda x: x["kickoff_utc"]):
        if f["comp"] in ("EPL", "ENG2") or (
                f["understat_home"] and f["understat_away"]):
            print("%-6s %-9s %-26s vs %-26s kick=%s class=%s" % (
                f["comp"], f["section"][:9], str(f["understat_home"]),
                str(f["understat_away"]), f["kickoff_utc"],
                f["modelability_class"]), flush=True)

    # ---- model + books + gates ----
    matches, board, prices_only, unparsed_qs = [], [], [], []
    groups = {}
    for fx, e in zip(fixtures, events):
        key = (fx["understat_home"], fx["understat_away"], fx["kickoff_utc"],
               fx["comp"], re.split(r"\s+-\s+", fx["title"], maxsplit=1)[0])
        groups.setdefault(key, {"fx": fx, "events": []})
        groups[key]["events"].append(e)

    for key in sorted(groups, key=lambda k: groups[k]["fx"]["kickoff_utc"]):
        grp = groups[key]
        fx = grp["fx"]
        home, away = fx["understat_home"], fx["understat_away"]
        lgh, lga = fx["home_league"], fx["away_league"]
        cross = bool(lgh and lga and lgh != lga)
        base_title = re.split(r"\s+-\s+", grp["events"][0].get("title") or "",
                              maxsplit=1)[0]
        fkey = fixture_key(home, away) if home and away else None
        held_here = HELD_POSITIONS.get(fkey, []) if fkey else []
        stale_here = sorted({s for s in (home, away) if s in STALE_CLUBS})

        if not fx["modelable"]:
            if fx["comp"] not in ("EPL", "ENG2"):
                continue
            prow, seen_mkt = [], set()
            for e in grp["events"]:
                for m in e["markets"]:
                    if m["id"] in seen_mkt:
                        continue
                    seen_mkt.add(m["id"])
                    side_specs = parse_market_sides(m, None, None)
                    if side_specs is None:
                        continue
                    for token_idx, kind, side_id, line, team_side in side_specs:
                        book = fetch_book(m, token_idx)
                        if book is None:
                            continue
                        walk = gates.walk_book(
                            [(p, s) for p, s in book["asks"]], side="ask")
                        prow.append({
                            "q": m["q"], "kind": kind, "side": side_id,
                            "line": line, "id": m["id"],
                            "bid": book["best_bid"], "ask": book["best_ask"],
                            "ask_vwap250": walk.vwap, "fill_250": walk.filled,
                            "liq_gamma": float(m.get("liq") or 0)})
            prices_only.append({
                "match": base_title, "comp": fx["comp"],
                "kickoff_utc": fx["kickoff_utc"], "section": fx["section"],
                "modelability": "model-void: club(s) not in snapshot universe",
                "rows": prow})
            print("PRICES-ONLY %-40s %-4s kick=%s rows=%d" % (
                base_title, fx["comp"], fx["kickoff_utc"], len(prow)), flush=True)
            continue

        if cross:
            variants = soccer_model.fixture_variants(
                snapshot, home, lgh, away, lga, bridge=kappa)
            method = "bridged 10-variant library path (WP-P2a kappa bridge)"
        else:
            variants = soccer_model.fixture_variants(
                snapshot, home, lgh, away, lga)
            method = ("library fixture_variants 10 sweeps, DOMESTIC %s "
                      "(FotMob WP-P3)" % lgh if lgh == "Championship"
                      else "library fixture_variants 10 sweeps, domestic EPL")
        if variants is None:
            fx["modelable"] = False
            fx["model_note"] = "variants returned None (missing blocks/teams)"
            print("MODEL-VOID %s: variants None" % base_title, flush=True)
            continue
        vs = [{"lambdas": (v.lambdas[0], v.lambdas[1]), "outputs": v.outputs,
               "spec": v.spec.name} for v in variants]
        lam_h = soccer_model.median([v["lambdas"][0] for v in vs])
        lam_a = soccer_model.median([v["lambdas"][1] for v in vs])
        f = league_strength.bridge_factor(kappa, lgh, lga) if cross else None
        p1x2 = {
            "H": soccer_model.median([v["outputs"].home_win for v in vs]),
            "D": soccer_model.median([v["outputs"].draw for v in vs]),
            "A": soccer_model.median([v["outputs"].away_win for v in vs]),
        }
        form_h = xg.recent_form(snapshot, home) if lgh != "Championship" else None
        form_a = xg.recent_form(snapshot, away) if lga != "Championship" else None
        matches.append({
            "match": base_title, "comp": fx["comp"], "cross_league": cross,
            "section": fx["section"], "in_entry_window": fx["in_entry_window"],
            "home_league": lgh, "away_league": lga,
            "fixture_key": fkey,
            "gamma_event_ids": sorted({e["id"] for e in grp["events"]}),
            "kickoff_utc": fx["kickoff_utc"],
            "bridge_factor": round(f, 4) if f else None,
            "kappa_home": kappa.get(lgh), "kappa_away": kappa.get(lga),
            "lambda_home": round(lam_h, 3), "lambda_total": round(lam_h + lam_a, 3),
            "lambda_away": round(lam_a, 3),
            "p1x2_med": {k: round(v, 4) for k, v in p1x2.items()},
            "form_home_last5": ({"gp": form_h.games, "gf": form_h.goals_for,
                                 "ga": form_h.goals_against,
                                 "xg_for": round(form_h.xg_per_game * form_h.games, 2),
                                 "o25_hits": form_h.over_2_5_hits,
                                 "btts_hits": form_h.btts_hits} if form_h else None),
            "form_away_last5": ({"gp": form_a.games, "gf": form_a.goals_for,
                                 "ga": form_a.goals_against,
                                 "xg_for": round(form_a.xg_per_game * form_a.games, 2),
                                 "o25_hits": form_a.over_2_5_hits,
                                 "btts_hits": form_a.btts_hits} if form_a else None),
            "stale_clubs": stale_here,
            "staleness": {s: STALENESS[s] for s in stale_here},
            "method": method,
        })
        o25_combined = ((form_h.over_2_5_hits if form_h else 0)
                        + (form_a.over_2_5_hits if form_a else 0))
        seen_mkt = set()
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
                        o25_hits=o25_combined, lambda_total=lam_h + lam_a,
                        lambda_home=lam_h, lambda_away=lam_a,
                        line=line if line else 2.5)
                    report = gates.evaluate_candidate(
                        quote, book["asks"], gamma_liquidity=liq, under_risk=ur,
                        fee_rate=gates.FEE_RATE_SPORTS)
                    pol, pol_eligible, pol_reason = scan_policy(kind, cross)
                    lib_pol = gates.suspension_policy(kind, cross_league=cross)
                    exit_walk = gates.walk_book(
                        [(p, s) for p, s in book["bids"]], side="bid")
                    row = {
                        "match": base_title, "comp": fx["comp"],
                        "cross_league": cross, "fixture_key": fkey,
                        "section": fx["section"],
                        "in_entry_window": fx["in_entry_window"],
                        "q": m["q"], "kind": kind, "side": side_id,
                        "line": line, "team_side": team_side,
                        "id": m["id"],
                        "policy": pol, "policy_eligible": pol_eligible,
                        "policy_reason": pol_reason,
                        "library_policy": lib_pol.policy,
                        "library_policy_reason": lib_pol.reason,
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
                        "exec_edge_gross": report.exec_edge_gross,
                        "fee_per_share": (round(gates.fee_cost(report.walk.vwap,
                                           gates.FEE_RATE_SPORTS), 4)
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
                    if cross and row["passed_numeric"]:
                        worst = report.worst_variant_edge
                        if worst is None or worst < 0.05 - 5e-4:
                            row["passed_numeric"] = False
                            row["cross_league_5c_worst"] = False
                        else:
                            row["cross_league_5c_worst"] = True
                    flags = []
                    stake = 250
                    if kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if kind == "ml":
                        stake = 150
                        flags.append("MW eligible-deprioritized; $150"
                                     + ("; Championship 1X2 limitation (gate E)"
                                        if lgh == "Championship" else ""))
                    row["stake_usd"] = stake
                    if stale_here:
                        flags.append(
                            "STALE-XG: %s (Nov-4 midweek round not in FotMob "
                            "snapshot; 1 league game missing each)" % ", ".join(stale_here))
                    if held_here:
                        flags.append("HELD-FIXTURE overlay active")
                    if row["passed_numeric"] and pol_eligible:
                        flags.append("NUMERIC-PASS (pending news-concordance)")
                    hrs = max(1, round((
                        datetime.fromisoformat(
                            fx["kickoff_utc"].replace("Z", "+00:00"))
                        - now).total_seconds() / 3600))
                    flags.append("T-%dh pre-kick (XIs unset; ~1h pre-kick drop)"
                                 % hrs)
                    if not fx["in_entry_window"]:
                        flags.append("ENTRY-TIMING: kickoff after window close")
                    row["entry_flags"] = flags
                    row["enterable"] = bool(
                        row["passed_numeric"] and pol_eligible and not any(
                            f.startswith(("BANNED", "SPREADS", "HELD")) for f in flags))
                    board.append(row)
        print("MODELED %-44s %-4s cross=%-5s kick=%s lam=%.2f/%.2f rows=%d stale=%s" % (
            base_title, fx["comp"], cross, fx["kickoff_utc"], lam_h, lam_a,
            sum(1 for r in board if r["fixture_key"] == fkey),
            ",".join(stale_here) or "-"), flush=True)

    board.sort(key=lambda r: (-(r["exec_edge_haircut"] if r["exec_edge_haircut"] is not None else -9),
                              r["match"]))
    not_modelable = [f for f in fixtures if not f["modelable"]
                     and f["comp"] in ("EPL", "ENG2")]

    n_stale_games = sum(s["missing"] for s in STALENESS.values())
    out = {
        "scan": "soccer-weekend",
        "round": 38,
        "sub_scan": ("EPL + Championship FULL WEEKEND (round-38A): 4 EPL Sat + "
                     "5 EPL Sun + 11 Championship Sat + 0 Championship Sun = 20 "
                     "fixtures (brief said 15; enumeration = 20); first FULL "
                     "Championship weekend modeled on FotMob WP-P3 data; all "
                     "pairs domestic (no bridge needed); fee-aware both-"
                     "directions odds board; 6 Championship clubs STALE by "
                     "exactly the Nov-4 midweek round (Cardiff, West Ham, "
                     "Wrexham, Middlesbrough, Bristol City, Wolves) - snapshot "
                     "fresh through Nov-3 only; EPL 18/18 clubs FULLY FRESH "
                     "(no EPL games Nov-3..5)"),
        "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("entry-placement window (brief): scan time Nov-6 "
                                "~11:00Z .. Nov-8 23:59Z; Saturday games T-26h+, "
                                "Sunday T-51h+ at scan; XIs unset; news-"
                                "concordance + T-2h re-check before entry")},
        "discovery_range_utc": {"lo": DISC_LO, "hi": DISC_HI,
                                "note": ("all Nov-7 and Nov-8 soccer events; "
                                         "weekend slate only")},
        "espn_fixture_source": {"fetched_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
            "raw": "round38/raw/espn_fixtures_r38_epl_champ.json",
            "endpoints": {f"{c}/{d}": f"{ESPN}/{c}/scoreboard?dates={d}"
                          for d in ESPN_DATES for c in ESPN_LEAGUES},
            "sunday_championship": "NONE (eng.2 20261108 = 0 games)"},
        "bridge": {
            "kappa_path": KAPPA_PATH,
            "loaded_via": "league_strength.load_kappa_report (provenance only)",
            "kappa": {k: round(v, 6) for k, v in kappa.items()},
            "note": ("no cross-league pair in this slate; bridge not exercised"),
        },
        "xg_bases": {
            "big5": {"path": understat_pointer.get("target"),
                     "pointer": UNDERSTAT_POINTER,
                     "pointer_sha256": understat_pointer.get("sha256"),
                     "fresh_through_utc": "2026-11-02 (Understat Oct-31 + FotMob Nov-1/2 merged)",
                     "per_club_verified": ("all 18 EPL slate clubs carry full "
                                           "pre-break history; ESPN eng.1 Nov-3/4/5 = 0 games "
                                           "-> zero missing league games"),
                     "http_probe_at_run": probe},
            "championship": {"path": FOTMOB,
                             "fresh_through_utc": "2026-11-03",
                             "validation": "WP-P3 gate D walk-forward PASS (O/U, BTTS, TT)",
                             "nov3_round_verified": ("all 9 Nov-3 midweek games IN "
                                                     "snapshot, results cross-checked vs ESPN"),
                             "nov4_round_missing": ("Cardiff-West Ham, Wrexham-"
                                                    "Middlesbrough, Bristol City-Wolves NOT in "
                                                    "snapshot -> 6 clubs 1 game stale")},
            "championship_1x2_limitation": ("gate E failure: relegated-EPL "
                                            "fallback clubs distort 1X2; O/U/"
                                            "BTTS/TT unaffected"),
        },
        "staleness_quantification": {
            "method": ("per-club: last snapshot game vs ESPN eng.2 scoreboard "
                       "Nov-2..Nov-5 (verified this session)"),
            "clubs": STALENESS,
            "affected_fixtures": [
                "Bristol City vs Norwich City (Bristol City stale)",
                "Wrexham vs Wolverhampton Wanderers (BOTH stale)",
                "Cardiff City vs Burnley (Cardiff stale)",
                "Blackburn Rovers vs West Ham United (West Ham stale)",
                "Watford vs Middlesbrough (Middlesbrough stale)",
            ],
            "totals": {
                "clubs_scope": 40,
                "clubs_fully_fresh": 34,
                "clubs_missing_league_games": 6,
                "league_games_missing_total": n_stale_games,
                "pooled_missing_share": round(n_stale_games / (40 * 12.0), 4),
                "resolution_note": ("FotMob Championship backfill covers through "
                                    "Nov-3; the Nov-4 round would refresh these "
                                    "6 clubs (out of scope for this scan; flagged)"),
            },
        },
        "method": ("Gamma date-window + tag discovery -> soccer events; ALL 20 "
                   "fixtures domestic pairs -> standard 10-variant "
                   "fixture_variants (no bridge); Championship pairs on FotMob "
                   "snapshot (WP-P3; MW $150 1X2-limited); full odds board "
                   "both token sides; CLOB $250 ask-VWAP walk; frozen gates; "
                   "fee-aware net-edge bars (r35 fee model); no held overlay "
                   "in this slate (#62 Alaves-Sevilla kicks Nov-6 20:00Z)"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "5bdae2e3",
                    "selfcheck": "PASS 10/10 (re-run 2026-11-06 ~10:5xZ)",
                    "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
                    "fee_model": ("evaluate_candidate(..., fee_rate="
                                  "FEE_RATE_SPORTS) - exec bar is NET of the "
                                  "Polymarket fee 0.05*p*(1-p) per share at the "
                                  "walked entry price; worst_variant_edge stays "
                                  "GROSS (model-agreement margin)")},
        "gates": dict(gates.GATES, notes=(
            "NET-EDGE BARS: exec>=+5c net of sports fee 0.05*p*(1-p) at the "
            "walked price (8c net if under-risk); domestic worst>=+4c gross; "
            "var<=6c; liq>=5k; fill_250; entry .10-.92; 50-50 haircut acts on "
            "the NET edge; news-concordance at candidate stage; spreads "
            "flagged-only; MW $150 deprioritized")),
        "max_new_positions": 3, "stake_per_position_usd": 250,
        "weekend_budget_note": ("weekend total across ALL agents <= $1,500; "
                                "this sub-scan share: max 3 candidates "
                                "($250 each; MW $150)"),
        "bankroll_usd": 13409.00, "cash_usd": 11923.00,
        "open_positions": 5,
        "open_positions_note": ("per coordinator brief bankroll/cash; 5 open = "
                                "#62 soccer (Alaves TT O0.5, kicks Nov-6 20:00Z, "
                                "NOT in this slate) + 4 non-soccer"),
        "held_positions": HELD_POSITIONS,
        "fixtures": fixtures, "not_modelable": not_modelable,
        "matches": matches, "prices_only": prices_only,
        "board_rows": len(board), "board": board,
        "unparsed_questions": sorted(set(unparsed_qs)),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nboard rows:", len(board), "matches:", len(matches),
          "prices-only fixtures:", len(prices_only), flush=True)
    print("saved", OUT, flush=True)

    pass_rows = [r for r in board if r["passed_numeric"] and r["policy_eligible"]]
    print("\nnumeric passers (eligible kinds):", len(pass_rows))
    for r in pass_rows[:40]:
        print("  PASS %-40s %-11s %-9s line=%-4s net=+%5.1fc worst=+%5.1fc "
              "var=%5.2fc liq=$%6.0f ask=%s p_med=%.3f stake=$%d %s" % (
                  r["match"][:40], r["kind"], r["side"], r["line"],
                  100 * (r["exec_edge_haircut"] or 0),
                  100 * (r["worst_variant_edge"] or 0),
                  100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
                  r["exec_ask_vwap250"], r["p_med"], r["stake_usd"],
                  ";".join(r["entry_flags"])[:90]))

    print("\nTOP-30 by haircut net edge:")
    for r in board[:30]:
        print("  NET %+6.1fc (gross %+6.1fc fee %.2fc) worst %+6.1fc var %5.2fc "
              "| %-38s | %-11s %-9s %-4s | p_med %.3f ask %s liq $%.0f" % (
                  100 * (r["exec_edge_haircut"] if r["exec_edge_haircut"] is not None else -9),
                  100 * (r["exec_edge_gross"] if r["exec_edge_gross"] is not None else -9),
                  100 * (r["fee_per_share"] or 0),
                  100 * (r["worst_variant_edge"] if r["worst_variant_edge"] is not None else -9),
                  100 * (r["var_spread"] or 0), r["match"][:38], r["kind"],
                  r["side"], r["line"], r["p_med"], r["exec_ask_vwap250"],
                  r["liq_gamma"] or 0))


if __name__ == "__main__":
    main()
