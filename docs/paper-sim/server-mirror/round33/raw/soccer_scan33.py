"""Round-33 SOCCER scan: THE THREE-FIRSTS SCAN (paper-only).

Historic firsts exercised in this scan:
  1. WP-P2a league-strength bridge in PRODUCTION: kappa table
     (round31/raw/league_strength_kappa.json, WP-P2b estimation report,
     walk-forward backtest overall_verdict=PASS 2026-11-03) threaded as
     bridge= into soccer_model.fixture_variants for every cross-league
     fixture. The r7/r8 bespoke 30-variant boost path is RETIRED for
     Big-5 pairs (r30/r31 lineage) - bridged 10-variant library path
     replaces it, exactly per FIXES.md 6 ("cross-league modeling requires
     the shared strength-adjusted path").
  2. Cross-league match_winner UNBANNED at the SCAN level (library
     registry still reads BANNED by design): the WP-P2b backtest PASS
     satisfies the FIXES.md 6 suspension-release condition ("until a
     2-3 season UCL/UEL walk-forward backtest passes with a
     league-strength coefficient bridging domestic xG"). Scan-level
     policy: ELIGIBLE-DEPRIORITIZED, $150 marginal sizing, worst>=+5c
     (cross-league margin), T4 accumulation (0/20 settled cross-league
     MW paper bets at scan time; registry flip needs >=20 per T4).
  3. Championship (eng.2) MODELABLE for the first time: WP-P3 FotMob
     adapter snapshot round31/raw/xg_fotmob_championship.json (720
     matches, O/U/BTTS/TT walk-forward gate D PASS 2026-11-03) merged
     into the snapshot universe; Cardiff-West Ham, Wrexham-Middlesbrough,
     Bristol City-Wolves run the standard domestic 10-variant path.
     Known 1X2 limitation (gate E failure from relegation fallback) is
     documented, does NOT block O/U/BTTS/TT.

Window (task brief): entry Nov-4 10:00Z .. Nov-5 10:00Z. UEL Thursday
MD4 evening kickoffs (Nov-5 17:45/20:00Z) fall after window close;
entries placed at scan time (~10:30Z Nov-4) are ~31-34h pre-kick, same
interpretation as r30 (Wednesday UCL) and r31 (Thursday UEL).

xG bases: Big-5 = understat_latest.json POINTER (2026-11-04 codex fix
#11: symlink + sidecar understat_latest_pointer.json, re-pointed by
tools/understat_refresh.py after every successful validation; seeded at
the round25 snapshot, fresh through Sat Oct-31 while Understat upstream
stays cron-owned for recovery -- recovery success now auto-advances the
scanner input); Championship = round31/raw/xg_fotmob_championship.json
(FRESH through Nov-3). Library: polymarket_alpha_lab.papersim @
19501719, selfcheck 10/10 PASS re-run this session before this script.
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
    gates,
    league_strength,
    soccer_model,
    xg,
)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
HOME = "/home/ubuntu/paper-sim"
# 2026-11-04 (codex review #11): the Big-5 xG base resolves through the
# validated-snapshot POINTER, not a hard-coded round path -- recovery
# output must reach the active scanner without a human editing constants.
# NEVER hard-code roundNN/raw/xg_understat_NN.json in a new scan.
UNDERSTAT_LATEST = f"{HOME}/understat_latest.json"
UNDERSTAT_POINTER = f"{HOME}/understat_latest_pointer.json"
FOTMOB = f"{HOME}/round31/raw/xg_fotmob_championship.json"
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"
R30_SCAN = f"{HOME}/round30/raw/soccer_scan.json"
OUTDIR = f"{HOME}/round33/raw"
OUT = f"{OUTDIR}/soccer_scan.json"
LO = "2026-11-04T10:00:00Z"
HI = "2026-11-05T10:00:00Z"
DISC_LO = "2026-11-04T00:00:00Z"   # capture the whole Wednesday slate
DISC_HI = "2026-11-06T06:00:00Z"   # capture UEL Thu evening + early Fri inventory
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")

TEAM_ALIASES = {
    "bv borussia 09 dortmund": "Borussia Dortmund",
    "borussia dortmund": "Borussia Dortmund",
    "dortmund": "Borussia Dortmund",
    "rb leipzig": "RasenBallsport Leipzig",
    "rasenballsport leipzig": "RasenBallsport Leipzig",
    "leipzig": "RasenBallsport Leipzig",
    "racing club de lens": "Lens", "rc lens": "Lens", "lens": "Lens",
    "como 1907": "Como", "como": "Como",
    "real betis balompie": "Real Betis", "real betis": "Real Betis",
    "betis": "Real Betis",
    "manchester city fc": "Manchester City", "manchester city": "Manchester City",
    "man city": "Manchester City",
    "crystal palace fc": "Crystal Palace", "crystal palace": "Crystal Palace",
    "tsg 1899 hoffenheim": "Hoffenheim", "tsg hoffenheim": "Hoffenheim",
    "hoffenheim": "Hoffenheim",
    "real sociedad de futbol": "Real Sociedad", "real sociedad": "Real Sociedad",
    "olympique lyonnais": "Lyon", "ol lyon": "Lyon", "lyon": "Lyon",
    "bayer 04 leverkusen": "Bayer Leverkusen", "bayer leverkusen": "Bayer Leverkusen",
    "leverkusen": "Bayer Leverkusen",
    "olympique de marseille": "Marseille", "marseille": "Marseille",
    "stade rennais fc 1901": "Rennes", "stade rennais": "Rennes",
    "rennes": "Rennes",
    "cardiff": "Cardiff City", "cardiff city": "Cardiff City",
    "west ham": "West Ham United", "west ham united": "West Ham United",
    "wolves": "Wolverhampton Wanderers",
    "wolverhampton wanderers": "Wolverhampton Wanderers",
    "bristol city": "Bristol City",
    "wrexham": "Wrexham", "wrexham afc": "Wrexham",
    "middleborough": "Middlesbrough", "middesbrough": "Middlesbrough",
    "middlessbrough": "Middlesbrough", "middlebrough": "Middlesbrough",
}
# short/ambiguous names that must NEVER resolve by substring
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


# ---------- team canon (Big-5 + Championship titles) ----------
ALL_TITLES = {}
TITLE_LEAGUE = {}


def canon_team(name):
    n = norm_name(name)
    if not n or n in CANON_DENY_EXACT:
        return None
    alias = TEAM_ALIASES.get(str(name).strip().lower()) or TEAM_ALIASES.get(n)
    if alias is not None and alias in TITLE_LEAGUE:
        return alias
    for t in ALL_TITLES:
        if norm_name(t) == n:
            return t
    # substring fallback only for names with enough specificity (>=5 chars)
    if len(n) >= 5:
        for t in ALL_TITLES:
            tn = norm_name(t)
            if tn and (tn in n or n in tn):
                return t
    return None


def comp_of(tags, home_lg, away_lg):
    tset = set(tags)
    for t in tset & {"ucl", "champions-league", "uefa-champions-league"}:
        return "UCL"
    for t in tset & {"uel", "europa-league", "uefa-europa-league"}:
        return "UEL"
    for t in tset & {"uecl", "conference-league", "uefa-conference-league"}:
        return "UECL"
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
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{time_total}s",
             "--max-time", "12", "https://understat.com/league/EPL/2026"],
            capture_output=True, text=True, timeout=20)
        return {"ok": r.returncode == 0 and r.stdout[:3] == "200",
                "detail": (r.stdout or r.stderr).strip()[:120]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": repr(e)[:120]}


def section_of(kick):
    if kick < "2026-11-04T17:00:00Z":
        return "wed_nov4_early (UEL 15:30Z in window)"
    if kick < "2026-11-05T00:00:00Z":
        return "wed_nov4_prime (UCL MD4 17:45/20:00Z + Championship 19:45/20:00Z; in window)"
    if kick <= HI:
        return "thu_nov5_morning_in_window"
    return "thu_nov5_evening_post_window (UEL MD4 17:45/20:00Z; enterable NOW ~31-34h pre-kick, r30/r31 interpretation)"


def scan_policy(kind, cross):
    """Scan-level policy overlay (documented, does NOT touch the library).

    Library suspension_policy still returns BANNED for cross-league MW -
    the registry flip needs T4 (>=20 settled cross-league MW paper bets).
    The WP-P2b backtest PASS satisfies the FIXES.md 6 release condition,
    so the SCAN treats cross-league MW as eligible-deprioritized at $150
    marginal sizing while the T4 sample accumulates.
    """
    if kind == "spread":
        return ("FLAGGED_ONLY", False,
                "spreads flagged-only (blowout-tail rule): counted, never entered")
    if kind == "ml":
        if cross:
            return ("ELIGIBLE-DEPRIORITIZED", True,
                    "cross-league MW scan-level unban: WP-P2b walk-forward PASS "
                    "(overall PASS, T1 p=0.026) satisfies FIXES.md-6 release "
                    "condition; $150 marginal sizing; worst>=+5c; T4 accumulation "
                    "0/20 settled; library registry still BANNED pending T4")
        return ("ELIGIBLE-DEPRIORITIZED", True,
                "Championship MW eligible-deprioritized; KNOWN 1X2 limitation "
                "(WP-P3 gate E failure: relegated-EPL fallback clubs distort "
                "attack multipliers); $150 marginal sizing")
    return ("ELIGIBLE", True, "allowed kind under tightened gates")


def main():
    now = datetime.now(timezone.utc)
    print("UTC now:", now.isoformat(), flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    # ---- FIRST: load the bridge ----
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)
    print("BRIDGE LOADED:", KAPPA_PATH, flush=True)
    for lg in sorted(kappa):
        print("  kappa[%s] = %+.6f" % (lg, kappa[lg]), flush=True)
    for a, b in (("EPL", "Bundesliga"), ("La_liga", "Ligue_1"),
                 ("Serie_A", "Ligue_1"), ("Bundesliga", "La_liga"),
                 ("EPL", "Serie_A"), ("Ligue_1", "Serie_A"),
                 ("EPL", "La_liga"), ("Bundesliga", "Ligue_1")):
        print("  bridge_factor(%s home vs %s away) = %s" % (
            a, b, league_strength.bridge_factor(kappa, a, b)), flush=True)
    # nuisance probe: any league NOT in the table has no bridge (None)
    print("  bridge_factor(EPL, nuisance) =", league_strength.bridge_factor(kappa, "EPL", "nuisance"),
          "| bridge_factor(EPL, Championship) =",
          league_strength.bridge_factor(kappa, "EPL", "Championship"), flush=True)

    # ---- snapshots ----
    # Big-5 base comes from the validated-snapshot pointer (codex fix #11):
    # read the sidecar for provenance, load through the symlink.
    with open(UNDERSTAT_POINTER, "r", encoding="utf-8") as _ph:
        understat_pointer = json.load(_ph)
    print("understat latest pointer ->", understat_pointer.get("target"),
          "fetched_at", understat_pointer.get("fetched_at_utc"),
          "pointed_at", understat_pointer.get("pointed_at_utc"), flush=True)
    snapshot = dict(xg.load_xg_snapshot(UNDERSTAT_LATEST))
    fot = xg.load_xg_snapshot(FOTMOB) if hasattr(xg, "load_xg_snapshot") else None
    # fotmob snapshot file is already in wire shape; merge blocks
    with open(FOTMOB, "r", encoding="utf-8") as h:
        fot_raw = json.load(h)
    for k, v in fot_raw.items():
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
    for probe_team in ("Cardiff", "West Ham", "Wrexham", "Middlesbrough",
                       "Bristol City", "Wolves", "AZ", "Dortmund", "Lens",
                       "Como", "RB Leipzig", "Betis", "Manchester City",
                       "Crystal Palace", "Hoffenheim", "Real Sociedad",
                       "Lyon", "Leverkusen", "Marseille", "Rennes"):
        print("  canon %-16s -> %s" % (probe_team, canon_team(probe_team)), flush=True)

    probe = understat_probe()
    print("understat probe:", probe, flush=True)

    # ---- discovery ----
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
        ("tag-championship", "volume24hr", {"tag_slug": "championship"}),
        ("tag-efl-champ", "volume24hr", {"tag_slug": "efl-championship"}),
        ("tag-epl", "volume24hr", {"tag_slug": "epl"}),
        ("tag-laliga", "volume24hr", {"tag_slug": "laliga"}),
        ("tag-serie-a", "volume24hr", {"tag_slug": "serie-a"}),
        ("tag-ligue-1", "volume24hr", {"tag_slug": "ligue-1"}),
        ("tag-bundesliga", "volume24hr", {"tag_slug": "bundesliga"}),
        ("tag-brasileirao", "volume24hr", {"tag_slug": "serie-a-brasil"}),
    ]
    seen = fetch_window(DISC_LO, DISC_HI, sweeps)
    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(f"{OUTDIR}/events_window_33.json", "w"), indent=1)
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
        if f["comp"] in ("UCL", "UEL", "UECL", "ENG2") or (f["understat_home"] and f["understat_away"]):
            print("%-5s %-16s %-28s vs %-28s kick=%s class=%s" % (
                f["comp"], f["section"][:16], str(f["understat_home"]),
                str(f["understat_away"]), f["kickoff_utc"],
                f["modelability_class"]), flush=True)

    # ---- r30 baseline for the compression table ----
    r30_board = json.load(open(R30_SCAN))["board"] if os.path.exists(R30_SCAN) else []

    # ---- model + books + gates ----
    matches, board, prices_only, unparsed_qs = [], [], [], []
    groups = {}
    for fx in fixtures:
        key = (fx["understat_home"], fx["understat_away"], fx["kickoff_utc"],
               fx["comp"], re.split(r"\s+-\s+", fx["title"], maxsplit=1)[0])
        groups.setdefault(key, {"fx": fx, "events": []})
    for g in groups.values():
        pass
    for fx, e in zip(fixtures, events):
        key = (fx["understat_home"], fx["understat_away"], fx["kickoff_utc"],
               fx["comp"], re.split(r"\s+-\s+", fx["title"], maxsplit=1)[0])
        groups[key]["events"].append(e)

    for key in sorted(groups, key=lambda k: groups[k]["fx"]["kickoff_utc"]):
        grp = groups[key]
        fx = grp["fx"]
        home, away = fx["understat_home"], fx["understat_away"]
        lgh, lga = fx["home_league"], fx["away_league"]
        cross = bool(lgh and lga and lgh != lga)
        base_title = re.split(r"\s+-\s+", grp["events"][0].get("title") or "",
                              maxsplit=1)[0]

        if not fx["modelable"]:
            # prices-only board (parse-then-fetch keeps call volume bounded)
            if fx["comp"] not in ("UCL", "UEL", "UECL", "ENG2"):
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
                "modelability": ("model-void: %s/%s not in snapshot universe "
                                 "(Big-5 Understat + Championship FotMob); "
                                 "bridge cannot create multipliers for absent "
                                 "clubs; kappa has no %s entry anyway"
                                 % (fx["title"].split(" vs.")[0][:24],
                                    str(away), lga or lgh or "non-Big-5")),
                "rows": prow})
            print("PRICES-ONLY %-34s %-4s kick=%s rows=%d" % (
                base_title, fx["comp"], fx["kickoff_utc"], len(prow)), flush=True)
            continue

        # modelable: bridged cross-league or domestic Championship
        if cross:
            variants = soccer_model.fixture_variants(
                snapshot, home, lgh, away, lga, bridge=kappa)
            method = ("bridged 10-variant library path (WP-P2a kappa bridge, "
                      "fixture_variants bridge=); retired r7/r8 30-variant "
                      "boost path")
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
        fkey = fixture_key(home, away)
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
            "p1x2_note": ("cross-league MW ELIGIBLE-DEPRIORITIZED (scan-level "
                          "unban, WP-P2b PASS; $150; T4 accumulating)" if cross
                          else "domestic MW eligible-deprioritized ($150; 1X2 "
                               "limitation documented)" if lgh == "Championship"
                          else "eligible-but-deprioritized"),
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
                        quote, book["asks"], gamma_liquidity=liq, under_risk=ur)
                    pol, pol_eligible, pol_reason = scan_policy(kind, cross)
                    lib_pol = gates.suspension_policy(kind, cross_league=cross)
                    exit_walk = gates.walk_book(
                        [(p, s) for p, s in book["bids"]], side="bid")
                    # r30 old spread for the compression table
                    r30_match = [r for r in r30_board
                                 if r.get("fixture_key") == fkey
                                 and r.get("kind") == kind
                                 and r.get("side") == side_id
                                 and r.get("line") == line]
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
                        "r30_old_var_spread": (r30_match[0]["var_spread"]
                                               if r30_match else None),
                        "r30_old_n_variants": (r30_match[0]["n_variants"]
                                               if r30_match else None),
                        "r30_old_p_med": (r30_match[0]["p_med"]
                                          if r30_match else None),
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
                    stake = 250
                    if kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if kind == "ml" and cross:
                        stake = 150
                        flags.append("CROSS-LEAGUE-MW: scan-level unban "
                                     "(WP-P2b PASS); $150 marginal; T4 accumulating")
                    if kind == "ml" and not cross:
                        stake = 150
                        flags.append("MW domestic: eligible-deprioritized; $150"
                                     + ("; 1X2 limitation (gate E)" if lgh == "Championship" else ""))
                    row["stake_usd"] = stake
                    if row["passed_numeric"] and pol_eligible:
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
                        row["passed_numeric"] and pol_eligible and not any(
                            f.startswith(("BANNED", "SPREADS")) for f in flags))
                    board.append(row)
        print("MODELED %-38s %-4s cross=%-5s kick=%s bridge_f=%s rows=%d" % (
            base_title, fx["comp"], cross, fx["kickoff_utc"],
            ("%.3f" % f) if f else "-", sum(
                1 for r in board if r["fixture_key"] == fkey)), flush=True)

    board.sort(key=lambda r: (-(r["exec_edge_haircut"] if r["exec_edge_haircut"] is not None else -9),
                              r["match"]))
    not_modelable = [f for f in fixtures if not f["modelable"]
                     and f["comp"] in ("UCL", "UEL", "UECL", "ENG2")]

    # compression table: per modeled fixture, market-family spreads new vs old
    compression = {}
    for m in matches:
        fk = m["fixture_key"]
        rows = [r for r in board if r["fixture_key"] == fk]
        fam = {}
        for r in rows:
            k = "%s/%s%s" % (r["kind"], r["side"],
                             ("/%.1f" % r["line"]) if r["line"] else "")
            fam[k] = {"new_spread": round(100 * r["var_spread"], 2),
                      "old_spread": (round(100 * r["r30_old_var_spread"], 2)
                                     if r["r30_old_var_spread"] is not None else None),
                      "n_new": r["n_variants"],
                      "n_old": r["r30_old_n_variants"],
                      "p_med_new": r["p_med"], "p_med_old": r["r30_old_p_med"]}
        compression[m["match"]] = {
            "fixture_key": fk, "cross_league": m["cross_league"],
            "bridge_factor": m["bridge_factor"],
            "kickoff_utc": m["kickoff_utc"], "markets": fam}

    out = {
        "scan": "soccer", "round": 33,
        "sub_scan": ("THREE-FIRSTS SCAN: WP-P2a bridge production debut + "
                     "cross-league MW scan-level unban (WP-P2b PASS, T4 "
                     "accumulating) + first Championship model (WP-P3 FotMob); "
                     "entry window Nov-4 10:00Z..Nov-5 10:00Z"),
        "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("entry-placement window (brief); UEL Thursday "
                                "evening kickoffs (17:45/20:00Z Nov-5) fall "
                                "after hi - entries placed at scan time "
                                "(~10:30Z Nov-4) are ~31-34h pre-kickoff "
                                "(r30/r31 interpretation)")},
        "discovery_range_utc": {"lo": DISC_LO, "hi": DISC_HI},
        "bridge": {
            "kappa_path": KAPPA_PATH,
            "loaded_via": "league_strength.load_kappa_report (WP-P2b nested)",
            "kappa": {k: round(v, 6) for k, v in kappa.items()},
            "clamp": "f = exp(clamp(kX-kY, +-ln1.25)); BRIDGE_CLAMP_RATIO=1.25",
            "backtest_evidence": ("round31/backtest_report.json "
                                  "overall_verdict=PASS; T1 pooled RPS diff "
                                  "-0.0130 (p=0.026); T2 away-cal err 0.039; "
                                  "T3 cal diff 0.0045; T5 reproducible; T4 "
                                  "(>=20 settled cross-league MW paper bets "
                                  "before registry flip) status=future"),
            "scan_level_mw_unban": ("cross-league MW eligible-deprioritized at "
                                    "$150, worst>=+5c; library registry still "
                                    "BANNED pending T4 accumulation"),
        },
        "xg_bases": {
            "big5": {"path": understat_pointer.get("target"),
                     "pointer": UNDERSTAT_POINTER,
                     "pointer_sha256": understat_pointer.get("sha256"),
                     "fresh_through_utc": "2026-10-31 (stale until recovery validates)",
                     "http_probe_at_run": probe},
            "championship": {"path": FOTMOB,
                             "fresh_through_utc": "2026-11-03",
                             "validation": "WP-P3 gate D walk-forward PASS (O/U, BTTS, TT)"},
            "championship_1x2_limitation": ("gate E failure: relegated-EPL "
                                            "fallback clubs distort 1X2; O/U/"
                                            "BTTS/TT unaffected"),
        },
        "method": ("Gamma date-window + tag discovery -> soccer events; "
                   "cross-league Big-5 pairs via BRIDGED 10-variant "
                   "fixture_variants (bridge=kappa, WP-P2a; MW eligible-"
                   "deprioritized $150 worst>=+5c); Championship pairs via "
                   "domestic 10-variant path on FotMob snapshot (WP-P3; MW "
                   "$150 1X2-limited); non-snapshot clubs = prices only; "
                   "full odds board both token sides; CLOB $250 ask-VWAP "
                   "walk; frozen gates + cross-league worst>=+5c"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "19501719", "selfcheck": "10/10 PASS",
                    "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src"},
        "gates": dict(gates.GATES, notes=(
            "cross-league all kinds: worst>=+5c (1c extra margin); domestic: "
            "worst>=+4c; both: exec>=+5c after 50-50 haircut (8c if "
            "under-risk), var<=6c, liq>=5k, fill_250, entry .10-.92; "
            "news-concordance at candidate stage; spreads flagged-only")),
        "max_new_positions": 3, "stake_per_position_usd": 250,
        "bankroll_usd": 12998.34, "cash_usd": 10563.00,
        "fixtures": fixtures, "not_modelable": not_modelable,
        "matches": matches, "prices_only": prices_only,
        "variant_compression_vs_r30": compression,
        "board_rows": len(board), "board": board,
        "unparsed_questions": sorted(set(unparsed_qs)),
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nboard rows:", len(board), "matches:", len(matches),
          "prices-only fixtures:", len(prices_only), flush=True)
    print("saved", OUT, flush=True)

    print("\n=== COMPRESSION SUMMARY (new bridged spread vs r30 old boost spread, cents) ===")
    for mk, comp in compression.items():
        pairs = [(k, v) for k, v in comp["markets"].items()
                 if v["old_spread"] is not None]
        if pairs:
            print("%s (bridge_f=%s):" % (mk, comp["bridge_factor"]))
            for k, v in pairs[:40]:
                print("   %-24s old %6.2fc -> new %5.2fc  (n %s->%s, p_med %s->%s)"
                      % (k, v["old_spread"], v["new_spread"], v["n_old"],
                         v["n_new"], v["p_med_old"], v["p_med_new"]))
        else:
            wide = sorted(comp["markets"].items(),
                          key=lambda kv: -kv[1]["new_spread"])[:6]
            print("%s (bridge_f=%s): NO r30 baseline; widest new spreads: %s"
                  % (mk, comp["bridge_factor"],
                     ", ".join("%s %.2fc" % (k, v["new_spread"]) for k, v in wide)))

    pass_rows = [r for r in board if r["passed_numeric"] and r["policy_eligible"]]
    print("\nnumeric passers (eligible kinds, incl. cross-league 5c):", len(pass_rows))
    for r in pass_rows[:20]:
        print("  PASS %-38s %-11s %-9s line=%-4s exec=+%5.1fc worst=+%5.1fc "
              "var=%5.2fc liq=$%6.0f ask=%s p_med=%.3f stake=$%d %s" % (
                  r["match"][:38], r["kind"], r["side"], r["line"],
                  100 * (r["exec_edge_haircut"] or 0),
                  100 * (r["worst_variant_edge"] or 0),
                  100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
                  r["exec_ask_vwap250"], r["p_med"], r["stake_usd"],
                  ";".join(r["entry_flags"])[:80]))

    print("\nTOP-15 by haircut exec edge:")
    for r in board[:15]:
        print("  %+6.1fc worst %+6.1fc var %5.2fc | %-40s | %-11s %-9s %-4s | "
              "p_med %.3f ask %s liq $%.0f | %s" % (
                  100 * (r["exec_edge_haircut"] if r["exec_edge_haircut"] is not None else -9),
                  100 * (r["worst_variant_edge"] if r["worst_variant_edge"] is not None else -9),
                  100 * (r["var_spread"] or 0), r["match"][:40], r["kind"],
                  r["side"], r["line"], r["p_med"], r["exec_ask_vwap250"],
                  r["liq_gamma"] or 0, r["section"][:20]))


if __name__ == "__main__":
    main()
