"""Round-30 SOCCER sub-scan: UCL MD4 WEDNESDAY slate (paper-only).

Entry window (brief): 2026-11-03T16:00Z .. 2026-11-04T16:00Z. The 9
Wednesday UCL MD4 fixtures kick off Nov-4 17:45/20:00Z, i.e. AFTER the
window close: an entry placed at scan time (~Nov-3 16:00Z) is ~26h
pre-kickoff and the position settles after the window ends. The window
bounds ENTRY placement, not settlement; every Wednesday row is flagged
entry_timing="post-window-close kickoff (entry now, ~26h early)" and the
fragility (lineup news still evolving, books thin) is carried into the
candidate stage.

Also in scope (task 1): Tuesday UCL MD4 evening games still inside the
entry window (round-29 subjects at 17:45/20:00Z Nov-3 -> fresh-book
recheck ~2-4h pre-kick), plus UEL Wednesday (if any game events exist),
Copa del Rey R1 continuations, EFL Trophy, MLS playoffs. MLS / EFL
Trophy / non-Big-5 pairs are NOT-MODELABLE report-only (Understat
snapshot covers Big-5 only); an MLS tag guard blocks canon
false-positives (e.g. 'Inter Miami' -> 'Inter').

DEGRADED MODE (owner-approved lineage): Understat upstream still
unreachable as of 15:30:13Z (cron status refresh_failed, curl 28 to
understat.com:443; cron every 30min owns recovery) -> xG base is the
round-25 fallback snapshot, fresh through Sat Oct-31. Verified at run
time: no round28/raw/xg_understat_28.json exists; a read-only HTTP probe
is recorded (no snapshot written by this scan).

Cross-league policy (FIXES.md 5-6 + task brief, unchanged from r29):
- match_winner (1X2/ML) and spreads on cross-league fixtures: BANNED.
- O/U, BTTS, team totals on cross-league fixtures: ALLOWED via the r7/r8
  bespoke totals path: bh=(bh1+bh2)/2, ba=(ba1+ba2)/2 (prior-season league
  bases averaged), each team's attack/defense multipliers vs OWN league,
  library SWEEPS (10) x 3 European boost variants (0/.10/.20) = 30
  variants. DOUBLE SCRUTINY: worst-variant >= +5c (vs domestic +4c).
- r29 lesson carried: this 30-variant grid produces 15-38c structural
  variant spreads; var<=6c co-gate therefore rejects most cross-league
  rows by construction.
- Domestic (same-league) pairs: canonical library fixture_variants (10
  variants), domestic bars. None expected in this UCL window.

Full board: every Polymarket full-match market per modelable fixture,
BOTH token sides, live CLOB best bid/ask + $250 ask-VWAP walk, frozen
gate set (var<=6c, worst bar, exec>=+5c after 50-50 haircut, liq>=5k,
fill_250, entry .10-.92, under-risk 8c screen; news at candidate stage).

Library: polymarket_alpha_lab.papersim @ 7b6cdd47, selfcheck 10/10 PASS
(re-run this session before this script).
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
from polymarket_alpha_lab.papersim import gates, soccer_model, xg  # noqa: E402

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
R28_SNAP = "/home/ubuntu/paper-sim/round28/raw/xg_understat_28.json"
R25 = "/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json"
CRON_STATUS = "/home/ubuntu/paper-sim/round28/raw/understat_recovery_status.json"
XG_PATH = R28_SNAP if os.path.exists(R28_SNAP) else R25
R28_PUBLISHED = os.path.exists(R28_SNAP)
cron_state = json.load(open(CRON_STATUS)) if os.path.exists(CRON_STATUS) else None

OUT = "/home/ubuntu/paper-sim/round30/raw/soccer_scan.json"
BOARD_OUT = "/home/ubuntu/paper-sim/round30/raw/odds_board_30.json"
EVENTS_OUT = "/home/ubuntu/paper-sim/round30/raw/events_window_30.json"

# entry window (brief) and discovery range (Wednesday slate + late-Wed US)
LO = "2026-11-03T16:00:00Z"
HI = "2026-11-04T16:00:00Z"
DISC_LO = LO
DISC_HI = "2026-11-05T09:00:00Z"

BIG5 = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]

COMP_OF_TAG = {
    "ucl": "UCL", "champions-league": "UCL", "uefa-champions-league": "UCL",
    "champions-league-2026": "UCL", "uefa-champions-league-2026": "UCL",
    "europa-league": "UEL", "uel": "UEL", "uefa-europa-league": "UEL",
    "europa-league-2026": "UEL", "uefa-europa-league-2026": "UEL",
    "conference-league": "UECL", "uecl": "UECL",
    "efl-cup": "EFL_CUP", "carabao-cup": "EFL_CUP", "carabao": "EFL_CUP",
    "copa-del-rey": "COPA", "copa-del-rey-2026": "COPA",
    "coupe-de-france": "CDF", "dfb-pokal": "DFB",
    "mls": "MLS", "mls-cup": "MLS", "mls-playoffs": "MLS",
    "efl-trophy": "EFL_TROPHY", "english-football-league-trophy": "EFL_TROPHY",
    "epl": "EPL_DOM", "premier-league": "EPL_DOM",
    "la-liga": "LIGA_DOM", "laliga": "LIGA_DOM",
    "serie-a": "SERIEA_DOM", "sea": "SERIEA_DOM",
    "ligue-1": "LIGUE1_DOM", "bundesliga": "BUNDES_DOM",
}
UCL_UEL_TAGS = {"ucl", "champions-league", "uefa-champions-league",
                "europa-league", "uel", "uefa-europa-league"}
CUP_TAGS = {"efl-cup", "carabao-cup", "carabao", "copa-del-rey",
            "coupe-de-france", "dfb-pokal", "efl-trophy",
            "english-football-league-trophy"}
# competitions whose clubs are outside the Big-5 Understat universe by
# construction: force not-modelable (canon false-positive guard)
NON_BIG5_COMP_TAGS = {"mls", "mls-cup", "mls-playoffs", "efl-trophy",
                      "english-football-league-trophy"}

TEAM_ALIASES = {
    "bayern munich": "Bayern Munich",
    "bayern": "Bayern Munich", "fc bayern munique": "Bayern Munich",
    "bayern munique": "Bayern Munich", "bayern munchen": "Bayern Munich",
    "fc bayern munchen": "Bayern Munich",
    "borussia monchengladbach": "Borussia M.Gladbach",
    "borussia mgladbach": "Borussia M.Gladbach",
    "atletico madrid": "Atletico Madrid", "atletico": "Atletico Madrid",
    "club atletico de madrid": "Atletico Madrid",
    "aston villa": "Aston Villa",
    "barcelona": "Barcelona", "fc barcelona": "Barcelona",
    "inter milan": "Inter", "internazionale": "Inter", "inter": "Inter",
    "fc internazionale milano": "Inter",
    "stuttgart": "VfB Stuttgart", "vfb stuttgart": "VfB Stuttgart",
    "lille": "Lille", "losc lille": "Lille", "losc": "Lille",
    "bayer leverkusen": "Bayer Leverkusen", "leverkusen": "Bayer Leverkusen",
    "rb leipzig": "RasenBallsport Leipzig", "leipzig": "RasenBallsport Leipzig",
    "rasenballsport leipzig": "RasenBallsport Leipzig",
    "manchester city": "Manchester City", "man city": "Manchester City",
    "manchester united": "Manchester United", "man united": "Manchester United",
    "psg": "Paris Saint Germain", "paris saint germain": "Paris Saint Germain",
    "paris sg": "Paris Saint Germain", "paris-saint-germain": "Paris Saint Germain",
    "ac milan": "AC Milan", "milan": "AC Milan",
    "real madrid": "Real Madrid", "real": "Real Madrid",
    "borussia dortmund": "Borussia Dortmund", "dortmund": "Borussia Dortmund",
    "as monaco": "Monaco", "monaco": "Monaco",
    "olympique lyonnais": "Lyon", "lyon": "Lyon",
    "olympique marseille": "Marseille", "marseille": "Marseille",
    "atalanta bc": "Atalanta", "atalanta": "Atalanta",
    "bologna": "Bologna", "fc bologna": "Bologna",
    "brentford": "Brentford", "brighton": "Brighton",
    "crystal palace": "Crystal Palace", "everton": "Everton", "fulham": "Fulham",
    "tottenham hotspur": "Tottenham", "tottenham": "Tottenham",
    "nottingham forest": "Nottingham Forest", "newcastle united": "Newcastle United",
    "newcastle": "Newcastle United",
    "villarreal": "Villarreal",
    "real betis": "Real Betis", "betis": "Real Betis",
    "real sociedad": "Real Sociedad", "sevilla": "Sevilla",
    "athletic bilbao": "Athletic Club", "athletic club": "Athletic Club",
    "celta vigo": "Celta Vigo", "celta": "Celta Vigo",
    "eintracht frankfurt": "Eintracht Frankfurt",
    "parma calcio 1913": "Parma Calcio 1913", "parma": "Parma Calcio 1913",
    "us sassuolo calcio": "Sassuolo", "sassuolo": "Sassuolo",
    "acf fiorentina": "Fiorentina", "fiorentina": "Fiorentina",
    "rc deportivo a coruna": "Deportivo La Coruna",
    "deportivo la coruna": "Deportivo La Coruna",
    "stade brestois 29": "Brest", "stade brestois": "Brest",
    "paris fc": "Paris FC", "roma": "Roma", "as roma": "Roma",
    "como": "Como", "como 1907": "Como",
    "lens": "Lens", "racing club de lens": "Lens", "rc lens": "Lens",
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
        "ballspielverein", "rasenballsport", "borussia", "eintracht", "bayer"}]
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


# ---------- team canon (cross-league: against ALL Big-5 titles) ----------
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
    for t in tset & NON_BIG5_COMP_TAGS:
        return COMP_OF_TAG[t]
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


# ---------- cross-league r7/r8 totals path on library primitives ----------
def cross_league_variants(snapshot, home, lgh, away, lga):
    variants = []
    for spec in soccer_model.SWEEPS:
        lw = 0.0 if spec.last_weight is None else spec.last_weight
        pg = 0.0 if spec.prior_games is None else spec.prior_games
        r1 = xg.ratings_for(snapshot, lgh, "2026",
                             last_weight=lw, prior_games=pg, mode=spec.mode)
        r2 = xg.ratings_for(snapshot, lga, "2026",
                             last_weight=lw, prior_games=pg, mode=spec.mode)
        if home not in r1.teams or away not in r2.teams:
            return None
        bh = (r1.goal_fit.home_rate + r2.goal_fit.home_rate) / 2.0
        ba = (r1.goal_fit.away_rate + r2.goal_fit.away_rate) / 2.0
        ah, dh = r1.teams[home]
        aa, da = r2.teams[away]
        for boost in (0.0, 0.10, 0.20):
            lh = bh * (ah ** spec.shrink) * (da ** spec.shrink) * (1.0 + boost)
            la = ba * (aa ** spec.shrink) * (dh ** spec.shrink) * (1.0 + boost)
            outputs = soccer_model.variant_outputs(lh, la, rho=spec.rho)
            variants.append({"spec": spec.name, "boost": boost,
                             "lambdas": (lh, la), "outputs": outputs})
    return variants or None


def variant_med(vs, fn):
    return soccer_model.median([fn(v) for v in vs])


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
    """Read-only HTTP probe (cron owns recovery; this scan writes nothing)."""
    try:
        r = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{time_total}s",
             "--max-time", "12", "https://understat.com/league/EPL/2026"],
            capture_output=True, text=True, timeout=20)
        return {"ok": r.returncode == 0 and r.stdout[:3] == "200",
                "detail": (r.stdout or r.stderr).strip()[:120]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": repr(e)[:120]}


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

    # ---- discovery over [entry-lo, disc-hi] ----
    sweeps = [
        ("date-volume", "volume24hr", {"start_date_min": DISC_LO,
                                       "start_date_max": DISC_HI}),
        ("date-liquidity", "liquidity", {"start_date_min": DISC_LO,
                                         "start_date_max": DISC_HI}),
        ("tag-ucl", "volume24hr", {"tag_slug": "ucl"}),
        ("tag-champions", "volume24hr", {"tag_slug": "champions-league"}),
        ("tag-uefa-cl", "volume24hr", {"tag_slug": "uefa-champions-league"}),
        ("tag-europa", "volume24hr", {"tag_slug": "europa-league"}),
        ("tag-uel", "volume24hr", {"tag_slug": "uel"}),
        ("tag-efl-cup", "volume24hr", {"tag_slug": "efl-cup"}),
        ("tag-carabao", "volume24hr", {"tag_slug": "carabao-cup"}),
        ("tag-copa", "volume24hr", {"tag_slug": "copa-del-rey"}),
        ("tag-cdf", "volume24hr", {"tag_slug": "coupe-de-france"}),
        ("tag-dfb", "volume24hr", {"tag_slug": "dfb-pokal"}),
        ("tag-mls", "volume24hr", {"tag_slug": "mls"}),
        ("tag-efl-trophy", "volume24hr", {"tag_slug": "efl-trophy"}),
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

    # ---- classify fixtures ----
    fixtures = []
    for e in events:
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        home_raw = parts[0].strip() if parts else ""
        away_raw = parts[1].strip() if len(parts) > 1 else ""
        non_big5_comp = bool(set(e["tags"]) & NON_BIG5_COMP_TAGS)
        home = None if non_big5_comp else canon_team(home_raw)
        away = None if non_big5_comp else canon_team(away_raw)
        lgh = TITLE_LEAGUE.get(home) if home else None
        lga = TITLE_LEAGUE.get(away) if away else None
        comp = comp_of(e["tags"], lgh, lga)
        kick = e["kick"]
        if kick <= "2026-11-04T16:00:00Z":
            in_entry = True
        else:
            in_entry = False
        if kick < "2026-11-04T00:00:00Z":
            section = "tue_nov3_in_window (r29 subjects, fresh-book recheck)"
        elif kick <= "2026-11-04T16:00:00Z":
            section = "wed_in_window"
        elif kick <= "2026-11-04T23:59:59Z":
            section = "WEDNESDAY PRIMARY SLATE (kickoff after window close; entry now ~26h pre-kick)"
        else:
            section = "late_wed_other (MLS/cups, post-window)"
        fixtures.append({
            "event_id": e["id"], "title": e["title"], "kickoff_utc": kick,
            "comp": comp, "tags": e["tags"],
            "section": section, "in_entry_window": in_entry,
            "modelable": bool(home and away),
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
    for f in base_fixtures.values():
        print("%-12s %-28s %-24s vs %-24s kick=%s modelable=%s" % (
            f["comp"], f["section"][:12], str(f["understat_home"]),
            str(f["understat_away"]), f["kickoff_utc"], f["modelable"]),
            flush=True)

    # ---- model + books + gates ----
    matches = []
    board = []
    unparsed_qs = []
    groups = {}
    for fx, e in zip(fixtures, events):
        if not fx["modelable"]:
            continue
        key = (fx["understat_home"], fx["understat_away"], fx["kickoff_utc"])
        groups.setdefault(key, {"fx": fx, "events": []})["events"].append(e)

    for key in sorted(groups, key=lambda k: groups[k]["fx"]["kickoff_utc"]):
        grp = groups[key]
        fx = grp["fx"]
        e0 = min(grp["events"], key=lambda e: len(e.get("title") or ""))
        base_title = re.split(r"\s+-\s+", e0.get("title") or "", maxsplit=1)[0]
        home, away = fx["understat_home"], fx["understat_away"]
        lgh, lga = fx["home_league"], fx["away_league"]
        cross = lgh != lga
        if cross:
            variants = cross_league_variants(snapshot, home, lgh, away, lga)
            method = ("cross-league r7/r8 totals path (library SWEEPS x 3 "
                      "boosts, n=%d); MW/spread BANNED cross-league"
                      % (len(variants) or 0))
        else:
            variants = soccer_model.fixture_variants(snapshot, home, lgh, away, lgh)
            method = "library fixture_variants (10 sweeps, domestic)"
        if variants is None:
            fx["modelable"] = False
            fx["model_note"] = "variants returned None"
            continue
        vs = [{"lambdas": (v.lambdas[0], v.lambdas[1]),
               "outputs": v.outputs,
               "spec": getattr(v.spec, "name", "?"), "boost": None}
              for v in variants] if not cross else variants
        lam_h = soccer_model.median([v["lambdas"][0] for v in vs])
        lam_a = soccer_model.median([v["lambdas"][1] for v in vs])
        p1x2 = {
            "H": variant_med(vs, lambda v: v["outputs"].home_win),
            "D": variant_med(vs, lambda v: v["outputs"].draw),
            "A": variant_med(vs, lambda v: v["outputs"].away_win),
        }
        form_h = xg.recent_form(snapshot, home)
        form_a = xg.recent_form(snapshot, away)
        fkey = fixture_key(home, away)
        matches.append({
            "match": base_title, "comp": fx["comp"], "cross_league": cross,
            "section": fx["section"], "in_entry_window": fx["in_entry_window"],
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
                        "section": fx["section"],
                        "in_entry_window": fx["in_entry_window"],
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
                    flags = []
                    if cross and kind in ("ml", "spread"):
                        flags.append("BANNED-CROSS-LEAGUE-MW/spread (FIXES 5-6)")
                    if not cross and kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if not cross and kind == "ml":
                        flags.append("MATCH-WINNER domestic: eligible-but-deprioritized")
                    if row["passed_numeric"] and not flags:
                        flags.append("NUMERIC-PASS (pending news-concordance)")
                    if not fx["in_entry_window"]:
                        flags.append(
                            "ENTRY-TIMING: kickoff after window close; entry now "
                            "is ~%dh pre-kick (lineups unset, extra fragility)"
                            % max(1, round((
                                datetime.fromisoformat(
                                    fx["kickoff_utc"].replace("Z", "+00:00"))
                                - now).total_seconds() / 3600)))
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
    not_modelable = [f for f in fixtures if not f["modelable"]]
    out = {
        "scan": "soccer", "round": 30,
        "sub_scan": ("UCL MD4 Wednesday slate (round-30 soccer sub-scan); "
                     "entry window Nov-3 16:00Z..Nov-4 16:00Z, Wednesday "
                     "kickoffs settle after window close"),
        "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("entry-placement window (brief); Wednesday "
                                "MD4 kickoffs 17:45/20:00Z Nov-4 fall after "
                                "hi - entries placed at scan time (~Nov-3 "
                                "16:00Z) are ~26h pre-kickoff")},
        "discovery_range_utc": {"lo": DISC_LO, "hi": DISC_HI},
        "degraded_mode": {
            "active": True,
            "reason": ("Understat upstream unreachable (cron every 30min owns "
                       "recovery)"),
            "xg_base": XG_PATH,
            "xg_base_fresh_through_utc": "2026-10-31 (Sat Oct-31 slate)",
            "r28_cron_snapshot_published": R28_PUBLISHED,
            "cron_status_at_run": cron_state,
            "http_probe_at_run": probe,
            "impact_note": ("snapshot club ratings fresh through Oct-31; all "
                            "six modelable clubs (Dortmund, Betis, Lens, Como, "
                            "RB Leipzig, Man City + Tue recheck clubs) last "
                            "played Oct 31-Nov 1 at most; weekend Nov-1 games "
                            "are NOT in the snapshot - noted as model risk"),
        },
        "method": ("Gamma date-window + competition-tag discovery -> soccer "
                   "events; domestic (same-league) pairs via canonical papersim "
                   "fixture_variants (10 sweeps); cross-league Big-5 pairs via "
                   "the r7/r8 bespoke totals path (bh=(bh1+bh2)/2, multipliers "
                   "vs OWN league, library SWEEPS x boosts {0,.1,.2}=30 "
                   "variants); cross-league MW/spread BANNED; MLS/EFL-Trophy/"
                   "non-Big-5 NOT-MODELABLE report-only; full odds board both "
                   "token sides; CLOB $250 ask-VWAP walk; frozen gates + "
                   "cross-league worst>=+5c"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "7b6cdd47", "selfcheck": "10/10 PASS",
                    "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src"},
        "gates": dict(gates.GATES, notes=(
            "cross-league: MW banned, totals allowed, worst>=+5c (double "
            "scrutiny); domestic: worst>=+4c; both: exec>=+5c after 50-50 "
            "haircut, var<=6c, liq>=5k, fill_250, entry .10-.92, under-risk "
            "8c screen; news-concordance at candidate stage")),
        "max_new_positions": 2, "stake_per_position_usd": 250,
        "bankroll_usd": 12841.14, "cash_usd": 10355.49,
        "fixtures": fixtures, "not_modelable": not_modelable,
        "matches": matches, "board_rows": len(board), "board": board,
        "unparsed_questions": sorted(set(unparsed_qs)),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    json.dump({
        "generated_utc": out["generated_utc"], "window_utc": out["window_utc"],
        "matches": matches, "board": board,
        "unparsed_questions": out["unparsed_questions"],
    }, open(BOARD_OUT, "w"), indent=1)
    print("board rows:", len(board), "matches:", len(matches), flush=True)
    print("saved", OUT, "and", BOARD_OUT, flush=True)
    pass_rows = [r for r in board if r["passed_numeric"]]
    print("numeric passers:", len(pass_rows), flush=True)
    for r in pass_rows[:12]:
        print("  PASS %s | %s %s line=%s exec=+%dc worst=+%dc var=%.1fc liq=$%d %s" % (
            r["match"], r["kind"], r["side"], r["line"],
            round(100 * (r["exec_edge_haircut"] or 0)),
            round(100 * (r["worst_variant_edge"] or 0)),
            100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
            ";".join(r["entry_flags"])), flush=True)
    # top-15 board dump for the report
    print("\nTOP-15 by exec_edge:")
    for r in board[:15]:
        print("  %+6.1fc worst %+6.1fc var %5.1fc | %-42s | %s %s %s | p_med %.3f ask %.3f liq $%.0f | %s" % (
            100 * (r["exec_edge"] if r["exec_edge"] is not None else -9),
            100 * (r["worst_variant_edge"] if r["worst_variant_edge"] is not None else -9),
            100 * (r["var_spread"] or 0), r["match"][:42], r["kind"], r["side"],
            r["line"], r["p_med"], r["exec_ask_vwap250"] or 0,
            r["liq_gamma"] or 0, r["section"][:14]), flush=True)


if __name__ == "__main__":
    main()
