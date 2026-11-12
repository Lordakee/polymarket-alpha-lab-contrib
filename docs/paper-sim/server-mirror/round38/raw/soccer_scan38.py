"""Round-38C SOCCER sub-scan (paper-only): Bundesliga + Ligue 1 weekend.

Slate (task brief, ESPN-verified 2026-11-06 ~10:5xZ): 16 fixtures.
  Bundesliga Sat Nov-7 (5): Dortmund-Elversberg 14:30Z, Mainz-Bayern 14:30Z,
    Leipzig-Augsburg 14:30Z, Paderborn-Frankfurt 14:30Z,
    Stuttgart-Bremen 17:30Z
  Bundesliga Sun Nov-8 (3): Cologne-Leverkusen 14:30Z, Freiburg-Union 16:30Z,
    Hoffenheim-Schalke 18:30Z
  Ligue 1 Sat Nov-7 (2): Auxerre-ParisFC 18:00Z, PSG-Troyes 20:05Z
  Ligue 1 Sun Nov-8 (6): Rennes-Lille 14:00Z, Angers-Nice 16:15Z,
    Brest-Lyon 16:15Z, Le Havre-Lorient 16:15Z, Le Mans-Monaco 16:15Z,
    Lens-Marseille 19:45Z

All 16 are DOMESTIC same-league pairs -> standard 10-variant
fixture_variants path; kappa bridge loaded for provenance only
(cross-league MW re-enabled at 5bdae2e3 but no cross pair in slate).

xG base: ~/paper-sim/understat_latest.json (FotMob merged through Nov-1/2;
pointer target round36/raw/xg_fotmob_big5_merged.json). All 32 clubs
verified present with full pre-break history (Bundesliga 8 gp, Ligue 1
9 gp); international break Nov-3..6 (ESPN idle-date check) -> no missing
league games; staleness missing==0 for every club.

FEE-AWARE GATES (library 5bdae2e3): evaluate_candidate(fee_rate=
FEE_RATE_SPORTS=0.05); +5c exec bar NET of fees (+8c under-risk);
haircut on NET edge; worst_variant_edge gross. Spreads flagged-only.
Domestic match_winner ELIGIBLE-DEPRIORITIZED $150.

Budget: bankroll $13,409 / cash $11,923 (coordinator brief). Weekend cap
across ALL agents $1,500; this sub-scan's share max 3 positions.
No held positions on these 16 fixtures (only known held soccer row #62
is alaves-sevilla, kicks Nov-6 20:00Z, outside this slate).

Entries placed at scan time (~11:0xZ Nov-6) are T-27h..T-57h pre-kick:
XIs unset; news-concordance re-check required before entry confirmation.
"""
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from polymarket_alpha_lab.papersim import (
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
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"
OUTDIR = f"{HOME}/round38/raw"
OUT = f"{OUTDIR}/bund_ligue_scan.json"
LO = "2026-11-06T10:00:00Z"
HI = "2026-11-08T23:59:59Z"
DISC_LO = "2026-11-07T00:00:00Z"
DISC_HI = "2026-11-08T23:59:59Z"
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")

ESPN_LEAGUES = {"ger.1": "Bundesliga", "fra.1": "Ligue_1"}
ESPN_DATES = ("20261107", "20261108")
ESPN_IDLE_DATES = ("20261103", "20261104", "20261105", "20261106")

HELD_POSITIONS = {}  # none of the 16 slate fixtures carries a held row

# snapshot titles for the 32 slate clubs (verified present + fresh)
SLUB_CLUBS = {
    "Bundesliga": [
        "Borussia Dortmund", "Elversberg", "Mainz 05", "Bayern Munich",
        "RasenBallsport Leipzig", "Augsburg", "Paderborn",
        "Eintracht Frankfurt", "VfB Stuttgart", "Werder Bremen",
        "FC Cologne", "Bayer Leverkusen", "Freiburg", "Union Berlin",
        "Hoffenheim", "Schalke 04",
    ],
    "Ligue_1": [
        "Auxerre", "Paris FC", "Paris Saint Germain", "Troyes",
        "Rennes", "Lille", "Angers", "Nice", "Brest", "Lyon",
        "Le Havre", "Lorient", "Le Mans", "Monaco", "Lens", "Marseille",
    ],
}

TEAM_ALIASES = {
    # Bundesliga
    "borussia dortmund": "Borussia Dortmund", "dortmund": "Borussia Dortmund",
    "bv borussia dortmund": "Borussia Dortmund", "bsv borussia dortmund": "Borussia Dortmund",
    "sv elversberg": "Elversberg", "elversberg": "Elversberg",
    "sv 07 elversberg": "Elversberg",
    "mainz": "Mainz 05", "mainz 05": "Mainz 05", "fsv mainz 05": "Mainz 05",
    "1.fsv mainz 05": "Mainz 05", "1. fsv mainz 05": "Mainz 05",
    "fsv mainz": "Mainz 05", "mainz 05b": "Mainz 05",
    "bayern munich": "Bayern Munich", "bayern": "Bayern Munich",
    "fc bayern munich": "Bayern Munich", "fc bayern": "Bayern Munich",
    "fc bayern munchen": "Bayern Munich", "bayern munchen": "Bayern Munich",
    "munchen": "Bayern Munich",
    "rb leipzig": "RasenBallsport Leipzig", "leipzig": "RasenBallsport Leipzig",
    "rasenballsport leipzig": "RasenBallsport Leipzig",
    "rbl": "RasenBallsport Leipzig",
    "fc augsburg": "Augsburg", "augsburg": "Augsburg",
    "sc paderborn": "Paderborn", "paderborn": "Paderborn",
    "sc paderborn 07": "Paderborn",
    "eintracht frankfurt": "Eintracht Frankfurt", "frankfurt": "Eintracht Frankfurt",
    "vfb stuttgart": "VfB Stuttgart", "stuttgart": "VfB Stuttgart",
    "werder bremen": "Werder Bremen", "bremen": "Werder Bremen",
    "sv werder bremen": "Werder Bremen",
    "fc koln": "FC Cologne", "koln": "FC Cologne", "cologne": "FC Cologne",
    "fc cologne": "FC Cologne", "1 fc koln": "FC Cologne",
    "bayer leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "bayer 04 leverkusen": "Bayer Leverkusen",
    "sc freiburg": "Freiburg", "freiburg": "Freiburg",
    "union berlin": "Union Berlin", "1 fc union berlin": "Union Berlin",
    "fc union berlin": "Union Berlin", "union": "Union Berlin",
    "tsg hoffenheim": "Hoffenheim", "hoffenheim": "Hoffenheim",
    "tsg 1899 hoffenheim": "Hoffenheim",
    "schalke 04": "Schalke 04", "schalke": "Schalke 04",
    "fc schalke 04": "Schalke 04", "fc gelsenkirchen-schalke 04": "Schalke 04",
    "borussia vlsi monchengladbach": "Borussia M.Gladbach",
    "borussia monchengladbach": "Borussia M.Gladbach",
    "hamburger sv": "Hamburger SV",
    # Ligue 1
    "aj auxerre": "Auxerre", "auxerre": "Auxerre",
    "paris fc": "Paris FC", "parisfc": "Paris FC",
    "paris saint germain": "Paris Saint Germain", "psg": "Paris Saint Germain",
    "paris saint-germain": "Paris Saint Germain",
    "paris sg": "Paris Saint Germain",
    "estac troyes": "Troyes", "troyes": "Troyes", "troyes ac": "Troyes",
    "stade rennais": "Rennes", "rennes": "Rennes",
    "stade rennais fc": "Rennes", "srfc": "Rennes",
    "stade rennais fc 1901": "Rennes", "stade rennais 1901": "Rennes",
    "stade rennais fc 1901b": "Rennes",
    "lille": "Lille", "losc lille": "Lille", "losc": "Lille",
    "lille osc": "Lille",
    "losc losc": "Lille",
    "angers": "Angers", "angers sco": "Angers",
    "ogc nice": "Nice", "nice": "Nice", "ogcn": "Nice",
    "stade brestois": "Brest", "brest": "Brest", "stade brestois 29": "Brest",
    "sb29": "Brest",
    "olympique lyonnais": "Lyon", "lyon": "Lyon", "ol lyon": "Lyon",
    "le havre": "Le Havre", "le havre ac": "Le Havre",
    "fc lorient": "Lorient", "lorient": "Lorient",
    "le mans": "Le Mans", "le mans fc": "Le Mans",
    "monaco": "Monaco", "as monaco": "Monaco",
    "lens": "Lens", "rc lens": "Lens",
    "marseille": "Marseille", "olympique de marseille": "Marseille",
    "om marseille": "Marseille", "om": "Marseille",
    "olympique marseille": "Marseille",
    # misc retained
    "sevilla fc": "Sevilla", "deportivo alaves": "Alaves",
}
CANON_DENY_EXACT = {"az", "nec", "ofi", "ski", "if", "go", "sk", "fk", "fc", "ac", "sc", "om", "ol", "psg", "om"}


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
    s = strip_accents(str(s).lower())
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
        if t in ("bundesliga", "ligue-1"):
            return "BIG5-DOMESTIC"
    for t in tset:
        if t in ("epl", "laliga", "serie-a", "championship", "efl-championship"):
            return "OTHER-BIG5"
    if home_lg and away_lg and home_lg != away_lg:
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
        if home is None:
            return None
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
        return "sat_nov7 (IN window)"
    if kick <= "2026-11-08T23:59:59Z":
        return "sun_nov8 (IN window)"
    return "post_window"


def scan_policy(kind, cross):
    if kind == "spread":
        return ("FLAGGED_ONLY", False,
                "spreads flagged-only (blowout-tail rule): counted, never entered")
    if kind == "ml":
        return ("ELIGIBLE-DEPRIORITIZED", True,
                "domestic MW eligible-deprioritized ($150); all 16 pairs "
                "domestic (bridge not exercised)")
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
                    evs.append({"date": norm_ts(ev.get("date")), "name": ev.get("name"),
                                "venue": (comp.get("venue") or {}).get("fullName"),
                                "teams": teams,
                                "status": (ev.get("status") or {}).get("type", {}).get("description")})
                day[label] = evs
            except Exception as e:  # noqa: BLE001
                day[label] = {"error": repr(e)}
        out[date] = day
    return out


def espn_idle_check():
    """November international break: no ger.1/fra.1 games Nov 3-6."""
    res = {}
    for date in ESPN_IDLE_DATES:
        n = 0
        for code in ESPN_LEAGUES:
            try:
                d = get(f"{ESPN}/{code}/scoreboard?dates={date}")
                n += len(d.get("events") or [])
            except Exception:  # noqa: BLE001
                n += 0
            time.sleep(0.3)
        res[date] = n
    return res


def main():
    now = datetime.now(timezone.utc)
    print("UTC now:", now.isoformat(), flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    espn = espn_fixtures()
    json.dump(espn, open(f"{OUTDIR}/espn_fixtures_r38.json", "w"), indent=1)
    idle = espn_idle_check()
    print("ESPN idle-date check (ger.1/fra.1 events Nov 3-6):", idle, flush=True)

    # ---- bridge (provenance only; all pairs domestic) ----
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)
    print("\nBRIDGE LOADED (provenance only; no cross pairs in slate):",
          KAPPA_PATH, flush=True)

    # ---- snapshots via validated loaders ----
    with open(UNDERSTAT_POINTER, "r", encoding="utf-8") as _ph:
        understat_pointer = json.load(_ph)
    print("understat latest pointer ->", understat_pointer.get("target"),
          "pointed_at", understat_pointer.get("pointed_at_utc"), flush=True)
    snapshot = dict(xg.load_xg_snapshot(UNDERSTAT_LATEST))
    for lg in BIG5:
        block = snapshot.get(f"{lg}_2026") or {}
        for t in (block.get("teams") or {}).values():
            title = t.get("title")
            if title:
                ALL_TITLES[title] = lg
                TITLE_LEAGUE[title] = lg
    print("registry titles (Big-5):", len(TITLE_LEAGUE), flush=True)

    probe = understat_probe()
    print("understat probe:", probe, flush=True)

    # ---- staleness: per-club verification against snapshot history ----
    STALENESS = {}
    fresh_floor = "2026-10-30"
    for lg, clubs in SLUB_CLUBS.items():
        teams = (snapshot.get(f"{lg}_2026") or {}).get("teams") or {}
        by_title = {v.get("title"): v for v in teams.values()}
        for c in clubs:
            h = (by_title.get(c) or {}).get("history") or []
            last = h[-1] if h else None
            last_d = str(last.get("date") or "")[:10] if last else ""
            missing = 0 if (last_d and last_d >= fresh_floor) else 1
            STALENESS[c] = {
                "missing": missing,
                "detail": ("games=%d last=%s %s-%s %s" % (
                    len(h), last_d, last.get("scored"), last.get("missed"),
                    last.get("result"))) if last else "NO HISTORY",
                "bias": "none" if missing == 0 else "lambda stale (missing round)",
            }
    STALE_CLUBS = {t for t, s in STALENESS.items() if s["missing"]}
    print("staleness: %d/%d clubs fresh" % (
        len(STALENESS) - len(STALE_CLUBS), len(STALENESS)), flush=True)
    for c in sorted(STALE_CLUBS):
        print("  STALE", c, STALENESS[c], flush=True)

    # ---- expected fixtures from ESPN (orientation truth) ----
    EXPECTED = {}
    for date, day in espn.items():
        for lg, evs in day.items():
            for ev in (evs if isinstance(evs, list) else []):
                th = ev["teams"].get("home", {}).get("name")
                ta = ev["teams"].get("away", {}).get("name")
                ch, ca = canon_team(th), canon_team(ta)
                if not ch or not ca:
                    print("ESPN canon FAIL", th, "->", ch, "|", ta, "->", ca, flush=True)
                    continue
                key = frozenset((ch, ca))
                EXPECTED[key] = {
                    "league": lg, "home": ch, "away": ca,
                    "kickoff_utc": ev["date"], "venue": ev.get("venue"),
                    "espn_name": ev.get("name"),
                }
    print("\nEXPECTED fixtures from ESPN:", len(EXPECTED), flush=True)
    for v in sorted(EXPECTED.values(), key=lambda x: x["kickoff_utc"]):
        print("  %-10s %-24s vs %-24s %s" % (
            v["league"], v["home"], v["away"], v["kickoff_utc"]), flush=True)

    # ---- discovery ----
    sweeps = [
        ("date-volume", "volume24hr", {"start_date_min": DISC_LO,
                                       "start_date_max": DISC_HI}),
        ("date-liquidity", "liquidity", {"start_date_min": DISC_LO,
                                         "start_date_max": DISC_HI}),
        ("tag-soccer", "volume24hr", {"tag_slug": "soccer"}),
        ("tag-bundesliga", "volume24hr", {"tag_slug": "bundesliga"}),
        ("tag-ligue-1", "volume24hr", {"tag_slug": "ligue-1"}),
    ]
    seen = fetch_window(DISC_LO, DISC_HI, sweeps)
    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(f"{OUTDIR}/events_window_38.json", "w"), indent=1)
    print("unique soccer events in discovery range:", len(events), flush=True)

    # ---- classify + restrict to the 16 slate fixtures ----
    fixtures, unmatched = [], []
    for e in events:
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        home_raw = parts[0].strip() if parts else ""
        away_raw = parts[1].strip() if len(parts) > 1 else ""
        home = canon_team(home_raw)
        away = canon_team(away_raw)
        lgh = TITLE_LEAGUE.get(home) if home else None
        lga = TITLE_LEAGUE.get(away) if away else None
        key = frozenset((home, away)) if home and away else None
        exp = EXPECTED.get(key) if key else None
        if exp is None:
            # not a slate fixture; keep for inventory if big5 domestic
            if {"bundesliga", "ligue-1"} & set(e.get("tags") or []):
                unmatched.append({"title": e.get("title"), "kick": e["kick"]})
            continue
        # use ESPN orientation + kickoff as truth
        fixtures.append({
            "event_id": e["id"], "title": e["title"], "kickoff_utc": exp["kickoff_utc"],
            "comp": "BIG5-DOMESTIC", "tags": e["tags"],
            "section": section_of(exp["kickoff_utc"]), "in_entry_window": True,
            "modelable": True, "modelability_class": "domestic-pair",
            "same_league": True, "league": exp["league"],
            "understat_home": exp["home"], "understat_away": exp["away"],
            "home_league": exp["league"], "away_league": exp["league"],
            "espn_kickoff": exp["kickoff_utc"], "gamma_kick": e["kick"],
            "venue": exp["venue"], "liq_event": e.get("liq"), "vol24": e.get("vol24"),
            "n_markets": len(e["markets"]),
        })
    # dedupe by fixture pair (multiple gamma events may cover same game)
    dedup = {}
    for f in fixtures:
        dedup[frozenset((f["understat_home"], f["understat_away"]))] = f
    fixtures = list(dedup.values())
    fixtures.sort(key=lambda f: f["kickoff_utc"])
    print("\nSLATE FIXTURES matched on Gamma:", len(fixtures), flush=True)
    for f in fixtures:
        print("  %-10s %-24s vs %-24s kick=%s markets=%d" % (
            f["league"], f["understat_home"], f["understat_away"],
            f["kickoff_utc"], f["n_markets"]), flush=True)
    if len(fixtures) != 16:
        print("!! WARNING: expected 16 slate fixtures, matched", len(fixtures), flush=True)
    if unmatched:
        print("non-slate bundesliga/ligue-1 events in range (inventory only):",
              flush=True)
        for u in unmatched[:12]:
            print("  ", u, flush=True)

    # re-attach gamma events per fixture for market enumeration
    ev_by_key = {}
    for e in events:
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        h = canon_team(parts[0].strip()) if parts else None
        a = canon_team(parts[1].strip()) if len(parts) > 1 else None
        if h and a and frozenset((h, a)) in dedup:
            ev_by_key.setdefault(frozenset((h, a)), []).append(e)

    # ---- model + books + gates ----
    matches, board, unparsed_qs = [], [], []
    for f in fixtures:
        home, away = f["understat_home"], f["understat_away"]
        lgh = f["home_league"]
        base_title = f"{home} vs. {away}"
        fkey = fixture_key(home, away)
        stale_here = sorted({s for s in (home, away) if s in STALE_CLUBS})
        grp_events = ev_by_key.get(frozenset((home, away)), [])

        variants = soccer_model.fixture_variants(snapshot, home, lgh, away, lgh)
        method = ("library fixture_variants 10 sweeps, DOMESTIC %s" % lgh)
        if variants is None:
            f["modelable"] = False
            f["model_note"] = "variants returned None (missing blocks/teams)"
            print("MODEL-VOID %s: variants None" % base_title, flush=True)
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
        form_h = xg.recent_form(snapshot, home)
        form_a = xg.recent_form(snapshot, away)
        matches.append({
            "match": base_title, "comp": f["comp"], "cross_league": False,
            "league": lgh, "section": f["section"], "in_entry_window": True,
            "home_league": lgh, "away_league": lgh,
            "fixture_key": fkey,
            "gamma_event_ids": sorted({e["id"] for e in grp_events}),
            "kickoff_utc": f["kickoff_utc"], "venue": f["venue"],
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
        n_rows = 0
        for e in grp_events:
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
                    pol, pol_eligible, pol_reason = scan_policy(kind, False)
                    lib_pol = gates.suspension_policy(kind, cross_league=False)
                    exit_walk = gates.walk_book(
                        [(p, s) for p, s in book["bids"]], side="bid")
                    row = {
                        "match": base_title, "league": lgh, "comp": f["comp"],
                        "cross_league": False, "fixture_key": fkey,
                        "section": f["section"], "in_entry_window": True,
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
                    flags = []
                    stake = 250
                    if kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if kind == "ml":
                        stake = 150
                        flags.append("MW eligible-deprioritized; $150")
                    row["stake_usd"] = stake
                    if stale_here:
                        flags.append("STALE-XG: %s" % ", ".join(stale_here))
                    if row["passed_numeric"] and pol_eligible:
                        flags.append("NUMERIC-PASS (pending news-concordance)")
                    hrs = max(1, round((
                        datetime.fromisoformat(
                            f["kickoff_utc"].replace("Z", "+00:00"))
                        - now).total_seconds() / 3600))
                    flags.append("T-%dh pre-kick (XIs unset; ~1h pre-kick drop)"
                                 % hrs)
                    row["entry_flags"] = flags
                    row["enterable"] = bool(
                        row["passed_numeric"] and pol_eligible and not any(
                            f.startswith(("BANNED", "SPREADS", "HELD")) for f in flags))
                    board.append(row)
                    n_rows += 1
        print("MODELED %-34s %-10s kick=%s lam=%.2f/%.2f rows=%d stale=%s" % (
            base_title, lgh, f["kickoff_utc"], lam_h, lam_a, n_rows,
            ",".join(stale_here) or "-"), flush=True)

    board.sort(key=lambda r: (-(r["exec_edge_haircut"] if r["exec_edge_haircut"] is not None else -9),
                              r["match"]))
    n_stale_games = sum(s["missing"] for s in STALENESS.values())
    out = {
        "scan": "soccer", "round": 38, "sub_scan": "bund_ligue",
        "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "slate": ("Bundesliga (8) + Ligue 1 (8) weekend fixtures Nov-7/8; "
                  "ESPN-verified kickoffs; all DOMESTIC pairs -> standard "
                  "10-variant path; bridge loaded for provenance only"),
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("entries placed at scan time (~11Z Nov-6) are "
                                "T-27h..T-57h pre-kick; XIs unset; "
                                "news-concordance re-check before entry")},
        "discovery_range_utc": {"lo": DISC_LO, "hi": DISC_HI},
        "espn_fixture_source": {
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "raw": "round38/raw/espn_fixtures_r38.json",
            "idle_dates_check": idle,
            "note": ("ger.1/fra.1 scoreboards 2026-11-07/08 enumerate exactly "
                     "the 16 slate fixtures; Nov 3-6 idle (international break) "
                     "confirms xG snapshot completeness")},
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
                     "fresh_through_utc": "2026-11-01/02 (FotMob merged round)",
                     "per_club_verified": ("all 32 slate clubs carry full "
                                           "pre-break history (Bundesliga 8gp, "
                                           "Ligue 1 9gp)"),
                     "http_probe_at_run": probe},
        },
        "staleness_quantification": {
            "method": ("per-club: last snapshot game >= 2026-10-30 (the "
                       "Oct-30..Nov-2 league round present); no league games "
                       "Nov 3-6 (international break, ESPN idle check)"),
            "clubs": STALENESS,
            "totals": {
                "clubs_scope": len(STALENESS),
                "clubs_fully_fresh": len(STALENESS) - len(STALE_CLUBS),
                "clubs_missing_league_games": len(STALE_CLUBS),
                "league_games_missing_total": n_stale_games,
            },
        },
        "method": ("Gamma date-window + tag discovery -> soccer events; "
                   "restricted to the 16 ESPN-verified slate fixtures; ALL "
                   "domestic -> standard 10-variant fixture_variants; full "
                   "odds board both token sides (O/U, BTTS, TT both "
                   "directions, ML, spreads-flagged); CLOB $250 ask-VWAP "
                   "walk; frozen gates; fee-aware net-edge bars"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "5bdae2e3",
                    "selfcheck": "277 passed, 1 skipped (papersim test files, "
                                 "re-run 2026-11-06 ~10:5xZ)",
                    "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
                    "fee_model": ("evaluate_candidate(..., fee_rate="
                                  "FEE_RATE_SPORTS) - exec bar is NET of the "
                                  "Polymarket fee 0.05*p*(1-p) per share at the "
                                  "walked entry price; worst_variant_edge stays "
                                  "GROSS")},
        "gates": dict(gates.GATES, notes=(
            "NET-EDGE BARS: exec>=+5c net of sports fee 0.05*p*(1-p) at the "
            "walked price (8c net if under-risk); domestic worst>=+4c gross; "
            "var<=6c; liq>=5k; fill_250; entry .10-.92; 50-50 haircut acts on "
            "the NET edge; news-concordance at candidate stage; spreads "
            "flagged-only; MW $150 deprioritized")),
        "weekend_budget": {
            "bankroll_usd": 13409.00, "cash_usd": 11923.00,
            "weekend_cap_all_agents_usd": 1500.00,
            "this_subscan_max_positions": 3, "stake_per_position_usd": 250,
            "mw_stake_usd": 150,
            "held_positions_on_slate": [],
            "note": ("no held soccer position on any of the 16 fixtures "
                     "(#62 alaves-sevilla kicks Nov-6 20:00Z, outside slate)")},
        "fixtures": fixtures, "matches": matches,
        "board_rows": len(board), "board": board,
        "unparsed_questions": sorted(set(unparsed_qs)),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nboard rows:", len(board), "matches:", len(matches), flush=True)
    print("saved", OUT, flush=True)

    pass_rows = [r for r in board if r["passed_numeric"] and r["policy_eligible"]]
    print("\nnumeric passers (eligible kinds):", len(pass_rows))
    for r in pass_rows[:30]:
        print("  PASS %-40s %-11s %-9s line=%-4s net=+%5.1fc worst=+%5.1fc "
              "var=%5.2fc liq=$%6.0f ask=%s p_med=%.3f stake=$%d %s" % (
                  r["match"][:40], r["kind"], r["side"], r["line"],
                  100 * (r["exec_edge_haircut"] or 0),
                  100 * (r["worst_variant_edge"] or 0),
                  100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
                  r["exec_ask_vwap250"], r["p_med"], r["stake_usd"],
                  ";".join(r["entry_flags"])[:60]))

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
