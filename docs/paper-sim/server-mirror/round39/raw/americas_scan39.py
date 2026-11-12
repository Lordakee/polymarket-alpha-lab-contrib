"""ROUND-39B paper-sim soccer scan: AMERICAS + REST OF WORLD, 48h window.

Scope: MLS Cup Playoffs, Brasileirao, Liga MX, Argentina Primera, plus any
other non-European soccer Polymarket lists (Saudi Pro League, J-League,
A-League, CONMEBOL) kicking 2026-11-06T13:30Z .. 2026-11-08T23:59:59Z.

COVERAGE VERDICT (checked before writing this script, per dispatch):
  - FotmobLeague enum in src/polymarket_alpha_lab/papersim/fotmob.py has
    ONLY Championship (48) and Eredivisie (57). MLS/Brasileirao/Liga MX/
    Argentina/Saudi/J-League/A-League are NOT adapter-covered.
  - ~/paper-sim/understat_latest.json -> round36/raw/xg_fotmob_big5_merged.json
    contains only EPL/La_liga/Serie_A/Bundesliga/Ligue_1 blocks (2025+2026).
  => NO model coverage for ANY in-scope league. Per dispatch rule 3 this is
     a BOARD-ONLY scan: every row is labeled "NO MODEL COVERAGE - report
     only, no entry". No model probabilities are fabricated. The only
     library call used is gates.walk_book (pure book math, no model).

Paper only: no real orders, no DB writes, no credentials.
Library selfcheck (run 2026-11-06 before this scan): PASS 10/10 @ 5bdae2e3.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import gates  # noqa: E402  (walk_book only)

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"
HOME = "/home/ubuntu/paper-sim"
OUTDIR = f"{HOME}/round39/raw"
OUT = f"{OUTDIR}/americas_scan.json"
SCAN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LO = "2026-11-06T13:30:00Z"          # kickoff window lo (dispatch)
HI = "2026-11-08T23:59:59Z"          # kickoff window hi (dispatch)

ESPN_LEAGUES = {
    "usa.1": "MLS",
    "bra.1": "Brasileirao",
    "mex.1": "Liga MX",
    "arg.1": "Argentina Primera",
    "sau.1": "Saudi Pro League",
    "jpn.1": "J-League",
    "aus.1": "A-League",
    "conmebol.libertadores": "Copa Libertadores",
    "conmebol.sudamericana": "Copa Sudamericana",
}
ESPN_DATES = ("20261106", "20261107", "20261108")

# League tag slugs (unknown soccer tags are printed and classified OTHER).
LEAGUE_TAG_MAP = {
    "mls": "MLS", "mls-cup": "MLS Cup Playoffs",
    "mls-cup-playoffs": "MLS Cup Playoffs", "mls-playoffs": "MLS Cup Playoffs",
    "mls-cup-2026": "MLS Cup Playoffs",
    "brasileirao": "Brasileirao", "brazilian-serie-a": "Brasileirao",
    "brasileirao-serie-a": "Brasileirao", "serie-a-brasil": "Brasileirao",
    "liga-mx": "Liga MX", "ligamx": "Liga MX", "futbol-mexicano": "Liga MX",
    "mexican-league": "Liga MX", "liga-mx-apertura": "Liga MX",
    "argentina-primera": "Argentina Primera", "liga-profesional": "Argentina Primera",
    "argentine-league": "Argentina Primera", "primera-division-argentina": "Argentina Primera",
    "saudi-pro-league": "Saudi Pro League", "saudi-league": "Saudi Pro League",
    "j-league": "J-League", "jleague": "J-League", "j1-league": "J-League",
    "a-league": "A-League", "aleague": "A-League", "a-league-men": "A-League",
    "libertadores": "Copa Libertadores", "conmebol-libertadores": "Copa Libertadores",
    "sudamericana": "Copa Sudamericana", "conmebol-sudamericana": "Copa Sudamericana",
}
WOMEN_TAGS = {"nwsl", "womens-soccer", "liga-mx-femenil", "nwsoccer",
              "womens-football", "feminine", "libertadores-femenina",
              "w-league", "a-league-women"}

RULE_KEYWORDS = ("extra time", "penalt", "shootout", "shoot-out",
                 "90 minutes", "regulation", "aggregate", "two-leg", "two leg",
                 "away goals", "tiebreaker")


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
        "rc", "ud", "us", "as", "sv", "cd", "ca"}]
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


def fetch_window(lo, hi, sweeps):
    seen = {}
    for label, order, ascending, extra in sweeps:
        try:
            evs = sweep(order, extra, ascending)
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
                continue
            n += 1
            if slim["id"] not in seen:
                seen[slim["id"]] = slim
        print("sweep %-24s total=%4d in_window=%d unique=%d" % (
            label, len(evs), n, len(seen)), flush=True)
        time.sleep(1.0)
    return seen


BOOK_CACHE = {}


def fetch_book(token):
    if token in BOOK_CACHE:
        return BOOK_CACHE[token]
    try:
        b = get(CLOB + "/book?token_id=" + token)
        asks = [(float(l["price"]), float(l["size"])) for l in b.get("asks", [])]
        bids = [(float(l["price"]), float(l["size"])) for l in b.get("bids", [])]
        book = {"asks": asks, "bids": bids,
                "best_ask": min((p for p, _ in asks), default=None),
                "best_bid": max((p for p, _ in bids), default=None)}
    except Exception as e:  # noqa: BLE001
        print("book err", token, repr(e), flush=True)
        book = None
    BOOK_CACHE[token] = book
    time.sleep(0.25)
    return book


MKT_CACHE = {}


def fetch_market(mid):
    if mid in MKT_CACHE:
        return MKT_CACHE[mid]
    try:
        m = get(BASE + "/markets/" + str(mid))
    except Exception as e:  # noqa: BLE001
        print("market verify err", mid, repr(e), flush=True)
        m = None
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
    if re.search(r"\bwin\b", blob) or re.search(r"advance|qualify|reach|lift|champion|title|relegat", blob):
        return "futures_adv"
    return "other"


def rule_scan(text):
    """Extract resolution-rule evidence from a description text."""
    t = re.sub(r"\s+", " ", str(text or "").lower())
    hits = {}
    for kw in RULE_KEYWORDS:
        for mth in re.finditer(re.escape(kw), t):
            ctx = t[max(0, mth.start() - 120):mth.end() + 160].strip()
            hits.setdefault(kw, []).append(ctx)
            if len(hits[kw]) >= 3:
                break
    return {k: v for k, v in hits.items() if k in (
        "extra time", "penalt", "shootout", "shoot-out", "90 minutes",
        "regulation", "aggregate", "away goals")}


def main():
    print("UTC now:", datetime.now(timezone.utc).isoformat(), flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    espn = espn_fixtures()
    json.dump(espn, open(f"{OUTDIR}/espn_fixtures_r39_americas.json", "w"), indent=1)
    print("\nESPN slate (in-scope leagues):", flush=True)
    n_espn = 0
    espn_index = []  # (norm_home, norm_away, date, league, name, note)
    for date, day in espn.items():
        for lg, evs in day.items():
            for ev in (evs if isinstance(evs, list) else []):
                th = ev["teams"].get("home", {}).get("name")
                ta = ev["teams"].get("away", {}).get("name")
                print("  %-18s %-28s vs %-28s %s %s" % (
                    lg, str(th), str(ta), ev.get("date") or "",
                    ("[" + str(ev.get("note")) + "]") if ev.get("note") else ""), flush=True)
                n_espn += 1
                espn_index.append((norm_name(th), norm_name(ta),
                                   (ev.get("date") or "")[:10], lg,
                                   ev.get("name") or "", ev.get("note") or ""))
    print("ESPN slate size: %d games" % n_espn, flush=True)

    sweeps = [
        ("date-volume", "volume24hr", "false",
         {"start_date_min": LO, "start_date_max": HI}),
        ("date-liquidity", "liquidity", "false",
         {"start_date_min": LO, "start_date_max": HI}),
        ("date-startdate-desc", "startDate", "false",
         {"start_date_min": LO, "start_date_max": HI}),
        ("date-startdate-asc", "startDate", "true",
         {"start_date_min": LO, "start_date_max": HI}),
        ("tag-soccer-vol", "volume24hr", "false", {"tag_slug": "soccer"}),
        ("tag-soccer-liq", "liquidity", "false", {"tag_slug": "soccer"}),
        ("tag-mls", "volume24hr", "false", {"tag_slug": "mls"}),
        ("tag-liga-mx", "volume24hr", "false", {"tag_slug": "liga-mx"}),
    ]
    seen = fetch_window(LO, HI, sweeps)
    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
    json.dump(events, open(f"{OUTDIR}/events_window_39b.json", "w"), indent=1)
    print("\nunique open soccer events with in-window kickoff:", len(events), flush=True)

    tag_inventory = {}
    for e in events:
        for t in e["tags"]:
            tag_inventory[t] = tag_inventory.get(t, 0) + 1
    print("\ntag inventory (soccer events in window):", flush=True)
    for t, c in sorted(tag_inventory.items(), key=lambda kv: -kv[1]):
        print("  %-34s %d" % (t, c), flush=True)

    def espn_match(title):
        base = re.split(r"\s+-\s+", title or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        a = norm_name(parts[0]) if parts else ""
        b = norm_name(parts[1]) if len(parts) > 1 else ""
        if not a or not b:
            return None
        for nh, na, dte, lg, name, note in espn_index:
            if (a in nh or nh in a or a in na or na in a) and \
               (b in nh or nh in b or b in na or na in b):
                return {"league": lg, "espn_name": name, "date": dte, "note": note}
        return None

    fixtures = []
    for e in events:
        tags = set(e["tags"])
        league_tags = [(t, LEAGUE_TAG_MAP[t]) for t in tags if t in LEAGUE_TAG_MAP]
        women = bool(tags & WOMEN_TAGS)
        em = espn_match(e.get("title"))
        league = None
        src = None
        if league_tags:
            league = sorted(set(l for _, l in league_tags))[0]
            src = "tag:" + ",".join(t for t, _ in league_tags)
        if league is None and em:
            league, src = em["league"], "espn-match"
        if league is None:
            continue  # out of Americas/ROW scope (Europe etc. -> agents A/B)
        kick = e["kick"]
        fixtures.append({
            "event_id": e["id"], "title": e["title"], "kickoff_utc": kick,
            "league": league, "league_src": src, "women_flag": women,
            "espn": em, "tags": e["tags"],
            "in_window": LO <= kick <= HI,
            "liq_event": e.get("liq"), "vol24": e.get("vol24"),
            "n_markets": len(e["markets"]),
            "event_description_excerpt": e.get("description_excerpt"),
            "_ev": e})

    fixtures.sort(key=lambda f: (f["kickoff_utc"], f["title"]))
    print("\nIN-SCOPE (Americas/ROW) fixtures:", flush=True)
    for f in fixtures:
        print("  %-18s %-10s kick=%s mkt=%2d liq=%s %s%s" % (
            f["league"], f["event_id"], f["kickoff_utc"], f["n_markets"],
            f["liq_event"], (f["title"] or "")[:60],
            " [WOMEN]" if f["women_flag"] else ""), flush=True)

    # ---- board rows + books + verification + rules ----
    board, verifications, rules_evidence = [], [], []
    for f in fixtures:
        rows = []
        mkts = sorted(f["_ev"]["markets"],
                      key=lambda m: -(float(m.get("liq") or 0)))
        for m in mkts[:24]:
            kind = classify_kind(m)
            outs = m.get("outcomes") or []
            toks = m.get("tokens") or []
            prices = m.get("prices") or []
            side_rows = []
            for i in range(min(len(outs), len(toks))):
                book = fetch_book(str(toks[i]))
                if book is None:
                    continue
                ask_levels = [(p, s) for p, s in book["asks"]]
                w250 = gates.walk_book(ask_levels, side="ask", notional=250.0)
                w150 = gates.walk_book(ask_levels, side="ask", notional=150.0)
                bid = book["best_bid"]
                ask = book["best_ask"]
                mid = round((bid + ask) / 2, 4) if (bid is not None and ask is not None) else None
                side_rows.append({
                    "outcome": outs[i], "token": str(toks[i]),
                    "best_bid": bid, "best_ask": ask, "mid_implied": mid,
                    "gamma_price": float(prices[i]) if i < len(prices) else None,
                    "vwap_250": w250.vwap, "fill_250": w250.filled,
                    "vwap_150": w150.vwap, "fill_150": w150.filled,
                    "depth_2c_usd": w250.depth_near2c})
            if not side_rows:
                continue
            rows.append({
                "market_id": m["id"], "question": m["q"], "group": m.get("group"),
                "kind": kind, "line": m.get("line"),
                "gameStartTime": m.get("gameStartTime"),
                "liq_gamma_usd": float(m.get("liq") or 0),
                "vol24": float(m.get("vol24") or 0),
                "sides": side_rows,
                "no_model_coverage": "NO MODEL COVERAGE - report only, no entry"})
        f.pop("_ev", None)
        board.append({"fixture": f, "rows": rows})

        # /markets/{id} verification + rules text for the top markets
        for m in mkts[:12]:
            vm = fetch_market(m["id"])
            if not isinstance(vm, dict):
                verifications.append({"market_id": m["id"], "ok": False,
                                      "error": "fetch failed"})
                continue
            gs = norm_ts(vm.get("gameStartTime"))
            ed = norm_ts(vm.get("endDate"))
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
            base_teams = strip_accents(
                re.split(r"\s+-\s+", f["title"] or "", maxsplit=1)[0].lower())
            team_a = norm_name(re.split(r"\s+vs\.?\s+|\s+at\s+", base_teams, maxsplit=1)[0])
            qm = bool(team_a and team_a in qtxt) if team_a else None
            verifications.append({
                "market_id": str(vm.get("id")), "ok": True,
                "question": vm.get("question"),
                "closed": vm.get("closed"), "active": vm.get("active"),
                "gameStartTime": gs, "endDate": ed,
                "kickoff_matches_event": kick_ok,
                "endDate_after_kick_within_30h": endd_ok,
                "question_names_fixture_team": qm})
            rdesc = str(vm.get("description") or "")
            r = rule_scan(rdesc)
            if r:
                rules_evidence.append({
                    "market_id": str(vm.get("id")), "question": vm.get("question"),
                    "kickoff_utc": f["kickoff_utc"], "league": f["league"],
                    "rules_hits": r})

    n_rows = sum(len(b["rows"]) for b in board)
    print("\nboard fixtures: %d; board rows: %d; verifications: %d; rules-hits: %d"
          % (len(board), n_rows, len(verifications), len(rules_evidence)), flush=True)

    out = {
        "round": 39, "scan": "americas-row-48h", "paper_only": True,
        "generated_utc": SCAN_TS,
        "window_utc": {"lo": LO, "hi": HI},
        "coverage_verdict": {
            "fotmob_adapter_leagues": ["Championship(48)", "Eredivisie(57)"],
            "xg_snapshot_leagues": ["EPL", "La_liga", "Serie_A", "Bundesliga",
                                    "Ligue_1"],
            "in_scope_leagues_covered": [],
            "conclusion": ("NO in-scope league (MLS/Brasileirao/Liga MX/Argentina/"
                           "Saudi/J-League/A-League/CONMEBOL) has adapter or snapshot "
                           "coverage -> BOARD-ONLY scan, every row labeled "
                           "NO MODEL COVERAGE - report only, no entry. No ratings "
                           "fabricated; kappa bridge not used (no model side).")},
        "provenance": {
            "understat_pointer": json.load(open(f"{HOME}/understat_latest_pointer.json")),
            "library_commit": "5bdae2e3",
            "selfcheck": "PASS 10/10 (run 2026-11-06 pre-scan)",
            "espn_leagues_queried": ESPN_LEAGUES, "espn_slate_games": n_espn,
            "gamma_sweeps": [s[0] for s in sweeps]},
        "tag_inventory_soccer_window": tag_inventory,
        "espn_fixtures": espn,
        "scope_fixtures": board,
        "market_verifications": verifications,
        "playoff_rules_evidence": rules_evidence,
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nwrote", OUT, flush=True)


if __name__ == "__main__":
    main()
