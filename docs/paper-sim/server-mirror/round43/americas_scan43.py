"""ROUND-43C paper-sim scan: AMERICAS OVERNIGHT TAIL, kickoff window
2026-11-09T01:15:00Z .. 2026-11-09T05:30:00Z (Sunday night UTC = South
American Sunday evening / MLS + Liga MX Sunday night).

BOARD-ONLY: FotmobLeague enum is {CHAMPIONSHIP(48), EREDIVISIE(57)} only;
Argentina/Brasileirao/Colombia/Chile/Ecuador/Uruguay/Paraguay/Bolivia/
MLS/Liga MX etc. have NO model coverage. Every row is labeled
"NO MODEL COVERAGE - report only, no entry". No ratings fabricated.
The only library call is gates.walk_book (pure book math, no model).
STOP rule: if any fixture unexpectedly has modelable clubs from the
snapshot (Big-5 / Championship / Eredivisie), STOP and report - no modeling.

Paper only: no orders, no DB writes, no credentials, GET-only HTTP.

Reuses round39/raw/americas_scan39.py + round40/41/42 sweep patterns.
Note (dispatch): /markets?ids= list param is BROKEN -> verify via
/markets/{id}. Pagination cap 1000 -> per-tag sweeps as r39 did.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import gates  # noqa: E402  (walk_book only)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HOME = "/home/ubuntu/paper-sim"
OUTDIR = f"{HOME}/round43/raw"
OUT = f"{OUTDIR}/americas_scan.json"
BOARD_OUT = f"{HOME}/round43/americas_board.json"
SCAN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LO = "2026-11-09T01:15:00Z"          # kickoff window lo (dispatch)
HI = "2026-11-09T05:30:00Z"          # kickoff window hi (dispatch)
REPO_COMMIT = "1a2760bc"

# ---- modelable-club snapshot sources (STOP check) ----
SNAPSHOT_POINTER = f"{HOME}/understat_latest_pointer.json"
BIG5_XG = f"{HOME}/round41/raw/xg_fotmob_big5_merged.json"
CHAMP_XG = f"{HOME}/championship_20261108/xg_fotmob_championship.json"
ERE_XG = f"{HOME}/round41/raw/xg_fotmob_eredivisie.json"

ESPN_LEAGUES = {
    # Americas (in scope)
    "arg.1": "Argentina Primera", "bra.1": "Brasileirao Serie A",
    "bra.2": "Brasileirao Serie B", "mex.1": "Liga MX",
    "usa.1": "MLS", "col.1": "Colombia Primera A",
    "chi.1": "Chile Primera Division", "ecu.1": "Ecuador Serie A",
    "uru.1": "Uruguay Primera Division", "par.1": "Paraguay Division Profesional",
    "bol.1": "Bolivia LFPB", "per.1": "Peru Liga 1",
    "ven.1": "Venezuela Primera Division", "crc.1": "Costa Rica Primera Division",
    "gua.1": "Guatemala Liga Nacional",
    # Europe Monday-early slippage check (expect kickoffs 19:45Z+ Mon, outside window)
    "eng.2": "Championship", "fra.1": "Ligue 1",
}
ESPN_DATES = ("20261108", "20261109", "20261110")

# League tag slugs observed on Gamma (r39 tag census) + common aliases.
LEAGUE_TAG_MAP = {
    "arg": "Argentina Primera", "argentina-primera": "Argentina Primera",
    "liga-profesional": "Argentina Primera",
    "primera-division-argentina": "Argentina Primera",
    "brazil-serie-a": "Brasileirao Serie A", "brasileirao": "Brasileirao Serie A",
    "brazilian-serie-a": "Brasileirao Serie A", "serie-a-brasil": "Brasileirao Serie A",
    "brazil-serie-b": "Brasileirao Serie B", "brasileirao-serie-b": "Brasileirao Serie B",
    "soccer-brco": "Copa do Brasil", "copa-do-brasil": "Copa do Brasil",
    "mex": "Liga MX", "liga-mx": "Liga MX", "ligamx": "Liga MX",
    "futbol-mexicano": "Liga MX", "mexican-league": "Liga MX",
    "liga-mx-apertura": "Liga MX", "mex2": "Liga MX Expansion",
    "mls": "MLS", "mls-cup": "MLS Cup Playoffs",
    "mls-cup-playoffs": "MLS Cup Playoffs", "mls-playoffs": "MLS Cup Playoffs",
    "mls-cup-2026": "MLS Cup Playoffs",
    "colombia-primera-a": "Colombia Primera A",
    "colombian-primera-a": "Colombia Primera A", "col2": "Colombia Primera B",
    "chile-primera": "Chile Primera Division",
    "chile-primera-division": "Chile Primera Division",
    "ecu1": "Ecuador Serie A", "ecuador-serie-a": "Ecuador Serie A",
    "peru-liga-1": "Peru Liga 1", "peru-liga": "Peru Liga 1",
    "par1": "Paraguay Division Profesional",
    "paraguay-division-profesional": "Paraguay Division Profesional",
    "Bolivia-LFPB": "Bolivia LFPB", "bolivia-lfpb": "Bolivia LFPB",
    "ven1": "Venezuela Primera Division",
    "uru1": "Uruguay Primera Division",
    "soccer-fpd": "Costa Rica Primera Division",
    "soccer-gtm": "Guatemala Liga Nacional",
    "canpl": "Canadian Premier League", "uslc": "USL Championship",
    "soccer-nwsl": "NWSL (women)",
}
WOMEN_TAGS = {"soccer-nwsl", "nwsl", "wsl", "womens-soccer", "liga-mx-femenil",
              "nwsoccer", "womens-football", "feminine", "libertadores-femenina",
              "w-league", "a-league-women", "soccer-womens"}
EURO_TAGS = {"epl", "EPL", "premier-league", "efl-championship", "championship",
             "la-liga", "laliga", "sea", "serie-a", "bundesliga", "ligue-1",
             "ere", "eredivisie", "bel1", "tur", "primeira-liga",
             "scottish-premiership", "ucl", "champions-league",
             "uefa-champions-league", "europa-league", "uel", "fa-cup",
             "la-liga-2", "bundesliga-2", "serie-b", "ligue-2", "bel2", "tur2"}
FRIENDLY_PAT = re.compile(r"\bfriendly\b|\bfriendlies\b|club friendly", re.I)

TAG_SWEEPS = [
    "soccer", "arg", "brazil-serie-a", "brazil-serie-b", "soccer-brco",
    "mex", "mex2", "liga-mx", "mls", "mls-cup", "colombia-primera-a", "col2",
    "chile-primera", "ecu1", "peru-liga-1", "par1", "Bolivia-LFPB", "ven1",
    "uru1", "soccer-fpd", "soccer-gtm", "canpl", "uslc", "soccer-nwsl",
]


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None  # dead endpoint: fast-fail, no retry
            last = e
            time.sleep(1.5 + i)
        except Exception as e:  # noqa: BLE001
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
        "rc", "ud", "us", "as", "sv", "cd", "ca", "scd", "sd"}]
    return " ".join(toks).strip()


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return []
    return raw or []


def sweep(order, extra_params, ascending="false", max_offset=1000):
    out, offset = [], 0
    while True:
        params = {"limit": 100, "active": "true", "closed": "false",
                  "order": order, "ascending": ascending, "offset": offset}
        params.update(extra_params)
        resp = get(BASE + "/events/pagination?" + urllib.parse.urlencode(params))
        if resp is None:
            return out
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
    desc = re.sub(r"\s+", " ", str(e.get("description") or "")).strip()
    slim = {"id": eid, "title": e.get("title"), "slug": e.get("slug"),
            "tags": tags, "liq": e.get("liquidityNum"),
            "vol24": e.get("volume24hr"),
            "description_excerpt": desc[:600], "markets": []}
    for m in e.get("markets") or []:
        if m.get("closed"):
            continue
        mdesc = re.sub(r"\s+", " ", str(m.get("description") or "")).strip()
        slim["markets"].append({
            "id": str(m.get("id")), "q": m.get("question"),
            "slug": m.get("slug"), "group": m.get("groupItemTitle"),
            "type": m.get("marketType"),
            "outcomes": parse_listy(m.get("outcomes")),
            "prices": parse_listy(m.get("outcomePrices")),
            "tokens": parse_listy(m.get("clobTokenIds")),
            "line": m.get("line") or m.get("handicap"),
            "gameStartTime": norm_ts(m.get("gameStartTime")),
            "endDate": norm_ts(m.get("endDate")),
            "liq": m.get("liquidityNum"), "vol24": m.get("volume24hr"),
            "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
            "spread": m.get("spread"), "active": m.get("active"),
            "description_excerpt": mdesc[:900]})
    kos = [m["gameStartTime"] for m in slim["markets"] if m["gameStartTime"]]
    slim["kick"] = min(kos) if kos else ""
    return slim


def in_range(ev, lo, hi):
    kos = [m["gameStartTime"] for m in ev["markets"] if m["gameStartTime"]]
    return any(lo <= k <= hi for k in kos)


BOOK_CACHE = {}
MKT_CACHE = {}


def fetch_book(token):
    if token in BOOK_CACHE:
        return BOOK_CACHE[token]
    book = None
    try:
        b = get(CLOB + "/book?token_id=" + token)
        if b is not None:
            asks = [(float(l["price"]), float(l["size"])) for l in b.get("asks", [])]
            bids = [(float(l["price"]), float(l["size"])) for l in b.get("bids", [])]
            book = {"asks": asks, "bids": bids,
                    "best_ask": min((p for p, _ in asks), default=None),
                    "best_bid": max((p for p, _ in bids), default=None)}
    except Exception as e:  # noqa: BLE001
        print("book err", token, repr(e), flush=True)
    BOOK_CACHE[token] = book
    time.sleep(0.25)
    return book


def fetch_market(mid):
    if mid in MKT_CACHE:
        return MKT_CACHE[mid]
    m = get(BASE + "/markets/" + str(mid))
    MKT_CACHE[mid] = m
    time.sleep(0.2)
    return m


def espn_fixtures():
    out = {}
    for date in ESPN_DATES:
        day = {}
        for code, label in ESPN_LEAGUES.items():
            try:
                d = get(f"{ESPN}/{code}/scoreboard?dates={date}")
                if d is None:
                    day[label] = {"error": "404/no data"}
                    continue
                evs = []
                for ev in d.get("events") or []:
                    comp = (ev.get("competitions") or [{}])[0]
                    teams = {}
                    for c in comp.get("competitors") or []:
                        t = c.get("team") or {}
                        teams["home" if c.get("homeAway") == "home" else "away"] = {
                            "name": t.get("displayName"),
                            "abbr": t.get("abbreviation")}
                    notes = str(((comp.get("notes") or [{}])[0].get("headline")) or "")
                    evs.append({"date": norm_ts(ev.get("date")), "name": ev.get("name"),
                                "venue": (comp.get("venue") or {}).get("fullName"),
                                "teams": teams, "note": notes,
                                "status": (ev.get("status") or {}).get("type", {}).get("description")})
                if evs:
                    day[label] = evs
            except Exception as e:  # noqa: BLE001
                day[label] = {"error": repr(e)}
            time.sleep(0.3)
        out[date] = day
    return out


def classify_kind(m):
    q = strip_accents(str(m.get("q") or "").lower())
    g = strip_accents(str(m.get("group") or "").lower())
    blob = q + " " + g
    if re.search(r"(1st|2nd|first|second)\s*half", blob) or "halftime" in blob:
        return "half"
    if any(w in blob for w in ("corner", "card ", "cards", "odd or even",
                               "score first", "exact score", "leading",
                               "player", "goalscorer", "score in")):
        return "prop"
    if q.startswith("spread") or re.search(r"\(\s*[-+]?\d+\.5\s*\)", blob):
        return "spread"
    if re.search(r"end in a draw", blob):
        return "ml_draw"
    if re.search(r"\bwin on\b|\bwin \(", blob) or "match winner" in g:
        return "ml_win"
    if re.search(r"\bo/u\b|over/under", blob) or ("over" in blob and "under" in blob) \
            or "score over" in blob or "score under" in blob:
        pre = re.split(r"\bo/u\b|over/under|\bover\b|\bunder\b", q)[0].strip()
        return "team_total" if pre.strip(" :") else "total"
    if "both teams" in blob or "btts" in g:
        return "btts"
    if re.search(r"\bwin\b", blob) or re.search(
            r"advance|qualify|reach|lift|champion|title|relegat", blob):
        return "futures_adv"
    return "other"


def load_modelable_clubs():
    """Clubs with model coverage: Big-5 snapshot + Championship + Eredivisie."""
    clubs, sources = {}, []
    ptr = {}
    try:
        ptr = json.load(open(SNAPSHOT_POINTER))
        sources.append({"file": SNAPSHOT_POINTER, "target": ptr.get("target")})
    except Exception as e:  # noqa: BLE001
        sources.append({"file": SNAPSHOT_POINTER, "error": repr(e)})
    for path, label in ((BIG5_XG, "big5"), (CHAMP_XG, "championship"),
                        (ERE_XG, "eredivisie")):
        try:
            d = json.load(open(path))
            n = 0
            for blk in d:
                for tid, t in (d[blk].get("teams") or {}).items():
                    title = str(t.get("title") or "").strip()
                    if title:
                        key = norm_name(title)
                        if key:
                            clubs.setdefault(key, {"title": title, "leagues": set()})
                            clubs[key]["leagues"].add(blk.rsplit("_20", 1)[0])
                            n += 1
            sources.append({"file": path, "role": label, "team_entries": n})
        except Exception as e:  # noqa: BLE001
            sources.append({"file": path, "role": label, "error": repr(e)})
    for c in clubs.values():
        c["leagues"] = sorted(c["leagues"])
    return clubs, sources, ptr


def main():
    print("UTC now:", datetime.now(timezone.utc).isoformat(), flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    # ---- modelable club universe (STOP check inputs) ----
    clubs, club_sources, pointer = load_modelable_clubs()
    print("modelable club universe: %d clubs (Big-5 + Championship + Eredivisie)"
          % len(clubs), flush=True)

    # ---- ESPN cross-check ----
    espn = espn_fixtures()
    json.dump(espn, open(f"{OUTDIR}/espn_fixtures_43.json", "w"), indent=1)
    espn_index = []  # (norm_home, norm_away, date, league, name, note, status)
    n_espn = 0
    print("\nESPN slate (Americas leagues + Monday-early Euro check):", flush=True)
    for date, day in espn.items():
        for lg, evs in day.items():
            for ev in (evs if isinstance(evs, list) else []):
                th = (ev["teams"].get("home") or {}).get("name")
                ta = (ev["teams"].get("away") or {}).get("name")
                n_espn += 1
                espn_index.append((norm_name(th), norm_name(ta),
                                   (ev.get("date") or ""), lg,
                                   ev.get("name") or "", ev.get("note") or "",
                                   ev.get("status") or ""))
                print("  %-26s %-30s vs %-30s %s %s %s" % (
                    lg, str(th)[:28], str(ta)[:28], ev.get("date") or "",
                    ("[" + str(ev.get("note")) + "]") if ev.get("note") else "",
                    ev.get("status") or ""), flush=True)
    print("ESPN slate size: %d games" % n_espn, flush=True)

    # ---- Gamma sweeps ----
    sweeps = [("date-volume", "volume24hr", "false",
               {"start_date_min": LO, "start_date_max": HI}),
              ("date-liquidity", "liquidity", "false",
               {"start_date_min": LO, "start_date_max": HI}),
              ("date-startdate-desc", "startDate", "false",
               {"start_date_min": LO, "start_date_max": HI}),
              ("date-startdate-asc", "startDate", "true",
               {"start_date_min": LO, "start_date_max": HI})]
    for t in TAG_SWEEPS:
        sweeps.append(("tag-" + t, "volume24hr", "false", {"tag_slug": t}))
    seen, sweep_log = {}, []
    for label, order, ascending, extra in sweeps:
        try:
            evs = sweep(order, extra, ascending)
        except Exception as e:  # noqa: BLE001
            print("sweep", label, "FAILED", repr(e), flush=True)
            sweep_log.append({"label": label, "error": repr(e)})
            continue
        n = 0
        for e in evs:
            try:
                slim = slim_event(e)
            except Exception:  # noqa: BLE001
                continue
            if not in_range(slim, LO, HI):
                sd = norm_ts(e.get("startDate"))
                if not (sd and LO <= sd <= HI and slim["markets"]):
                    continue
            n += 1
            if slim["id"] not in seen:
                seen[slim["id"]] = slim
        print("sweep %-26s total=%4d in_window=%d unique=%d" % (
            label, len(evs), n, len(seen)), flush=True)
        sweep_log.append({"label": label, "total": len(evs), "in_window": n})
        time.sleep(1.0)

    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")
              and LO <= e["kick"] <= HI]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(f"{OUTDIR}/events_window_43.json", "w"), indent=1)
    print("\nunique open soccer events with in-window kickoff: %d" % len(events), flush=True)

    tag_census = {}
    for e in events:
        for t in e["tags"]:
            tag_census[t] = tag_census.get(t, 0) + 1
    print("tag census (in-window soccer events):", flush=True)
    for t, c in sorted(tag_census.items(), key=lambda kv: -kv[1]):
        print("  %-34s %d" % (t, c), flush=True)

    # ---- classify: Americas in-scope vs euro slippage vs other ----
    def espn_match(title):
        base = re.split(r"\s+-\s+", title or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        a = norm_name(parts[0]) if parts else ""
        b = norm_name(parts[1]) if len(parts) > 1 else ""
        if not a or not b:
            return None
        for nh, na, dte, lg, name, note, status in espn_index:
            if (a in nh or nh in a or a in na or na in a) and \
               (b in nh or nh in b or b in na or na in b):
                return {"league": lg, "espn_name": name, "date": dte,
                        "note": note, "status": status}
        return None

    americas, euro_slip, other_league = [], [], []
    for e in events:
        tags = set(e["tags"])
        league_tags = [(t, LEAGUE_TAG_MAP[t]) for t in tags if t in LEAGUE_TAG_MAP]
        women = bool(tags & WOMEN_TAGS)
        em = espn_match(e.get("title"))
        league, src = None, None
        if league_tags:
            league = sorted(set(l for _, l in league_tags))[0]
            src = "tag:" + ",".join(sorted(t for t, _ in league_tags))
        if league is None and em:
            lg_em = em["league"]
            src = "espn-match"
            if lg_em in ("Championship", "Ligue 1"):
                league, src = lg_em, "espn-match-euro"
            else:
                league = lg_em
        if league is None:
            if tags & EURO_TAGS:
                euro_slip.append(e)
            else:
                other_league.append(e)
            continue
        if league in ("Championship", "Ligue 1"):
            euro_slip.append(e)
            continue
        friendly = bool(FRIENDLY_PAT.search(
            " ".join(filter(None, [e.get("title"), e.get("description_excerpt")]))))
        americas.append({"event": e, "league": league, "league_src": src,
                         "women": women, "friendly": friendly, "espn": em})

    print("\nin-scope Americas events: %d | euro-tagged in-window: %d | other/none: %d"
          % (len(americas), len(euro_slip), len(other_league)), flush=True)
    for e in euro_slip:
        print("  EURO-SLIP? %s %s tags=%s" % (
            e["kick"], (e.get("title") or "")[:60], e["tags"]), flush=True)
    for e in other_league:
        print("  OTHER    %s %s tags=%s" % (
            e["kick"], (e.get("title") or "")[:60], e["tags"]), flush=True)

    # ---- group into fixtures by match ----
    def match_key(title):
        base = re.split(r"\s+-\s+", title or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        a = norm_name(parts[0]) if parts else ""
        b = norm_name(parts[1]) if len(parts) > 1 else ""
        return a + "|" + b if a and b else "slug:" + str(title)

    fixtures = {}
    for a in americas:
        e = a["event"]
        mk = match_key(e.get("title"))
        f = fixtures.setdefault(mk, {
            "match": re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0],
            "league": a["league"], "league_src": set(), "kickoff_utc": e["kick"],
            "event_ids": [], "women_flag": False, "friendly_flag": False,
            "espn": None, "liq_event_usd": 0.0, "vol24": 0.0,
            "markets": [], "tags": set()})
        f["league_src"].add(a["league_src"])
        f["event_ids"].append(e["id"])
        f["women_flag"] = f["women_flag"] or a["women"]
        f["friendly_flag"] = f["friendly_flag"] or a["friendly"]
        if a["espn"]:
            f["espn"] = a["espn"]
        try:
            f["liq_event_usd"] += float(e.get("liq") or 0)
        except Exception:  # noqa: BLE001
            pass
        try:
            f["vol24"] += float(e.get("vol24") or 0)
        except Exception:  # noqa: BLE001
            pass
        f["kickoff_utc"] = min(f["kickoff_utc"], e["kick"]) if f["kickoff_utc"] else e["kick"]
        f["markets"].extend(e["markets"])
        f["tags"].update(e["tags"])

    board = []
    for mk, f in fixtures.items():
        f["league_src"] = sorted(f["league_src"])
        f["tags"] = sorted(f["tags"])
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        f["kickoff_status_at_scan"] = ("PRE-KICK" if now_utc < f["kickoff_utc"]
                                       else "ALREADY KICKED")
        board.append(f)
    board.sort(key=lambda f: (f["kickoff_utc"], f["match"]))
    print("\nAmericas board fixtures: %d" % len(board), flush=True)

    # ---- board rows: prices, CLOB books, anomaly flags ----
    ML_KINDS = ("ml_win", "ml_draw", "spread", "total", "team_total", "btts")
    anomalies = []
    for f in board:
        mkts = sorted(f["markets"], key=lambda m: -float(m.get("liq") or 0))
        del f["markets"]  # raw events keep full markets; board keeps rows
        rows, kinds = [], {}
        book_budget = 36
        draw_yes = None
        win_yes = []
        for m in mkts[:24]:
            kind = classify_kind(m)
            kinds[kind] = kinds.get(kind, 0) + 1
            outs, toks, prices = m.get("outcomes") or [], m.get("tokens") or [], m.get("prices") or []
            need_book = kind in ML_KINDS and book_budget > 0
            side_rows = []
            for i in range(min(len(outs), len(toks))):
                gp = float(prices[i]) if i < len(prices) else None
                if kind == "ml_draw" and outs[i].lower() == "yes":
                    draw_yes = gp if gp is not None else draw_yes
                if kind == "ml_win" and outs[i].lower() == "yes":
                    win_yes.append(gp)
                if not need_book:
                    side_rows.append({
                        "outcome": outs[i], "token": str(toks[i]),
                        "gamma_price": gp,
                        "gamma_best_bid": m.get("bestBid"),
                        "gamma_best_ask": m.get("bestAsk"),
                        "clob": "skipped (budget)"})
                    continue
                book = fetch_book(str(toks[i]))
                if book is None:
                    side_rows.append({
                        "outcome": outs[i], "token": str(toks[i]),
                        "gamma_price": gp,
                        "gamma_best_bid": m.get("bestBid"),
                        "gamma_best_ask": m.get("bestAsk"),
                        "clob": "no book (dead token or fetch failed)"})
                    book_budget -= 1
                    continue
                book_budget -= 1
                w250 = gates.walk_book(book["asks"], side="ask", notional=250.0)
                w150 = gates.walk_book(book["asks"], side="ask", notional=150.0)
                bid, ask = book["best_bid"], book["best_ask"]
                mid = round((bid + ask) / 2, 4) if (bid is not None and ask is not None) else None
                side_rows.append({
                    "outcome": outs[i], "token": str(toks[i]),
                    "gamma_price": gp,
                    "gamma_best_bid": m.get("bestBid"),
                    "gamma_best_ask": m.get("bestAsk"),
                    "clob_best_bid": bid, "clob_best_ask": ask,
                    "mid_implied": mid,
                    "vwap_250": w250.vwap, "fill_250": w250.filled,
                    "vwap_150": w150.vwap, "fill_150": w150.filled,
                    "depth_2c_usd": w250.depth_near2c})
            if side_rows:
                rows.append({
                    "market_id": m["id"], "question": m["q"], "kind": kind,
                    "line": m.get("line"), "gameStartTime": m.get("gameStartTime"),
                    "liq_gamma_usd": float(m.get("liq") or 0),
                    "vol24": float(m.get("vol24") or 0),
                    "sides": side_rows,
                    "no_model_coverage": "NO MODEL COVERAGE - report only, no entry"})

        # ---- anomaly detection ----
        flags = []
        if f["women_flag"]:
            flags.append("WOMENS_LEAGUE_LOOKALIKE - never enterable")
        if f["friendly_flag"]:
            flags.append("FRIENDLY_LOOKALIKE - never enterable")
        if draw_yes is not None and draw_yes >= 0.85 and \
                all((w is None or w <= 0.15) for w in win_yes) and win_yes:
            flags.append("CANCELLATION-PRICED DRAW (draw YES >= 0.85, win sides <= 0.15;"
                         " r39 Al-Ettifaq pattern) - not a normal result market")
        for r in rows:
            gp = [s.get("gamma_price") for s in r["sides"]]
            dead_book = all(not s.get("clob_best_bid") and not s.get("clob_best_ask")
                            for s in r["sides"])
            if r["vol24"] == 0 and dead_book and \
                    sorted(gp) and abs(gp[0] - 0.5) <= 0.011 and abs(gp[-1] - 0.5) <= 0.011:
                r["anomaly"] = "PLACEHOLDER 0.49/0.51 no-volume dead book"
            spreads = [s["clob_best_ask"] - s["clob_best_bid"]
                       for s in r["sides"]
                       if s.get("clob_best_bid") is not None and s.get("clob_best_ask") is not None]
            if spreads and max(spreads) >= 0.10:
                r["anomaly"] = (r.get("anomaly", "") + " | " if r.get("anomaly") else "") + \
                    "WIDE SPREAD >= 10c (max %.3f)" % max(spreads)
            for s in r["sides"]:
                if s.get("mid_implied") is not None and s.get("gamma_price") is not None \
                        and abs(s["mid_implied"] - s["gamma_price"]) > 0.05:
                    r.setdefault("anomaly", "")
                    if "GAMMA-VS-CLOB divergence > 5c" not in r["anomaly"]:
                        r["anomaly"] = (r["anomaly"] + " | " if r["anomaly"] else "") + \
                            "GAMMA-VS-CLOB divergence > 5c"
        if f["vol24"] == 0:
            flags.append("ZERO 24h volume on all listing events")
        f["anomaly_flags"] = flags
        f["market_kinds"] = kinds
        f["rows"] = rows
        for fl in flags:
            anomalies.append({"match": f["match"], "league": f["league"],
                              "kickoff_utc": f["kickoff_utc"], "flag": fl})
        for r in rows:
            if r.get("anomaly"):
                anomalies.append({"match": f["match"], "league": f["league"],
                                  "kickoff_utc": f["kickoff_utc"],
                                  "market_id": r["market_id"],
                                  "kind": r["kind"], "flag": r["anomaly"],
                                  "question": r["question"]})

    # ---- /markets/{id} verification (top-3 per fixture by liq) ----
    verifications = []
    for f in board:
        top = sorted(f["rows"], key=lambda r: -r["liq_gamma_usd"])[:3]
        for r in top:
            vm = fetch_market(r["market_id"])
            if not isinstance(vm, dict):
                verifications.append({"market_id": r["market_id"], "ok": False,
                                      "error": "fetch failed"})
                continue
            gs, ed = norm_ts(vm.get("gameStartTime")), norm_ts(vm.get("endDate"))
            kick_ok = None
            if gs and f["kickoff_utc"]:
                kick_ok = abs((
                    datetime.fromisoformat(gs.replace("Z", "+00:00")) -
                    datetime.fromisoformat(f["kickoff_utc"].replace("Z", "+00:00"))
                ).total_seconds()) <= 3600
            endd_ok = None
            if ed and gs:
                dd = (datetime.fromisoformat(ed.replace("Z", "+00:00")) -
                      datetime.fromisoformat(gs.replace("Z", "+00:00"))).total_seconds()
                endd_ok = 0 <= dd <= 60 * 60 * 30
            qtxt = strip_accents(str(vm.get("question") or "").lower())
            team_a = norm_name(re.split(
                r"\s+vs\.?\s+|\s+at\s+",
                re.split(r"\s+-\s+", f["match"], maxsplit=1)[0], maxsplit=1)[0])
            verifications.append({
                "market_id": str(vm.get("id")), "ok": True,
                "question": vm.get("question"),
                "closed": vm.get("closed"), "active": vm.get("active"),
                "gameStartTime": gs, "endDate": ed,
                "kickoff_matches_event": kick_ok,
                "endDate_after_kick_within_30h": endd_ok,
                "question_names_fixture_team": bool(team_a and team_a in qtxt)})

    # ---- modelable-club STOP check ----
    modelable_alerts = []
    for f in board:
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", f["match"], maxsplit=1)
        for p in parts:
            key = norm_name(p)
            if key and key in clubs:
                modelable_alerts.append({
                    "match": f["match"], "league": f["league"],
                    "kickoff_utc": f["kickoff_utc"], "club": clubs[key]["title"],
                    "club_leagues": clubs[key]["leagues"],
                    "action": "STOP - dispatch rule: unexpected modelable club;"
                              " report instead of modeling"})

    # ---- ESPN-only fixtures (in window, no Gamma listing) ----
    gamma_keys = set()
    for f in board:
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+",
                         re.split(r"\s+-\s+", f["match"], maxsplit=1)[0], maxsplit=1)
        if len(parts) == 2:
            gamma_keys.add(frozenset([norm_name(parts[0]), norm_name(parts[1])]))
    espn_only = []
    for nh, na, dte, lg, name, note, status in espn_index:
        if not (nh and na):
            continue
        if dte and LO <= dte <= HI and lg not in ("Championship", "Ligue 1"):
            if frozenset([nh, na]) not in gamma_keys:
                espn_only.append({"league": lg, "date": dte, "name": name,
                                  "note": note, "status": status})

    euro_monday_note = []
    for nh, na, dte, lg, name, note, status in espn_index:
        if lg in ("Championship", "Ligue 1") and dte:
            euro_monday_note.append({"league": lg, "date": dte, "name": name})

    n_rows = sum(len(f["rows"]) for f in board)
    n_bad_verify = sum(1 for v in verifications
                       if not v.get("ok") or v.get("closed") is True
                       or v.get("kickoff_matches_event") is False
                       or v.get("endDate_after_kick_within_30h") is False)
    print("\nboard fixtures=%d rows=%d verifications=%d bad=%d anomalies=%d STOP_alerts=%d"
          % (len(board), n_rows, len(verifications), n_bad_verify,
             len(anomalies), len(modelable_alerts)), flush=True)
    if modelable_alerts:
        print("!!! MODELABLE CLUB ALERT - STOP AND REPORT:", flush=True)
        for a in modelable_alerts:
            print("   ", json.dumps(a), flush=True)

    # ---- raw output ----
    raw = {
        "round": 43, "scan": "americas-overnight-tail", "paper_only": True,
        "generated_utc": SCAN_TS,
        "window_utc": {"lo": LO, "hi": HI},
        "coverage_verdict": {
            "fotmob_adapter_leagues": ["Championship(48)", "Eredivisie(57)"],
            "xg_snapshot_leagues": ["EPL", "La_liga", "Serie_A", "Bundesliga",
                                    "Ligue_1"],
            "in_scope_leagues_covered": [],
            "conclusion": ("NO in-scope league (Argentina Primera/Brasileirao/"
                           "Colombia/Chile/Ecuador/Uruguay/Paraguay/Bolivia/MLS/"
                           "Liga MX and other Americas leagues) has adapter or "
                           "snapshot coverage -> BOARD-ONLY scan, every row "
                           "labeled NO MODEL COVERAGE - report only, no entry. "
                           "No ratings fabricated; only gates.walk_book used.")},
        "provenance": {
            "repo_commit": REPO_COMMIT,
            "library": "polymarket_alpha_lab.papersim gates.walk_book only",
            "selfcheck": "not needed (no modeling, per dispatch)",
            "understat_pointer": pointer,
            "modelable_club_sources": club_sources,
            "modelable_club_count": len(clubs),
            "espn_leagues_queried": ESPN_LEAGUES,
            "espn_dates": ESPN_DATES, "espn_slate_games": n_espn,
            "gamma_sweep_log": sweep_log,
            "note_ids_param_broken": "Gamma /markets?ids= list param is BROKEN;"
                                     " all verifications via /markets/{id}"},
        "tag_census_in_window": tag_census,
        "espn_fixtures": espn,
        "euro_slippage_events": [
            {"kick": e["kick"], "title": e.get("title"), "id": e["id"],
             "tags": e["tags"]} for e in euro_slip],
        "other_tag_events": [
            {"kick": e["kick"], "title": e.get("title"), "id": e["id"],
             "tags": e["tags"]} for e in other_league],
        "board_fixtures": board,
        "market_verifications": verifications,
        "verification_bad_count": n_bad_verify,
        "modelable_club_alerts": modelable_alerts,
        "anomalies": anomalies,
        "espn_only_fixtures_in_window": espn_only,
        "euro_monday_kickoffs_documented": euro_monday_note,
    }
    json.dump(raw, open(OUT, "w"), indent=1)
    print("\nwrote", OUT, flush=True)

    # ---- summary board ----
    fx_summary = []
    for f in board:
        ml_rows = [r for r in f["rows"] if r["kind"] in ("ml_win", "ml_draw")]
        side_brief = []
        for r in ml_rows[:6]:
            for s in r["sides"][:3]:
                gp = s.get("gamma_price")
                cb, ca = s.get("clob_best_bid"), s.get("clob_best_ask")
                side_brief.append({
                    "kind": r["kind"], "outcome": s.get("outcome"),
                    "gamma_price": gp,
                    "clob_bid": cb, "clob_ask": ca,
                    "vwap_250_ask": s.get("vwap_250"),
                    "fill_250": s.get("fill_250"),
                    "depth_2c_usd": s.get("depth_2c_usd")})
        top_liq_row = max(f["rows"], key=lambda r: r["liq_gamma_usd"]) if f["rows"] else None
        spread_note = None
        for r in f["rows"]:
            sp = [s["clob_best_ask"] - s["clob_best_bid"]
                  for s in r["sides"]
                  if s.get("clob_best_bid") is not None and s.get("clob_best_ask") is not None]
            if sp:
                spread_note = {"market_kind": r["kind"],
                               "min_spread_c": round(min(sp) * 100, 1),
                               "max_spread_c": round(max(sp) * 100, 1)}
                break
        fx_summary.append({
            "match": f["match"], "league": f["league"], "kickoff_utc": f["kickoff_utc"],
            "kickoff_status_at_scan": f["kickoff_status_at_scan"],
            "liq_event_usd": round(f["liq_event_usd"], 2),
            "vol24_usd": round(f["vol24"], 2),
            "n_events": len(f["event_ids"]), "event_ids": f["event_ids"],
            "market_kinds": f["market_kinds"],
            "key_prices": side_brief, "spread_quality": spread_note,
            "anomaly_flags": f["anomaly_flags"],
            "espn_cross": (f["espn"] or {}).get("league"),
            "coverage": "NO MODEL COVERAGE - report only, no entry"})

    summary = {
        "round": 43, "scan": "americas-overnight-tail", "paper_only": True,
        "generated_utc": SCAN_TS,
        "window_utc": {"lo": LO, "hi": HI},
        "coverage_statement": (
            "FotmobLeague enum = {CHAMPIONSHIP, EREDIVISIE} only; xG snapshot "
            "covers Big-5 only. Argentina Primera, Brasileirao, Colombia, Chile, "
            "Ecuador, Uruguay, Paraguay, Bolivia, MLS, Liga MX and any other "
            "league in this window have NO model coverage: BOARD-ONLY report, "
            "no entry, no fabricated ratings. Stake $0."),
        "decision": ("ENTER NOTHING. Board-only scan ($0 of budget): no in-scope "
                     "league is modelable; every fixture is report-only."),
        "modelable_club_alerts": modelable_alerts,
        "euro_slippage_check": {
            "euro_tagged_events_in_window": raw["euro_slippage_events"],
            "euro_monday_kickoffs_documented": euro_monday_note,
            "note": ("Championship/Ligue 1 Monday games kick 19:45Z+ Mon "
                     "(outside 05:30Z window end); any European-tagged event "
                     "inside the window would be listed above.")},
        "enumeration": {
            "gamma_sweeps": sweep_log,
            "unique_in_window_soccer_events": len(events),
            "board_fixtures": len(board),
            "espn_slate_games": n_espn,
            "espn_only_fixtures_in_window": espn_only},
        "fixtures": fx_summary,
        "anomalies": anomalies,
        "verification": {"checked": len(verifications), "bad": n_bad_verify},
    }
    json.dump(summary, open(BOARD_OUT, "w"), indent=1)
    print("wrote", BOARD_OUT, flush=True)


if __name__ == "__main__":
    main()
