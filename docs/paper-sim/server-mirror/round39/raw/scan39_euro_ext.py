"""Round-39A EUROPE-BEYOND-BIG5 scan (paper-only): Eredivisie modeled on the
WP-P3 FotMob library path (FIRST Eredivisie adapter run; both season blocks
fetched live 2026-11-07 through Nov-6 games), all other European leagues in
scope reported as NO MODEL COVERAGE board-only rows.

Window: kickoff 2026-11-06T13:30Z .. 2026-11-08T23:59:59Z. At scan time
(Sat 2026-11-07 ~07:2xZ) every Nov-6 fixture is POST-KICKOFF (ESPN: Full
Time) -> excluded from entry; enterable slate = Sat Nov-7 + Sun Nov-8.

xG BASES:
  Eredivisie: round39/raw/xg_fotmob_eredivisie.json (Eredivisie_2026: 100
    matches through Nov-6 19:00Z, 18 teams x 11 games; Eredivisie_2025: 306
    matches). Live fetch via library fetch_fotmob_league/fetch_match_details
    (FotMobLeague.EREDIVISIE id 57, 34 rounds, 18 teams). Inline sanity:
    2025 goal fit xG 1.778/1.381 vs goals 1.801/1.376 per game (~1.3%),
    Pearson r xGF-GF 0.859 / xGA-GA 0.776 (Championship gate-C bar: 0.7).
    NOT full WP-P3 validated: gates D/E never run for Eredivisie -> match_
    winner stays deprioritized with an explicit first-run caveat; totals-
    family channels follow the WP-P3 sanction shape.
  Big-5 + Championship snapshots loaded for classification/registry only
    (no modeling in this scan; Big-5+Championship = other agents' territory).

Policy: spreads FLAGGED-ONLY; totals $250 standard (subscan budget $150
total, coordinator arbitrates); ml $150 deprioritized + Eredivisie caveat;
no held-fixture overlay expected (7 held fixtures are all Big-5/French).
"""
import json
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import (  # noqa: E402
    fotmob, gates, league_strength, soccer_model, xg)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
HOME = "/home/ubuntu/paper-sim"
UNDERSTAT_LATEST = f"{HOME}/understat_latest.json"
UNDERSTAT_POINTER = f"{HOME}/understat_latest_pointer.json"
FOTMOB_CHAMP = f"{HOME}/round31/raw/xg_fotmob_championship.json"
ERED = f"{HOME}/round39/raw/xg_fotmob_eredivisie.json"
ERED_META = ERED + ".meta.json"
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"
OUTDIR = f"{HOME}/round39/raw"
OUT = f"{OUTDIR}/euro_ext_scan.json"
LO = "2026-11-06T13:30:00Z"
HI = "2026-11-08T23:59:59Z"
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")
NOW = datetime.now(timezone.utc)
NOW_S = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

ESPN_LEAGUES = {"ned.1": "Eredivisie", "bel.1": "Belgian Pro League",
                "por.1": "Primeira Liga", "sco.1": "Scottish Premiership",
                "tur.1": "Turkish Super Lig", "aut.1": "Austrian Bundesliga",
                "sui.1": "Swiss Super League", "den.1": "Danish Superliga",
                "nor.1": "Norwegian Eliteserien", "gre.1": "Greek Super League",
                "swe.1": "Allsvenskan", "rus.1": "Russian Premier League"}

# Gamma league tag -> league label (SCOPE: European first tiers beyond Big-5)
LEAGUE_TAGS = {
    "ere": "Eredivisie",
    "primeira-liga": "Primeira Liga",
    "scottish-premiership": "Scottish Premiership",
    "tur": "Turkish Super Lig",
    "bel1": "Belgian Pro League",
    "austria-bundesliga": "Austrian Bundesliga",
    "switzerland-super-league": "Swiss Super League",
    "denmark-superliga": "Danish Superliga",
    "norway-eliteserien": "Norwegian Eliteserien",
    "sweden-allsvenskan": "Allsvenskan",
    "rus": "Russian Premier League",
    "gre1": "Greek Super League",
    "poland-ekstraklasa": "Ekstraklasa",
    "czechia-fortuna-liga": "Czech First League",
    "Romania-SuperLiga": "Romanian SuperLiga",
    "ukraine-premier-liha": "Ukrainian Premier League",
    "serbian-superliga": "Serbian SuperLiga",
    "hungary-nb1": "Hungarian NB1",
    "bulgaria-parva-liga": "Bulgarian Parva Liga",
    "slovenia-prvaliga": "Slovenian PrvaLiga",
    "soccer-hr1": "Croatian HNL",
    "est1": "Estonian Meistriliiga",
    "fin1": "Finnish Veikkausliiga",
    "lva1": "Latvian Virsliga",
    "ltu1": "Lithuanian A Lyga",
    "nirl1": "Northern Ireland Premiership",
    "irl1": "League of Ireland",
    "blr1": "Belarusian Premier League",
    "israel-premier-league": "Israeli Premier League",
    "aze1": "Azerbaijan Premier League",
}
# second/third tiers + cups + continental: census-only, no board rows
CENSUS_ONLY = {"bel2", "ned2", "tur2", "nor2", "swe2", "pt2", "serie-b",
               "serc", "la-liga-2", "bundesliga-2", "ligue-2", "es3",
               "fa-cup", "nls", "ucl", "uel", "conference-league"}
BIG5_TAGS = {"epl", "premier-league", "la-liga", "sea", "bundesliga",
             "ligue-1", "efl-championship", "championship"}

TEAM_ALIASES = {
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
CANON_DENY_EXACT = {"ofi", "ski", "if", "go", "sk", "fk", "fc", "ac", "sc"}

HELD_FIXTURES = [
    ("Sevilla", "Alaves"), ("Manchester United", "Aston Villa"),
    ("Mainz 05", "Bayern Munich"), ("Osasuna", "Athletic Club"),
    ("Valencia", "Real Madrid"), ("Le Mans", "Monaco"), ("Brest", "Lyon"),
]


def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2.0 + 2 * i)
    raise last


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


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


HELD_KEYS = {fixture_key(h, a) for h, a in HELD_FIXTURES}

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
        if home is not None and resolved == home:
            return "home"
        if away is not None and resolved == away:
            return "away"
        n = norm_name(name)
        if not n or n in CANON_DENY_EXACT:
            return None
        if len(n) >= 5:
            for cand, side in ((home, "home"), (away, "away")):
                if cand is None:
                    continue
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


def scan_policy(kind):
    if kind == "spread":
        return ("FLAGGED_ONLY", False,
                "spreads flagged-only (blowout-tail rule): counted, never entered")
    if kind == "ml":
        return ("ELIGIBLE-DEPRIORITIZED", True,
                "domestic MW eligible-deprioritized ($150); EREDIVISIE 1X2 caveat: "
                "adapter FIRST RUN (WP-P3 gates D/E never run; promoted-side prior-"
                "season fallback = gate-E distortion class)")
    return ("ELIGIBLE", True,
            "totals-family allowed; Eredivisie adapter first run, inline B/C-equiv "
            "checks passed (goal fit ~1.3%, r=0.86/0.78 vs 0.7 bar)")


def main():
    print("UTC now:", NOW_S, flush=True)

    # ---- snapshots via validated loaders (template Block 2 provenance) ----
    with open(UNDERSTAT_POINTER, "r", encoding="utf-8") as _ph:
        understat_pointer = json.load(_ph)
    print("understat latest pointer ->", understat_pointer.get("target"),
          "pointed_at", understat_pointer.get("pointed_at_utc"), flush=True)
    snapshot = dict(xg.load_xg_snapshot(UNDERSTAT_LATEST))
    fot_payload = fotmob.load_fotmob_snapshot(FOTMOB_CHAMP)
    for k, v in fot_payload.items():
        snapshot[k] = v
    ered_payload = fotmob.load_fotmob_snapshot(ERED)
    for k, v in ered_payload.items():
        snapshot[k] = v
    print("snapshot blocks:", sorted(snapshot.keys()), flush=True)
    for lg in BIG5:
        block = snapshot.get(f"{lg}_2026") or {}
        for t in (block.get("teams") or {}).values():
            if t.get("title"):
                ALL_TITLES[t["title"]] = lg
                TITLE_LEAGUE[t["title"]] = lg
    for lgkey, label in (("Championship_2026", "Championship"),
                         ("Eredivisie_2026", "Eredivisie")):
        for t in (snapshot[lgkey].get("teams") or {}).values():
            if t.get("title"):
                ALL_TITLES[t["title"]] = label
                TITLE_LEAGUE[t["title"]] = label
    print("registry titles: Big-5 %d + Championship %d + Eredivisie %d" % (
        sum(1 for v in TITLE_LEAGUE.values() if v in BIG5),
        sum(1 for v in TITLE_LEAGUE.values() if v == "Championship"),
        sum(1 for v in TITLE_LEAGUE.values() if v == "Eredivisie")), flush=True)

    with open(ERED_META) as mh:
        ered_meta = json.load(mh)

    # ---- bridge (provenance only; Eredivisie pairs all domestic) ----
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)
    print("bridge loaded (provenance only):", KAPPA_PATH, flush=True)

    # ---- ESPN fixtures ----
    espn = json.load(open(f"{OUTDIR}/espn_leagues_probe.json"))
    espn_rows = []
    for date, day in espn.items():
        for code, payload in day.items():
            label = ESPN_LEAGUES.get(code)
            if not label:
                continue
            for ev in (payload.get("events") if isinstance(payload, dict) else None) or []:
                th = ev["teams"].get("home")
                ta = ev["teams"].get("away")
                espn_rows.append({"espn_league": label, "home": th, "away": ta,
                                  "kick": ev.get("date") or "", "status": ev.get("status")})
    espn_rows.sort(key=lambda r: r["kick"])
    print("ESPN in-scope fixtures (Nov 6-8):", len(espn_rows), flush=True)

    # ---- events ----
    events = json.load(open(f"{OUTDIR}/events_window_39.json"))
    events = [e for e in events if LO <= (e.get("kick") or "") <= HI]
    print("soccer events with kickoff in window:", len(events), flush=True)

    # ---- coverage census ----
    census = {}
    for e in events:
        for t in e["tags"]:
            if t in ("sports", "games", "soccer"):
                continue
            census[t] = census.get(t, 0) + 1

    # ---- classify events to leagues ----
    def league_of(e):
        tags = set(e["tags"])
        for tag, label in LEAGUE_TAGS.items():
            if tag in tags:
                return label, tag
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+", base, maxsplit=1)
        if len(parts) == 2:
            h, a = canon_team(parts[0].strip()), canon_team(parts[1].strip())
            if h and a and TITLE_LEAGUE.get(h) == "Eredivisie" == TITLE_LEAGUE.get(a):
                return "Eredivisie", "(registry)"
        for tag in BIG5_TAGS:
            if tag in tags:
                return "BIG5_OR_CHAMP", tag
        for tag in CENSUS_ONLY:
            if tag in tags:
                return "CENSUS_ONLY", tag
        return None, None

    in_scope = []
    skipped = {"BIG5_OR_CHAMP": 0, "CENSUS_ONLY": 0, "OTHER_TAG": 0, "NOTAG": 0}
    for e in events:
        label, tag = league_of(e)
        if label is None:
            skipped["NOTAG" if not tag else "OTHER_TAG"] += 1
            continue
        if label == "BIG5_OR_CHAMP":
            skipped["BIG5_OR_CHAMP"] += 1
            continue
        if label == "CENSUS_ONLY":
            skipped["CENSUS_ONLY"] += 1
            continue
        e["league"] = label
        e["league_tag"] = tag
        in_scope.append(e)
    print("in-scope board events:", len(in_scope), "| skipped:", skipped, flush=True)

    # group events into primary fixtures
    groups = {}
    for e in in_scope:
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        key = (e["kick"], base, e["league"])
        groups.setdefault(key, []).append(e)

    def espn_match(kick, league, base):
        # require league agreement + kickoff within 3h; verify team overlap
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
            dt = abs((datetime.fromisoformat(r["kick"].replace("Z", "+00:00"))
                      - datetime.fromisoformat(kick.replace("Z", "+00:00"))
                      ).total_seconds())
            if dt > 3 * 3600:
                continue
            agree = team_overlap(r)
            if (best is None or (agree and not best_agree)
                    or (agree == best_agree and dt < best_dt)):
                best_dt, best, best_agree = dt, r, agree
        if best is not None:
            return {**best, "teams_agree": best_agree}
        return None

    fixtures, matches, board, board_only, unparsed_qs = [], [], [], [], []
    for key in sorted(groups, key=lambda k: (k[0], k[1])):
        kick, base, league = key
        grp = groups[key]
        post_kick = kick <= NOW_S
        er = espn_match(kick, league, base)
        parts = re.split(r"\s+vs\.?\s+", base, maxsplit=1)
        home_raw = parts[0].strip() if parts else ""
        away_raw = parts[1].strip() if len(parts) > 1 else ""
        home = canon_team(home_raw)
        away = canon_team(away_raw)
        fkey = fixture_key(home_raw, away_raw) if home_raw and away_raw else None
        held_here = fkey in HELD_KEYS if fkey else False
        fixtures.append({
            "match": base, "league": league, "kickoff_utc": kick,
            "post_kickoff": post_kick,
            "enterable_window": (not post_kick) and kick <= HI,
            "held_fixture": held_here,
            "espn_cross": ({"league": er["espn_league"], "home": er["home"],
                            "away": er["away"], "kick": er["kick"],
                            "status": er["status"],
                            "teams_agree": er.get("teams_agree")} if er else None),
            "gamma_event_ids": sorted({e["id"] for e in grp}),
            "n_markets": sum(len(e["markets"]) for e in grp),
            "understat_home": home if league == "Eredivisie" else None,
            "understat_away": away if league == "Eredivisie" else None})

        if league != "Eredivisie" or post_kick or not (home and away):
            rows = []
            top_liq_m, top_liq = None, -1.0
            seen_mkt = set()
            for e in grp:
                for m in e["markets"]:
                    if m["id"] in seen_mkt:
                        continue
                    seen_mkt.add(m["id"])
                    liq = float(m.get("liq") or 0)
                    rows.append({"q": m["q"], "id": m["id"],
                                 "outcomes": m["outcomes"], "prices": m["prices"],
                                 "line": m.get("line"), "group": m.get("group"),
                                 "liq_gamma": liq, "best_bid": m.get("bestBid"),
                                 "best_ask": m.get("bestAsk")})
                    if liq > top_liq:
                        top_liq_m, top_liq = m, liq
            book = fetch_book(top_liq_m, 0) if top_liq_m else None
            board_only.append({
                "match": base, "league": league, "kickoff_utc": kick,
                "post_kickoff": post_kick, "held_fixture": held_here,
                "coverage": "NO MODEL COVERAGE - report only, no entry",
                "reason": ("league not in FotMob adapter enum (Championship/"
                           "Eredivisie only); cross-league pairing of unrated "
                           "teams banned by library guard"),
                "espn_cross": (fixtures[-1]["espn_cross"]),
                "n_markets": fixtures[-1]["n_markets"],
                "top_book": ({"q": top_liq_m["q"], "id": top_liq_m["id"],
                              "best_bid": book["best_bid"],
                              "best_ask": book["best_ask"]} if book else None),
                "rows": rows})
            print("BOARD-ONLY %-34s %-24s kick=%s rows=%d%s" % (
                base[:34], league, kick, len(rows),
                " POST-KICKOFF" if post_kick else ""), flush=True)
            continue

        # ---- Eredivisie modeled path ----
        variants = soccer_model.fixture_variants(snapshot, home, "Eredivisie",
                                                  away, "Eredivisie")
        if variants is None:
            fixtures[-1]["modelable"] = False
            print("MODEL-VOID %s: variants None" % base, flush=True)
            continue
        vs = [{"lambdas": (v.lambdas[0], v.lambdas[1]), "outputs": v.outputs,
               "spec": v.spec.name} for v in variants]
        lam_h = soccer_model.median([v["lambdas"][0] for v in vs])
        lam_a = soccer_model.median([v["lambdas"][1] for v in vs])
        p1x2 = {"H": soccer_model.median([v["outputs"].home_win for v in vs]),
                "D": soccer_model.median([v["outputs"].draw for v in vs]),
                "A": soccer_model.median([v["outputs"].away_win for v in vs])}
        try:
            form_h = xg.recent_form(snapshot, home)
            form_a = xg.recent_form(snapshot, away)
        except Exception:  # noqa: BLE001
            form_h = form_a = None
        matches.append({
            "match": base, "league": "Eredivisie", "kickoff_utc": kick,
            "home": home, "away": away, "fixture_key": fkey,
            "lambda_home": round(lam_h, 3), "lambda_away": round(lam_a, 3),
            "lambda_total": round(lam_h + lam_a, 3),
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
            "method": ("library fixture_variants 10 sweeps, DOMESTIC Eredivisie "
                       "(FotMob WP-P3 first run)")})
        o25_combined = ((form_h.over_2_5_hits if form_h else 0)
                        + (form_a.over_2_5_hits if form_a else 0))
        seen_mkt = set()
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
                    book = fetch_book(m, token_idx)
                    if book is None:
                        continue
                    liq = float(m.get("liq") or 0)
                    quote = {"model_median": soccer_model.median(qs),
                             "qs_variants": tuple(qs)}
                    ur, ur_reason = gates.under_risk_check(
                        kind=kind,
                        side=(side_id.split("_no")[0]
                              if side_id.endswith("_no") else side_id),
                        o25_hits=o25_combined, lambda_total=lam_h + lam_a,
                        lambda_home=lam_h, lambda_away=lam_a,
                        line=line if line else 2.5)
                    report = gates.evaluate_candidate(
                        quote, book["asks"], gamma_liquidity=liq, under_risk=ur,
                        fee_rate=gates.FEE_RATE_SPORTS)
                    pol, pol_eligible, pol_reason = scan_policy(kind)
                    lib_pol = gates.suspension_policy(kind, cross_league=False)
                    exit_walk = gates.walk_book(
                        [(p, s) for p, s in book["bids"]], side="bid")
                    flags = []
                    stake = 250
                    if kind == "spread":
                        flags.append("SPREADS-FLAGGED-ONLY (never entered)")
                    if kind == "ml":
                        stake = 150
                        flags.append("MW eligible-deprioritized; EREDIVISIE 1X2 "
                                     "caveat (adapter first run)")
                    if held_here:
                        flags.append("HELD-FIXTURE (never entered)")
                    row = {
                        "match": base, "league": "Eredivisie", "fixture_key": fkey,
                        "kickoff_utc": kick, "q": m["q"], "kind": kind,
                        "side": side_id, "line": line, "team_side": team_side,
                        "id": m["id"], "policy": pol, "policy_eligible": pol_eligible,
                        "policy_reason": pol_reason,
                        "library_policy": lib_pol.policy,
                        "library_policy_reason": lib_pol.reason,
                        "p_med": round(quote["model_median"], 4),
                        "p_min": round(min(qs), 4), "p_max": round(max(qs), 4),
                        "n_variants": len(qs), "var_spread": report.variant_spread,
                        "book_best_bid": book["best_bid"],
                        "book_best_ask": book["best_ask"],
                        "liq_gamma": liq, "exec_ask_vwap250": report.walk.vwap,
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
                        "exec_edge_haircut": report.exec_edge_haircut,
                        "worst_variant_edge": report.worst_variant_edge,
                        "haircut": report.haircut, "under_risk": ur,
                        "under_risk_reason": ur_reason,
                        "checks": {k: bool(v) for k, v in report.checks.items()},
                        "passed_numeric": all(v for k, v in report.checks.items()
                                              if k != "news_concordant"),
                        "stake_usd": stake, "entry_flags": flags,
                        "held_fixture": held_here, "post_kickoff": False,
                        "enterable": False}
                    if row["passed_numeric"] and pol_eligible:
                        flags.append("NUMERIC-PASS (pending news-concordance)")
                    hrs = max(1, round((datetime.fromisoformat(
                        kick.replace("Z", "+00:00")) - NOW).total_seconds() / 3600))
                    flags.append("T-%dh pre-kick (XIs unset; ~1h pre-kick drop)" % hrs)
                    row["enterable"] = bool(
                        row["passed_numeric"] and pol_eligible and not held_here
                        and not post_kick and not any(
                            f.startswith(("BANNED", "SPREADS", "HELD")) for f in flags))
                    board.append(row)
        print("MODELED %-34s kick=%s lam=%.2f/%.2f rows=%d" % (
            base[:34], kick, lam_h, lam_a,
            sum(1 for r in board if r["fixture_key"] == fkey)), flush=True)

    board.sort(key=lambda r: (-(r["exec_edge_haircut"]
                                if r["exec_edge_haircut"] is not None else -9),
                              r["match"]))

    # ---- candidate verification: GET /markets/{id} for numeric passers ----
    passers = [r for r in board if r["passed_numeric"] and r["policy_eligible"]]
    verifications = {}
    for r in passers[:12]:
        try:
            m = get(BASE + "/markets/" + r["id"])
            verifications[r["id"]] = {
                "question": m.get("question"), "closed": m.get("closed"),
                "active": m.get("active"), "endDate": m.get("endDate"),
                "gameStartTime": m.get("gameStartTime"),
                "liquidityNum": m.get("liquidityNum"), "id": str(m.get("id"))}
            time.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            verifications[r["id"]] = {"error": repr(e)[:150]}

    out = {
        "scan": "soccer-europe-beyond-big5", "round": 39, "sub_scan": "A (euro-ext)",
        "paper_only": True,
        "generated_utc": NOW_S,
        "window_utc": {"lo": LO, "hi": HI,
                       "note": ("scan ran Sat 2026-11-07 ~07:2xZ; every Nov-6 fixture "
                                "is POST-KICKOFF (ESPN Full Time) -> excluded from entry")},
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "5bdae2e3",
                    "selfcheck": "PASS 10/10 (re-run 2026-11-07 ~06:5xZ)",
                    "fee_model": ("evaluate_candidate(..., fee_rate=FEE_RATE_SPORTS) "
                                  "- net of Polymarket fee 0.05*p*(1-p); worst variant gross")},
        "coverage": {
            "fotmob_adapter_enum": ["Championship", "Eredivisie"],
            "modeled": ["Eredivisie (FIRST adapter run; WP-P3 full validation NOT run)"],
            "no_model_coverage": sorted({b["league"] for b in board_only}),
            "census_only_tags": sorted(CENSUS_ONLY),
            "skipped_counts": skipped,
            "tag_census_window": dict(sorted(census.items(), key=lambda kv: -kv[1]))},
        "xg_bases": {
            "eredivisie": {"path": ERED, "meta": ered_meta,
                           "fresh_through": "2026-11-06 19:00Z (Eredivisie_2026: 100 matches)",
                           "sanity": ("2025 goal fit xG 1.778/1.381 vs goals 1.801/1.376 "
                                      "(~1.3%); Pearson r xGF-GF 0.859, xGA-GA 0.776")},
            "big5_pointer": {"target": understat_pointer.get("target"),
                             "sha256": understat_pointer.get("sha256"),
                             "note": "classification/registry only; not modeled in this scan"},
            "championship": {"path": FOTMOB_CHAMP, "note": "registry only"}},
        "bridge": {"kappa_path": KAPPA_PATH,
                   "kappa": {k: round(v, 6) for k, v in kappa.items()},
                   "note": "loaded for provenance only; Eredivisie pairs all domestic"},
        "gates": dict(gates.GATES, notes=(
            "NET-EDGE BARS: exec>=+5c net of sports fee 0.05*p*(1-p) at walked price "
            "(8c net if under-risk); domestic worst>=+4c gross; var<=6c; liq>=5k; "
            "fill_250; news-concordance at candidate stage; spreads flagged-only; "
            "MW $150 deprioritized + Eredivisie first-run caveat")),
        "budget": {"weekend_cap_all_agents_usd": 200,
                   "this_subscan_max_usd": 150,
                   "note": "coordinator arbitrates combined pool across agents A+B"},
        "held_positions": {"fixtures": [" - ".join(x) for x in HELD_FIXTURES],
                           "note": "all Big-5/French; no overlay expected in this scan"},
        "espn_fixture_source": {"path": f"{OUTDIR}/espn_leagues_probe.json",
                                "codes": list(ESPN_LEAGUES)},
        "fixtures": fixtures, "matches": matches, "board_only": board_only,
        "board_rows": len(board), "board": board,
        "candidate_verifications": verifications,
        "unparsed_questions": sorted(set(unparsed_qs))[:40]}
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nsaved", OUT, flush=True)
    print("board rows:", len(board), "| matches:", len(matches),
          "| board-only fixtures:", len(board_only), flush=True)

    print("\nnumeric passers (eligible kinds):", len(passers))
    for r in passers[:20]:
        print("  PASS %-38s %-11s %-9s line=%-4s net=+%5.1fc worst=+%5.1fc var=%5.2fc "
              "liq=$%6.0f ask=%s p_med=%.3f %s" % (
                  r["match"][:38], r["kind"], r["side"], r["line"],
                  100 * (r["exec_edge_haircut"] or 0),
                  100 * (r["worst_variant_edge"] or 0),
                  100 * (r["var_spread"] or 0), r["liq_gamma"] or 0,
                  r["exec_ask_vwap250"], r["p_med"], ";".join(r["entry_flags"])[:80]))

    print("\nTOP-25 by haircut net edge:")
    for r in board[:25]:
        print("  NET %+6.1fc worst %+6.1fc var %5.2fc | %-36s | %-11s %-8s %-4s | "
              "p_med %.3f ask %s liq $%.0f" % (
                  100 * (r["exec_edge_haircut"]
                         if r["exec_edge_haircut"] is not None else -9),
                  100 * (r["worst_variant_edge"]
                         if r["worst_variant_edge"] is not None else -9),
                  100 * (r["var_spread"] or 0), r["match"][:36], r["kind"],
                  r["side"], r["line"], r["p_med"], r["exec_ask_vwap250"],
                  r["liq_gamma"] or 0))


if __name__ == "__main__":
    main()
