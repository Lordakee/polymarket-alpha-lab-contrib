"""Round-36 SOCCER scan (paper-only). Friday domestic openers (Nov-6) FEE-AWARE scan.

Window (task brief): entry Nov-5 23:00Z .. Nov-6 23:00Z. All six Friday
league openers kick Nov-6 19:30/19:45/20:00Z -> IN window at ~20h ahead
of kickoff at scan time (~23:5xZ Nov-5). These are the FIRST domestic
league games after the November international break.

Six fixtures (ESPN verified 2026-11-05 ~23:30Z):
  EPL          Everton vs Coventry City        20:00Z
  Championship Derby County vs Bolton Wdrs    20:00Z
  Serie A      Venezia vs Udinese              19:45Z
  La Liga      Sevilla vs Alaves               20:00Z
  Bundesliga   Hamburger SV vs B. Gladbach     19:30Z
  Ligue 1      Toulouse vs Strasbourg          19:45Z

All DOMESTIC same-league pairs -> standard 10-variant path, bridge not
needed (kappa loaded for provenance only). r35 held positions #59
(Lev-OM BTTS) and #60 (Boro-Wrexham U3.5) are settled; no open paper
position on any Friday fixture -> no held overlay this round.

FEE-AWARE GATES (library 76934762): evaluate_candidate(fee_rate=
FEE_RATE_SPORTS=0.05) charges 0.05*p*(1-p) per share at the walked
entry; frozen +5c exec bar (+8c under-risk) is NET of fees; haircut
acts on the NET edge; worst_variant_edge stays gross.

xG staleness (Understat still down, "We will come back soon"): Big-5
base = understat_latest.json (round25 pointer, league results through
Oct-31). Nov-1/2 league round absent for clubs that played then; six
of the twelve clubs are missing exactly one league game (quantified in
STALENESS below). Championship FotMob snapshot fresh through Nov-3.
Selfcheck re-run this session: 277 passed, 1 skipped.
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
OUTDIR = f"{HOME}/round36/raw"
OUT = f"{OUTDIR}/soccer_scan.json"
LO = "2026-11-05T23:00:00Z"
HI = "2026-11-06T23:00:00Z"
DISC_LO = "2026-11-05T23:00:00Z"   # from window open
DISC_HI = "2026-11-07T06:00:00Z"   # Friday slate + early Sat inventory
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")

ESPN_LEAGUES = {  # code -> (label, understat league)
    "eng.1": "EPL", "eng.2": "Championship", "ita.1": "Serie_A",
    "esp.1": "La_liga", "ger.1": "Bundesliga", "fra.1": "Ligue_1",
}

# No open paper positions on any Friday fixture (r35 #59/#60 settled).
HELD_POSITIONS = {}

# Per-club xG staleness (verified vs ESPN results Oct-25..Nov-5):
# games played AFTER the club's last game inside the xG snapshot.
STALENESS = {
    "Everton": {"missing": 1, "detail": "Nov-2 Newcastle 0-1 Everton (A, W) not in model",
                "bias": "model slightly UNDERRATES Everton (missing away win at Newcastle)"},
    "Coventry": {"missing": 0, "detail": "last snap game Oct-31 (3-1 v Sunderland)", "bias": "none"},
    "Derby County": {"missing": 0, "detail": "FotMob fresh through Nov-3 (0-4 v Norwich in)", "bias": "none"},
    "Bolton Wanderers": {"missing": 0, "detail": "FotMob fresh through Nov-3 (1-0 at Charlton in)", "bias": "none"},
    "Venezia": {"missing": 1, "detail": "Nov-1 Como 1-0 Venezia (A, L) not in model",
                "bias": "model slightly OVERRATES Venezia (n=9 only)"},
    "Udinese": {"missing": 0, "detail": "last snap game Oct-31 (2-5 v Roma)", "bias": "none"},
    "Sevilla": {"missing": 1, "detail": "Nov-1 Getafe 3-1 Sevilla (A, L) not in model",
                "bias": "model slightly OVERRATES Sevilla (missing defeat; last-in-snap was 2-0 W)"},
    "Alaves": {"missing": 0, "detail": "last snap game Oct-31 (1-6 L)", "bias": "none"},
    "Hamburger SV": {"missing": 1, "detail": "Nov-1 Frankfurt 3-1 HSV (A, L) not in model",
                     "bias": "model slightly OVERRATES Hamburg (n=7 only)"},
    "Borussia M.Gladbach": {"missing": 0, "detail": "last snap game Oct-31 (0-0 v Paderborn)", "bias": "none"},
    "Toulouse": {"missing": 1, "detail": "Nov-1 Marseille 2-0 Toulouse (A, L) not in model",
                 "bias": "model slightly OVERRATES Toulouse"},
    "Strasbourg": {"missing": 1, "detail": "Nov-1 Strasbourg 5-1 Auxerre (H, W) not in model",
                   "bias": "model UNDERRATES Strasbourg attack (5-goal win missing; n=8 only)"},
}
STALE_CLUBS = {t for t, s in STALENESS.items() if s["missing"]}

TEAM_ALIASES = {
    "sevilla fc": "Sevilla", "sevilla": "Sevilla",
    "deportivo alaves": "Alaves", "alaves": "Alaves",
    "cd alaves": "Alaves", "alaves ": "Alaves",
    "everton fc": "Everton", "everton": "Everton",
    "coventry city fc": "Coventry", "coventry city": "Coventry", "coventry": "Coventry",
    "derby county fc": "Derby County", "derby county": "Derby County", "derby": "Derby County",
    "bolton wanderers fc": "Bolton Wanderers", "bolton wanderers": "Bolton Wanderers",
    "bolton": "Bolton Wanderers",
    "venezia fc": "Venezia", "venezia": "Venezia",
    "udinese calcio": "Udinese", "udinese": "Udinese",
    "hamburger sv": "Hamburger SV", "hamburg": "Hamburger SV", "hsv": "Hamburger SV",
    "borussia monchengladbach": "Borussia M.Gladbach",
    "borussia monchengladbach ": "Borussia M.Gladbach",
    "monchengladbach": "Borussia M.Gladbach",
    "borussia m gladbach": "Borussia M.Gladbach",
    "borussia m. gladbach": "Borussia M.Gladbach",
    "b. monchengladbach": "Borussia M.Gladbach",
    "gladbach": "Borussia M.Gladbach",
    "borussia vlsi monchengladbach": "Borussia M.Gladbach",
    "borussia gladbach": "Borussia M.Gladbach", "gladbach": "Borussia M.Gladbach",
    "b monchengladbach": "Borussia M.Gladbach",
    "toulouse fc": "Toulouse", "toulouse": "Toulouse",
    "rc strasbourg alsace": "Strasbourg", "strasbourg": "Strasbourg",
    # retained from r35 for any other in-range discovery hits
    "bayer 04 leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "olympique de marseille": "Marseille", "marseille": "Marseille",
    "real sociedad de futbol": "Real Sociedad", "real sociedad": "Real Sociedad",
    "olympique lyonnais": "Lyon", "lyon": "Lyon",
    "getafe cf": "Getafe", "getafe": "Getafe",
    "brighton hove albion": "Brighton", "brighton and hove albion": "Brighton",
    "crystal palace fc": "Crystal Palace", "crystal palace": "Crystal Palace",
    "tsg 1899 hoffenheim": "Hoffenheim", "hoffenheim": "Hoffenheim",
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
        if t in ("epl", "laliga", "serie-a", "ligue-1", "bundesliga"):
            return "BIG5-DOMESTIC"
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
    if kick < "2026-11-06T00:00:00Z":
        return "fri_nov6_early (rare; any leftover Thu/post-window)"
    if kick <= "2026-11-06T19:29:59Z":
        return "fri_nov6_pre_prime"
    if kick <= "2026-11-06T23:00:00Z":
        return "fri_nov6_prime (19:30/19:45/20:00Z openers; IN window)"
    return "post_window (inventory only)"


def scan_policy(kind, cross):
    if kind == "spread":
        return ("FLAGGED_ONLY", False,
                "spreads flagged-only (blowout-tail rule): counted, never entered")
    if kind == "ml":
        return ("ELIGIBLE-DEPRIORITIZED", True,
                "domestic MW eligible-deprioritized ($150); Championship 1X2 "
                "limitation (WP-P3 gate E) documented")
    return ("ELIGIBLE", True, "allowed kind under tightened gates")


def espn_fixtures():
    out = {}
    for code, label in ESPN_LEAGUES.items():
        try:
            d = get(f"{ESPN}/{code}/scoreboard?dates=20261106")
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
            out[label] = evs
        except Exception as e:  # noqa: BLE001
            out[label] = {"error": repr(e)}
    return out


def main():
    now = datetime.now(timezone.utc)
    print("UTC now:", now.isoformat(), flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    espn = espn_fixtures()
    json.dump(espn, open(f"{OUTDIR}/espn_fixtures_20261106.json", "w"), indent=1)
    print("\nESPN FRIDAY OPENERS (2026-11-06):", flush=True)
    for lg, evs in espn.items():
        for ev in (evs if isinstance(evs, list) else []):
            th = ev["teams"].get("home", {}).get("name")
            ta = ev["teams"].get("away", {}).get("name")
            print("  %-13s %-24s vs %-24s %s @ %s" % (
                lg, str(th), str(ta), ev.get("date"), ev.get("venue")), flush=True)

    # ---- bridge (provenance only; all pairs domestic this round) ----
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)
    print("\nBRIDGE LOADED (provenance only; no cross pairs this round):",
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
        ("tag-laliga", "volume24hr", {"tag_slug": "laliga"}),
        ("tag-serie-a", "volume24hr", {"tag_slug": "serie-a"}),
        ("tag-ligue-1", "volume24hr", {"tag_slug": "ligue-1"}),
        ("tag-bundesliga", "volume24hr", {"tag_slug": "bundesliga"}),
    ]
    seen = fetch_window(DISC_LO, DISC_HI, sweeps)
    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(f"{OUTDIR}/events_window_36.json", "w"), indent=1)
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
        if f["comp"] in ("ENG2", "BIG5-DOMESTIC", "CROSS(other)") or (
                f["understat_home"] and f["understat_away"]):
            print("%-14s %-16s %-30s vs %-30s kick=%s class=%s" % (
                f["comp"], f["section"][:16], str(f["understat_home"]),
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
            if fx["comp"] not in ("ENG2", "BIG5-DOMESTIC"):
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
                      else "library fixture_variants 10 sweeps, domestic")
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
                            "STALE-XG: %s (1 league game missing each, Nov-1/2 "
                            "round; see staleness block)" % ", ".join(stale_here))
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
                     and f["comp"] in ("ENG2", "BIG5-DOMESTIC")]

    n_stale_games = sum(s["missing"] for s in STALENESS.values())
    n_snap_games = 8 + 9 + 14 + 14 + 10 + 9 + 10 + 11 + 7 + 8 + 8 + 8  # 12-club snapshot games
    out = {
        "scan": "soccer", "round": 36,
        "sub_scan": ("FRIDAY DOMESTIC OPENERS post-international-break "
                     "FEE-AWARE scan; entry window Nov-5 23:00Z..Nov-6 "
                     "23:00Z; six league openers kick Nov-6 19:30/19:45/20:00Z "
                     "(~20h pre-kick at scan); ALL DOMESTIC pairs -> standard "
                     "10-variant path, bridge not needed; no held overlay "
                     "(#59/#60 settled)"),
        "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("entry-placement window (brief); all six Friday "
                                "kickoffs INSIDE the window; entries placed at "
                                "scan time (~23:5xZ Nov-5) are ~20h pre-kickoff; "
                                "XIs drop ~18:30-19:00Z Nov-6; news-concordance "
                                "re-check before entry")},
        "discovery_range_utc": {"lo": DISC_LO, "hi": DISC_HI},
        "espn_fixture_source": {"fetched_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
            "raw": "round36/raw/espn_fixtures_20261106.json",
            "endpoints": {c: f"{ESPN}/{c}/scoreboard?dates=20261106"
                          for c in ESPN_LEAGUES}},
        "bridge": {
            "kappa_path": KAPPA_PATH,
            "loaded_via": "league_strength.load_kappa_report (provenance only)",
            "kappa": {k: round(v, 6) for k, v in kappa.items()},
            "note": "no cross-league pair in this slate; bridge not exercised",
        },
        "xg_bases": {
            "big5": {"path": understat_pointer.get("target"),
                     "pointer": UNDERSTAT_POINTER,
                     "pointer_sha256": understat_pointer.get("sha256"),
                     "fresh_through_utc": "2026-10-31 (league results; Nov-1/2 round absent)",
                     "http_probe_at_run": probe},
            "championship": {"path": FOTMOB,
                             "fresh_through_utc": "2026-11-03",
                             "validation": "WP-P3 gate D walk-forward PASS (O/U, BTTS, TT)"},
            "championship_1x2_limitation": ("gate E failure: relegated-EPL "
                                            "fallback clubs distort 1X2; O/U/"
                                            "BTTS/TT unaffected"),
        },
        "staleness_quantification": {
            "method": ("per-club: ESPN results Oct-25..Nov-5 vs club history "
                       "inside xG snapshot; missing = league games played "
                       "after the club's last snapshot game"),
            "clubs": STALENESS,
            "totals": {
                "clubs_scope": 12,
                "clubs_fully_fresh": 6,
                "clubs_missing_1_league_game": 6,
                "league_games_missing_total": n_stale_games,
                "snapshot_games_in_scope": n_snap_games,
                "pooled_missing_share": round(n_stale_games / n_snap_games, 4),
                "per_affected_club_share": "1 of 7-11 games = 9-14% of that club's sample",
                "directional": ("missing results bias: model OVERRATES Venezia, "
                                "Sevilla, Hamburg, Toulouse (missing defeats) and "
                                "UNDERRATES Everton (missing W at Newcastle) and "
                                "Strasbourg (missing 5-1 W). Toulouse-Strasbourg "
                                "is the only fixture with BOTH clubs stale."),
                "irreducible": ("international-break fortnight means no league "
                                "xG for ANY club Nov-2..5; snapshot staleness "
                                "adds at most 1 extra missing game per affected "
                                "club on top of that shared gap"),
            },
        },
        "method": ("Gamma date-window + tag discovery -> soccer events; "
                   "ALL six fixtures domestic -> standard 10-variant "
                   "fixture_variants (no bridge); Championship pair on FotMob "
                   "snapshot (WP-P3; MW $150 1X2-limited); full odds board "
                   "both token sides; CLOB $250 ask-VWAP walk; frozen gates; "
                   "fee-aware net-edge bars (r35 fee model)"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "76934762",
                    "selfcheck": "277 passed, 1 skipped (papersim test files, "
                                 "re-run 2026-11-05 ~23:30Z this session)",
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
        "max_new_positions": 2, "stake_per_position_usd": 250,
        "bankroll_usd": 13409.00, "cash_usd": 11923.00,
        "open_positions": 3,
        "open_positions_note": ("per coordinator brief bankroll/cash; r35 soccer "
                                "positions #59 (Lev-OM BTTS) and #60 (Boro-"
                                "Wrexham U3.5) settled; no open paper position "
                                "on any of the six Friday fixtures"),
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
    for r in pass_rows[:25]:
        print("  PASS %-40s %-11s %-9s line=%-4s net=+%5.1fc worst=+%5.1fc "
              "var=%5.2fc liq=$%6.0f ask=%s p_med=%.3f stake=$%d %s" % (
                  r["match"][:40], r["kind"], r["side"], r["line"],
                  100 * (r["exec_edge_haircut"] or 0),
                  100 * (r["worst_variant_edge"] or 0),
                  100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
                  r["exec_ask_vwap250"], r["p_med"], r["stake_usd"],
                  ";".join(r["entry_flags"])[:80]))

    print("\nTOP-25 by haircut net edge:")
    for r in board[:25]:
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
