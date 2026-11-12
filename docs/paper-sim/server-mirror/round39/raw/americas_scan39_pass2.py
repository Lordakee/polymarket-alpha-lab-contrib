"""ROUND-39B pass 2: complete per-tag enumeration for ALL Americas/ROW leagues.

Why pass 2 exists (recorded for lineage):
  - Pass-1 date/tag sweeps each hit the 1000-event pagination cap, and the
    pass-1 LEAGUE_TAG_MAP guessed wrong slugs for several leagues (actual:
    'mex', 'arg', 'saudi-professional-league', 'k-league', 'brazil-serie-b',
    'colombia-primera-a', ...). Classification survived only via ESPN
    cross-match, so tag-only leagues (Saudi, Korea, China, South America
    beyond Argentina, CONCACAF minors, Morocco) were MISSED, and some Liga MX
    fixtures may be missing due to the cap.
  - Pass 2 re-enumerates by exact tag slug (cheap: one pagination per tag),
    merges with the pass-1 event file, classifies with the corrected map,
    groups events into fixtures, and boards them (Gamma prices everywhere;
    CLOB books + walks only for the most liquid fixtures).
  - 'soccer-brco' = Copa do Brasil (verified from event descriptions):
    KNOCKOUT games -> full /markets/{id} verification + resolution-rules
    text capture (ET/pens/aggregate), per the dispatch playoff caveat.

Still BOARD-ONLY: no in-scope league has model coverage (see pass 1 header).
Paper only. No DB writes, no credentials, no orders.
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
HOME = "/home/ubuntu/paper-sim"
OUTDIR = f"{HOME}/round39/raw"
OUT = f"{OUTDIR}/americas_scan_pass2.json"
SCAN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LO = "2026-11-06T13:30:00Z"
HI = "2026-11-08T23:59:59Z"

TAG2LEAGUE = {
    "mls": "MLS", "canpl": "Canadian Premier League", "uslc": "USL Championship",
    "brazil-serie-a": "Brasileirao Serie A", "brazil-serie-b": "Brasileirao Serie B",
    "soccer-brco": "Copa do Brasil", "mex": "Liga MX", "arg": "Argentina Primera",
    "soccer-fpd": "Costa Rica Primera Division", "soccer-gtm": "Guatemala Liga Nacional",
    "colombia-primera-a": "Colombia Primera A", "chile-primera": "Chile Primera Division",
    "peru-liga-1": "Peru Liga 1", "Bolivia-LFPB": "Bolivia LFPB",
    "ecu1": "Ecuador Serie A", "par1": "Paraguay Division Profesional",
    "ven1": "Venezuela Primera Division",
    "saudi-professional-league": "Saudi Pro League", "japan-j-league": "J-League",
    "japan-j2-league": "J2 League", "ja3": "J3 League", "k-league": "K-League",
    "kor2": "K League 2", "australian-a-league": "A-League",
    "chinese-super-league": "Chinese Super League", "chi2": "China League One (chi2)",
    "indian-super-league": "Indian Super League", "tha1": "Thai League 1",
    "idn1": "Indonesia Liga 1", "uzb1": "Uzbekistan Super League",
    "qat1": "Qatar Stars League", "uae1": "UAE Pro League",
    "Morocco-Botola-Pro": "Morocco Botola Pro",
}
WOMEN_TAGS = {"soccer-nwsl", "wsl", "nwsl", "womens-soccer"}
KINDS_WANTED = {"ml_win", "ml_draw", "total", "team_total", "btts", "spread"}
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


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return []
    return raw or []


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
            "outcomes": parse_listy(m.get("outcomes")),
            "prices": parse_listy(m.get("outcomePrices")),
            "tokens": parse_listy(m.get("clobTokenIds")),
            "line": m.get("line") or m.get("handicap"),
            "gameStartTime": norm_ts(m.get("gameStartTime")),
            "endDate": norm_ts(m.get("endDate")),
            "liq": m.get("liquidityNum"), "vol24": m.get("volume24hr"),
            "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
            "active": m.get("active"),
            "description_excerpt": mdesc[:900]})
    kos = [m["gameStartTime"] for m in slim["markets"] if m["gameStartTime"]]
    slim["kick"] = min(kos) if kos else ""
    return slim


def in_window(slim):
    kos = [m["gameStartTime"] for m in slim["markets"] if m["gameStartTime"]]
    return any(LO <= k <= HI for k in kos)


def tag_sweep(slug):
    """Complete enumeration for one tag slug (pagination until exhausted)."""
    out, offset = [], 0
    while True:
        params = {"limit": 100, "active": "true", "closed": "false",
                  "order": "volume24hr", "ascending": "false",
                  "offset": offset, "tag_slug": slug}
        resp = get(BASE + "/events/pagination?" + urllib.parse.urlencode(params))
        batch = resp.get("data") if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100:
            return out
        offset += 100
        if offset >= 2000:
            return out
        time.sleep(1.0)


def classify_kind(m):
    q = strip_accents(str(m.get("q") or "").lower())
    g = strip_accents(str(m.get("group") or "").lower())
    blob = q + " " + g
    if re.search(r"(1st|2nd|first|second)\s*half", blob) or "halftime" in blob:
        return "half"
    if any(w in blob for w in ("corner", "card ", "cards", "odd or even",
                               "score first", "exact score", "leading",
                               "player", "goalscorer", "score in",
                               "first team to score")):
        return "prop"
    if q.startswith("spread") or re.search(r"\(\s*[-+]?\d+\.5\s*\)", blob):
        return "spread"
    if re.search(r"end in a draw", blob):
        return "ml_draw"
    if re.search(r"\bwin on\b|\bwin \(", blob) or "match winner" in g:
        return "ml_win"
    if re.search(r"\bo/u\b|over/under", blob) or ("over" in blob and "under" in blob) \
            or "score over" in blob or "score under" in blob:
        return "total_or_tt"
    if "both teams" in blob or "btts" in g:
        return "btts"
    if re.search(r"\bwin\b", blob) or re.search(r"advance|qualify|reach|lift|champion|title|relegat", blob):
        return "futures_adv"
    return "other"


def rule_scan(text):
    t = re.sub(r"\s+", " ", str(text or "").lower())
    hits = {}
    for kw in RULE_KEYWORDS:
        for mth in re.finditer(re.escape(kw), t):
            ctx = t[max(0, mth.start() - 140):mth.end() + 200].strip()
            hits.setdefault(kw, []).append(ctx)
            if len(hits[kw]) >= 3:
                break
    return hits


def fetch_book(token, cache):
    if token in cache:
        return cache[token]
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
    cache[token] = book
    time.sleep(0.25)
    return book


def fetch_market(mid, cache):
    if mid in cache:
        return cache[mid]
    try:
        m = get(BASE + "/markets/" + str(mid))
    except Exception as e:  # noqa: BLE001
        print("market verify err", mid, repr(e), flush=True)
        m = None
    cache[mid] = m
    time.sleep(0.2)
    return m


def main():
    print("UTC now:", datetime.now(timezone.utc).isoformat(), flush=True)

    seen = {}
    for e in json.load(open(f"{OUTDIR}/events_window_39b.json")):
        seen[e["id"]] = e
    print("pass-1 events loaded:", len(seen), flush=True)

    for slug, league in TAG2LEAGUE.items():
        try:
            raw = tag_sweep(slug)
        except Exception as e:  # noqa: BLE001
            print("tag sweep FAILED", slug, repr(e), flush=True)
            continue
        n_new, n_win = 0, 0
        for e in raw:
            try:
                slim = slim_event(e)
            except Exception:  # noqa: BLE001
                continue
            if not in_window(slim):
                continue
            n_win += 1
            if slim["id"] not in seen:
                seen[slim["id"]] = slim
                n_new += 1
        print("tag %-26s league=%-28s total=%4d in_window=%3d new=%3d" % (
            slug, league, len(raw), n_win, n_new), flush=True)
        time.sleep(0.8)

    events = [e for e in seen.values()
              if "soccer" in (e.get("tags") or []) and e.get("kick")]
    print("\ntotal unique open soccer events in window (pass1+pass2):", len(events),
          flush=True)

    # ---- classify + group into fixtures ----
    fixtures = {}
    for e in events:
        tags = set(e["tags"])
        lt = [(t, TAG2LEAGUE[t]) for t in tags if t in TAG2LEAGUE]
        if not lt:
            continue  # European / women's / out of scope
        if tags & WOMEN_TAGS:
            continue
        league = sorted(set(l for _, l in lt))[0]
        base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
        if " vs" not in base:
            continue
        key = e["kick"] + "|" + base
        fx = fixtures.setdefault(key, {
            "match": base, "kickoff_utc": e["kick"], "league": league,
            "league_tags": sorted(t for t, _ in lt), "event_ids": [],
            "events": [], "women_flag": False})
        fx["event_ids"].append(e["id"])
        fx["events"].append(e)

    print("unique in-scope fixtures (leagues tagged):", len(fixtures), flush=True)

    book_cache, mkt_cache = {}, {}
    board = []
    for key in sorted(fixtures, key=lambda k: (fixtures[k]["kickoff_utc"],
                                               fixtures[k]["match"])):
        fx = fixtures[key]
        league = fx["league"]
        knockout = league in ("Copa do Brasil",)
        rows = []
        for e in fx["events"]:
            for m in e["markets"]:
                kind = classify_kind(m)
                if kind not in KINDS_WANTED:
                    continue
                outs = m.get("outcomes") or []
                toks = m.get("tokens") or []
                prices = m.get("prices") or []
                sides = []
                for i in range(min(len(outs), len(toks))):
                    bid = m.get("bestBid")
                    ask = m.get("bestAsk")
                    try:
                        bid = float(bid) if bid is not None else None
                        ask = float(ask) if ask is not None else None
                    except Exception:  # noqa: BLE001
                        bid = ask = None
                    gp = None
                    try:
                        gp = float(prices[i]) if i < len(prices) else None
                    except Exception:  # noqa: BLE001
                        pass
                    sides.append({
                        "outcome": outs[i], "token": str(toks[i]),
                        "gamma_best_bid": bid, "gamma_best_ask": ask,
                        "gamma_price": gp})
                rows.append({
                    "market_id": m["id"], "question": m["q"],
                    "event_id": e["id"], "kind": kind, "line": m.get("line"),
                    "gameStartTime": m.get("gameStartTime"),
                    "liq_gamma_usd": float(m.get("liq") or 0),
                    "sides": sides,
                    "no_model_coverage": "NO MODEL COVERAGE - report only, no entry"})
        # dedupe by market id, sort by liquidity
        ded = {}
        for r in rows:
            if r["market_id"] not in ded:
                ded[r["market_id"]] = r
        rows = sorted(ded.values(), key=lambda r: -r["liq_gamma_usd"])[:16]
        fx["total_liq_usd"] = round(sum(r["liq_gamma_usd"] for r in rows), 2)
        fx["n_markets_kinds"] = len(rows)
        fx.pop("events", None)
        fx["knockout_competition"] = knockout
        board.append({"fixture": fx, "rows": rows})

    # ---- books for the most liquid fixtures (top 25 by total liq) ----
    top = sorted(board, key=lambda b: -b["fixture"]["total_liq_usd"])[:25]
    top_keys = {id(b) for b in top}
    n_books = 0
    for b in board:
        if id(b) not in top_keys:
            continue
        for r in b["rows"][:10]:
            for s in r["sides"]:
                book = fetch_book(s["token"], book_cache)
                if book is None:
                    continue
                n_books += 1
                w250 = gates.walk_book(book["asks"], side="ask", notional=250.0)
                w150 = gates.walk_book(book["asks"], side="ask", notional=150.0)
                s["clob_best_bid"] = book["best_bid"]
                s["clob_best_ask"] = book["best_ask"]
                s["vwap_250"] = w250.vwap
                s["fill_250"] = w250.filled
                s["vwap_150"] = w150.vwap
                s["fill_150"] = w150.filled
                s["depth_2c_usd"] = w250.depth_near2c
    print("\nCLOB books fetched for top-25 fixtures:", n_books, flush=True)

    # ---- verification + rules (Copa do Brasil = full; top fixtures = top ML) ----
    verifications, rules_evidence = [], []
    for b in board:
        knockout = b["fixture"]["knockout_competition"]
        is_top = id(b) in top_keys
        check = b["rows"] if knockout else (
            [r for r in b["rows"] if r["kind"] in ("ml_win", "ml_draw")][:3]
            if is_top else [])
        for r in check[:8]:
            vm = fetch_market(r["market_id"], mkt_cache)
            if not isinstance(vm, dict):
                verifications.append({"market_id": r["market_id"], "ok": False,
                                      "error": "fetch failed"})
                continue
            gs = norm_ts(vm.get("gameStartTime"))
            ed = norm_ts(vm.get("endDate"))
            kick_ok = None
            if gs and b["fixture"]["kickoff_utc"]:
                kick_ok = abs((
                    datetime.fromisoformat(gs.replace("Z", "+00:00")) -
                    datetime.fromisoformat(
                        b["fixture"]["kickoff_utc"].replace("Z", "+00:00"))
                ).total_seconds()) <= 3600
            endd_ok = None
            if ed and gs:
                dd = (datetime.fromisoformat(ed.replace("Z", "+00:00")) -
                      datetime.fromisoformat(gs.replace("Z", "+00:00"))).total_seconds()
                endd_ok = 0 <= dd <= 60 * 60 * 30
            verifications.append({
                "market_id": str(vm.get("id")), "ok": True, "league":
                    b["fixture"]["league"],
                "question": vm.get("question"),
                "closed": vm.get("closed"), "active": vm.get("active"),
                "gameStartTime": gs, "endDate": ed,
                "kickoff_matches_event": kick_ok,
                "endDate_after_kick_within_30h": endd_ok})
            hits = rule_scan(str(vm.get("description") or ""))
            if hits:
                rules_evidence.append({
                    "market_id": str(vm.get("id")),
                    "league": b["fixture"]["league"],
                    "match": b["fixture"]["match"],
                    "kickoff_utc": b["fixture"]["kickoff_utc"],
                    "question": vm.get("question"),
                    "rules_hits": hits,
                    "description_full_len": len(str(vm.get("description") or ""))})

    print("verifications:", len(verifications), "rules-hits:", len(rules_evidence),
          flush=True)

    league_counts = {}
    for b in board:
        league_counts[b["fixture"]["league"]] = league_counts.get(
            b["fixture"]["league"], 0) + 1
    print("\nfixtures by league:", flush=True)
    for lg, c in sorted(league_counts.items(), key=lambda kv: -kv[1]):
        print("  %-30s %d" % (lg, c), flush=True)

    out = {
        "round": 39, "pass": 2, "scan": "americas-row-48h-tag-complete",
        "paper_only": True, "generated_utc": SCAN_TS,
        "window_utc": {"lo": LO, "hi": HI},
        "note": ("pass 2 = complete per-tag enumeration with corrected slugs; "
                 "merged with pass-1 events file; still BOARD-ONLY (no model "
                 "coverage in any in-scope league)"),
        "tag_to_league": TAG2LEAGUE,
        "fixtures_by_league": league_counts,
        "board": board,
        "market_verifications": verifications,
        "playoff_rules_evidence": rules_evidence,
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nwrote", OUT, flush=True)


if __name__ == "__main__":
    main()
