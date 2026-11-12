"""Round-27 Monday scan: Serie A + La Liga + EPL + Ligue 1 (+Bundesliga check).

Paper-only scan. Window 2026-11-02T01:00Z .. 2026-11-03T01:00Z.
Pipeline identical to r26 scan_b (canonical):
  1. Gamma discovery (date window + league tag sweeps).
  2. Kickoff verification: Understat fixture list + ESPN scoreboard (20261102).
  3. 10-variant xG-Poisson via canonical papersim library (repo 7b6cdd47).
  4. CLOB $250-ask VWAP walks per market side; full frozen gate set per side.
  5. Writes round27/raw/scan_27.json.
xG base: round27 refresh if the Understat fetch landed, else r25 snapshot
(fresh through Sat Oct-31; no Monday club played Sunday).
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
from polymarket_alpha_lab.papersim import gates, soccer_model, xg  # noqa: E402

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
R27 = "/home/ubuntu/paper-sim/round27/raw/xg_understat_27.json"
R25 = "/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json"
EXPECTED_KEYS = {"EPL_2025", "EPL_2026", "La_liga_2025", "La_liga_2026",
                 "Serie_A_2025", "Serie_A_2026", "Bundesliga_2025",
                 "Bundesliga_2026", "Ligue_1_2025", "Ligue_1_2026"}
if os.path.exists(R27):
    keys = set(json.load(open(R27)).keys())
    if EXPECTED_KEYS <= keys:
        XG_PATH = R27
    else:
        XG_PATH = R25
else:
    XG_PATH = R25
OUT = "/home/ubuntu/paper-sim/round27/raw/scan_27.json"
ESPN_OUT = "/home/ubuntu/paper-sim/round27/raw/espn_fixtures_27.json"
EVENTS_OUT = "/home/ubuntu/paper-sim/round27/raw/events_window_27.json"

LO = "2026-11-02T01:00:00Z"
HI = "2026-11-03T01:00:00Z"
LEAGUE_OF_TAG = {
    "epl": "EPL", "premier-league": "EPL", "england-premier-league": "EPL",
    "bundesliga": "Bundesliga", "german-bundesliga": "Bundesliga",
    "ligue-1": "Ligue_1", "france-ligue-1": "Ligue_1", "ligue-1-uber-eats": "Ligue_1",
    "serie-a": "Serie_A", "italy-serie-a": "Serie_A", "italian-serie-a": "Serie_A",
    "sea": "Serie_A",
    "la-liga": "La_liga", "laliga": "La_liga", "spain-la-liga": "La_liga",
    "la-liga-santander": "La_liga",
}
SOCCER_TAGS = set(LEAGUE_OF_TAG) | {
    "mls", "liga-mx", "eredivisie", "championship", "efl-championship",
    "primeira-liga", "portuguese-primeira", "scottish-prem", "scottish-premiership",
    "belgian-pro-league", "belgian-first-div-a", "turkish-super-lig", "austria-bundesliga",
    "swiss-super-league", "brasileirao", "brazil-serie-a", "jupiler", "soccer",
    "ucl", "champions-league", "uefa-champions-league",
}
TEAM_ALIASES = {
    "sassuolo": "Sassuolo", "us sassuolo": "Sassuolo", "atalanta": "Atalanta",
    "atalanta bc": "Atalanta", "fiorentina": "Fiorentina", "acf fiorentina": "Fiorentina",
    "parma": "Parma Calcio 1913", "parma calcio 1913": "Parma Calcio 1913",
    "deportivo": "Deportivo La Coruna", "deportivo la coruna": "Deportivo La Coruna",
    "rc deportivo": "Deportivo La Coruna", "deportivo de la coruna": "Deportivo La Coruna",
    "deportivo a coruna": "Deportivo La Coruna", "rc deportivo a coruna": "Deportivo La Coruna",
    "osasuna": "Osasuna", "ca osasuna": "Osasuna",
    "newcastle": "Newcastle United", "newcastle united": "Newcastle United",
    "everton": "Everton",
    "lorient": "Lorient", "fc lorient": "Lorient", "brest": "Brest",
    "stade brestois": "Brest", "stade brestois 29": "Brest",
    "koln": "FC Cologne", "frankfurt": "Eintracht Frankfurt",
    "hamburg": "Hamburger SV", "union berlin": "Union Berlin",
    "leverkusen": "Bayer Leverkusen", "bayern": "Bayern Munich",
    "dortmund": "Borussia Dortmund", "gladbach": "Borussia M.Gladbach",
    "leipzig": "RasenBallsport Leipzig", "mainz": "Mainz 05", "schalke": "Schalke 04",
    "stuttgart": "VfB Stuttgart", "bremen": "Werder Bremen",
    "psg": "Paris Saint Germain", "marseille": "Marseille", "lyon": "Lyon",
    "paris fc": "Paris FC", "liverpool": "Liverpool", "arsenal": "Arsenal",
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


def canon_team(name, understat_titles):
    n = norm_name(name)
    if not n:
        return None
    for alias, full in TEAM_ALIASES.items():
        if norm_name(alias) == n:
            if full in understat_titles:
                return full
    for t in understat_titles:
        if norm_name(t) == n:
            return t
    for t in understat_titles:
        tn = norm_name(t)
        if tn and (tn in n or n in tn):
            return t
    return None


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return []
    return raw or []


def sweep(order, extra_params):
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
        if offset >= 1000:
            return out
        time.sleep(1.0)


def main():
    now = datetime.now(timezone.utc)
    print("UTC now:", now.isoformat(), "XG base:", XG_PATH, flush=True)
    snapshot = xg.load_xg_snapshot(XG_PATH)
    league_understat = {"EPL": "EPL", "Bundesliga": "Bundesliga", "Ligue_1": "Ligue_1",
                        "Serie_A": "Serie_A", "La_liga": "La_liga"}
    titles = {}
    fixtures_from_understat = {}
    for lg in league_understat:
        block = snapshot.get(f"{lg}_2026") or {}
        titles[lg] = [t.get("title") for t in (block.get("teams") or {}).values()
                      if t.get("title")]
        for row in block.get("dates") or []:
            if row.get("isResult"):
                continue
            dt = norm_ts((row.get("datetime") or "").replace(" ", "T") + "Z"
                         if row.get("datetime") else "")
            if not (LO <= dt <= HI):
                continue
            h = (row.get("h") or {}).get("title")
            a = (row.get("a") or {}).get("title")
            fixtures_from_understat[(lg, h, a)] = dt

    print("Understat in-window fixtures:", len(fixtures_from_understat), flush=True)
    for (lg, h, a), dt in sorted(fixtures_from_understat.items(), key=lambda kv: kv[1]):
        print(f"  {dt} {lg}: {h} - {a}", flush=True)

    # ---- discovery ----
    if os.path.exists(EVENTS_OUT) and time.time() - os.path.getmtime(EVENTS_OUT) < 7200:
        events = json.load(open(EVENTS_OUT))
        for e in events:
            if "kick" not in e:
                e["kick"] = min((norm_ts(m.get("gameStartTime"))
                                 for m in e["markets"] if m.get("gameStartTime")),
                                default="")
        print("loaded cached events:", len(events), flush=True)
    else:
        seen = {}
        sweeps = [
            ("date-volume", "volume24hr", {"start_date_min": "2026-11-02T00:00:00Z",
                                            "start_date_max": "2026-11-03T01:00:00Z"}),
            ("date-liquidity", "liquidity", {"start_date_min": "2026-11-02T00:00:00Z",
                                             "start_date_max": "2026-11-03T01:00:00Z"}),
            ("tag-sea", "volume24hr", {"tag_slug": "sea"}),
            ("tag-serie-a", "volume24hr", {"tag_slug": "serie-a"}),
            ("tag-laliga", "volume24hr", {"tag_slug": "laliga"}),
            ("tag-la-liga", "volume24hr", {"tag_slug": "la-liga"}),
            ("tag-epl", "volume24hr", {"tag_slug": "epl"}),
            ("tag-ligue-1", "volume24hr", {"tag_slug": "ligue-1"}),
            ("tag-bundesliga", "volume24hr", {"tag_slug": "bundesliga"}),
        ]
        for label, order, extra in sweeps:
            try:
                evs = sweep(order, extra)
            except Exception as e:  # noqa: BLE001
                print("sweep", label, "FAILED", repr(e), flush=True)
                continue
            n = 0
            for e in evs:
                mkts = e.get("markets") or []
                kos = [norm_ts(m.get("gameStartTime")) for m in mkts
                       if norm_ts(m.get("gameStartTime"))]
                in_win = any(LO <= k <= HI for k in kos)
                if not in_win and not extra.get("tag_slug"):
                    sd = norm_ts(e.get("startDate"))
                    in_win = bool(sd) and sd >= LO and sd <= HI and bool(kos)
                if not in_win:
                    continue
                eid = str(e.get("id"))
                n += 1
                if eid in seen:
                    continue
                tags = [t.get("slug") for t in (e.get("tags") or []) if t.get("slug")]
                slim = {"id": eid, "title": e.get("title"), "slug": e.get("slug"),
                        "tags": tags, "liq": e.get("liquidityNum"),
                        "vol24": e.get("volume24hr"), "markets": []}
                for m in mkts:
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
                seen[eid] = slim
            print("sweep %-16s total=%4d in_window=%d unique=%d" % (
                label, len(evs), n, len(seen)), flush=True)
            time.sleep(1.0)

        events = list(seen.values())
        for e in events:
            e["kick"] = min((m["gameStartTime"] for m in e["markets"]
                             if m["gameStartTime"]), default="")
        events.sort(key=lambda e: (e["kick"], e.get("title") or ""))
        json.dump(events, open(EVENTS_OUT, "w"), indent=1)
        print("unique in-window events:", len(events), flush=True)
        for e in events:
            print("  %-56s kick=%s nmk=%2d liq=%9s tags=%s" % (
                str(e["title"])[:56], e["kick"][11:16], len(e["markets"]),
                e.get("liq"), ",".join(t for t in e["tags"] if t in SOCCER_TAGS)[:44]),
                flush=True)

    # ---- classify fixtures ----
    fixtures = []
    for e in events:
        tags = set(e["tags"])
        league = None
        for t in tags:
            if t in LEAGUE_OF_TAG:
                league = LEAGUE_OF_TAG[t]
                break
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
        home_raw = parts[0].strip() if parts else ""
        away_raw = parts[1].strip() if len(parts) > 1 else ""
        home = away = None
        if league:
            home = canon_team(home_raw, titles[league])
            away = canon_team(away_raw, titles[league])
        fixtures.append({
            "event_id": e["id"], "title": e["title"], "kickoff_utc": e["kick"],
            "league_tag": league or "OTHER",
            "modelable": bool(league and home and away),
            "understat_home": home, "understat_away": away,
            "liq_event": e.get("liq"), "vol24": e.get("vol24"),
            "n_markets": len(e["markets"]),
        })

    # ---- ESPN kickoff verification ----
    espn = {}
    for code, lg in [("eng.1", "EPL"), ("ger.1", "Bundesliga"), ("fra.1", "Ligue_1"),
                     ("ita.1", "Serie_A"), ("esp.1", "La_liga")]:
        try:
            data = get("https://site.api.espn.com/apis/site/v2/sports/soccer/"
                       "%s/scoreboard?dates=20261102" % code)
            rows = []
            for ev in data.get("events", []):
                comp = (ev.get("competitions") or [{}])[0]
                odds = [[(o.get("provider", {}) or {}).get("name"),
                         o.get("details"), o.get("overUnder")]
                        for o in comp.get("odds", [])]
                rows.append({"name": ev.get("name"), "date": norm_ts(ev.get("date")),
                             "state": (ev.get("status") or {}).get("type", {}).get("state"),
                             "odds": odds})
            espn[lg] = rows
        except Exception as e:  # noqa: BLE001
            espn[lg] = {"error": repr(e)}
        time.sleep(0.4)
    json.dump(espn, open(ESPN_OUT, "w"), indent=1)

    # ---- model + books + gates ----
    matches = []
    gate_rows = []
    unparsed_qs = []
    groups = {}
    for fx, e in zip(fixtures, events):
        if not fx["modelable"]:
            continue
        key = (fx["league_tag"], fx["understat_home"], fx["understat_away"])
        groups.setdefault(key, {"fx": fx, "events": []})["events"].append(e)

    for key in sorted(groups, key=lambda k: groups[k]["fx"]["kickoff_utc"]):
        grp = groups[key]
        fx = grp["fx"]
        e0 = min(grp["events"], key=lambda e: len(e.get("title") or ""))
        base_title = re.split(r"\s+-\s+", e0.get("title") or "", maxsplit=1)[0]
        lg, home, away = fx["league_tag"], fx["understat_home"], fx["understat_away"]
        u_dt = fixtures_from_understat.get((lg, home, away))
        verified = u_dt is not None and u_dt[:16] == fx["kickoff_utc"][:16]
        if not verified:
            rev = fixtures_from_understat.get((lg, away, home))
            if rev is not None and rev[:16] == fx["kickoff_utc"][:16]:
                home, away = away, home
                fx["understat_home"], fx["understat_away"] = home, away
                fx["home_away_swapped"] = True
                verified = True
        fx["kickoff_verified_understat"] = verified
        variants = soccer_model.fixture_variants(snapshot, home, lg, away, lg)
        if variants is None:
            fx["modelable"] = False
            fx["model_note"] = "fixture_variants returned None"
            continue
        lam_h, lam_a = soccer_model.match_lambdas(snapshot, home, lg, away, lg)
        p1x2 = {
            "H": soccer_model.median([v.outputs.home_win for v in variants]),
            "D": soccer_model.median([v.outputs.draw for v in variants]),
            "A": soccer_model.median([v.outputs.away_win for v in variants]),
        }
        form_h = xg.recent_form(snapshot, home)
        form_a = xg.recent_form(snapshot, away)
        matches.append({
            "match": base_title, "league": lg,
            "gamma_event_ids": [e["id"] for e in grp["events"]],
            "kickoff_utc": fx["kickoff_utc"],
            "kickoff_verified_understat": verified,
            "lambda_home": round(lam_h, 3), "lambda_away": round(lam_a, 3),
            "lambda_total": round(lam_h + lam_a, 3),
            "p1x2_med": {k: round(v, 4) for k, v in p1x2.items()},
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
                    for v in variants:
                        o = v.outputs
                        qv = model_quote(o, kind, side_id, line, team_side)
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
                        kind=kind, side=side_id, o25_hits=o25_combined,
                        lambda_total=lam_h + lam_a, lambda_home=lam_h,
                        lambda_away=lam_a, line=line if line else 2.5)
                    report = gates.evaluate_candidate(
                        quote, book["asks"], gamma_liquidity=liq, under_risk=ur)
                    pol = suspension_policy(kind)
                    gate_rows.append({
                        "match": base_title, "league": lg, "q": m["q"],
                        "kind": kind, "side": side_id,
                        "line": line, "team_side": team_side,
                        "id": m["id"], "policy": pol,
                        "p_med": round(quote["model_median"], 4),
                        "p_min": round(min(qs), 4), "p_max": round(max(qs), 4),
                        "var_spread": report.variant_spread,
                        "gamma_bestAsk": m.get("bestAsk"), "gamma_bestBid": m.get("bestBid"),
                        "liq_gamma": liq,
                        "exec_ask_vwap250": report.walk.vwap,
                        "fill_250": report.walk.filled,
                        "depth_2c": report.walk.depth_near2c,
                        "exit_bid": book["best_bid"],
                        "exec_edge": report.exec_edge,
                        "worst_variant_edge": report.worst_variant_edge,
                        "haircut": report.haircut,
                        "exec_edge_haircut": report.exec_edge_haircut,
                        "under_risk": ur, "under_risk_reason": ur_reason,
                        "checks": {k: bool(v) for k, v in report.checks.items()},
                        "passed_numeric": all(
                            v for k, v in report.checks.items()
                            if k != "news_concordant"),
                    })

    out = {
        "scan": "soccer", "round": 27, "paper_only": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI},
        "method": ("Gamma date-window + league tag discovery -> in-window events; kickoff "
                   "cross-verified vs Understat fixture list + ESPN scoreboard; 10-variant "
                   "xG-Poisson via canonical papersim library (repo 7b6cdd47, selfcheck "
                   "10/10 PASS); CLOB $250-ask VWAP walk + frozen gate set (var<=6c, "
                   "worst>=+4c, exec>=+5c after 50-50 haircut, liq>=5k, fill_250, entry "
                   ".10-.92; news at candidate stage)"),
        "library": {"package": "polymarket_alpha_lab.papersim",
                    "repo_commit": "7b6cdd47", "selfcheck": "10/10 PASS",
                    "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src"},
        "gates": dict(gates.GATES, notes=(
            "cross-league MW banned; domestic MW eligible-but-deprioritized; "
            "spreads flagged-only; news-concordance required at candidate stage")),
        "bankroll_usd": 12374.33, "cash_usd": 9488.68,
        "xg_base": {"file": XG_PATH,
                    "note": ("r27 Understat refresh attempted 04:30Z Nov-2; see "
                             "xg_refresh note in scan output for fetch status.")},
        "fixtures": fixtures, "matches": matches, "gate_rows": gate_rows,
        "unparsed_questions": sorted(set(unparsed_qs)), "espn_verify": espn,
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("gate_rows:", len(gate_rows), "matches:", len(matches), flush=True)
    print("saved", OUT, flush=True)


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
        book = {"asks": asks, "best_bid": max((p for p, _ in bids), default=None)}
    except Exception as e:  # noqa: BLE001
        print("book err", m.get("id"), repr(e), flush=True)
        book = None
    BOOK_CACHE[tok] = book
    time.sleep(0.25)
    return book


def suspension_policy(kind):
    d = gates.suspension_policy(kind, cross_league=False)
    return d.policy


def parse_market_sides(m, home, away):
    """Return [(token_idx, kind, side_id, line, team_side)] or None if unparsed."""
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
        resolved = canon_team(name, [home, away])
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
        for i, o in enumerate(outcomes):
            if team_side_of(str(o)) == team:
                return [(i, "spread", team, line, team)]
        return None

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
        for i, o in enumerate(outcomes):
            if str(o).lower() in ("yes", "draw"):
                return [(i, "ml", "draw", None, None)]
        return None

    if re.search(r"win on|win \(", core) or ("match winner" in g):
        head = re.split(r"\bwin\b", core)[0].replace("will ", "").strip()
        team = team_side_of(head)
        if team is None:
            return None
        for i, o in enumerate(outcomes):
            if str(o).lower() == "yes":
                return [(i, "ml", team, None, None)]
        return None

    return None


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
        return {"home": o.home_win, "away": o.away_win, "draw": o.draw}[side_id]
    if kind == "spread":
        return soccer_model.cover_probability(o, team_side, line)
    return None


if __name__ == "__main__":
    main()
