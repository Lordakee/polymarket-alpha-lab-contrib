"""Round45: POR playoffs market mark + CLOB book + remaining slates via public-search."""
import json, urllib.request, urllib.parse, time, datetime, os

RAW = "/home/ubuntu/paper-sim/round45/raw"
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

def get(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as ex:
            print("ERR", url[:130], ex, flush=True)
            if i == tries - 1:
                return None
            time.sleep(2)

def dump(name, obj):
    json.dump({"fetched_at": NOW.isoformat(), "data": obj}, open(f"{RAW}/{name}.json", "w"))

G = "https://gamma-api.polymarket.com"

# 1) NBA make-playoffs event markets -> find Trail Blazers
ev = get(f"{G}/events/681898?include_markets=true")
if ev:
    dump("nba_make_playoffs_event", ev)
    mkts = ev.get("markets", [])
    print("make-playoffs event markets:", len(mkts), flush=True)
    por = [m for m in mkts if "blazer" in str(m.get("question", "")).lower()]
    for m in por:
        keep = {k: m.get(k) for k in ["id", "question", "conditionId", "slug", "outcomes", "outcomePrices",
                                       "bestBid", "bestAsk", "lastTradePrice", "liquidityNum", "volumeNum",
                                       "volume24hr", "endDate", "active", "closed", "clobTokenIds", "umaResolutionStatus"]}
        print("POR MARKET:", json.dumps(keep, indent=1), flush=True)

# 2) CLOB book for POR market tokens
if ev:
    por = [m for m in ev.get("markets", []) if "blazer" in str(m.get("question", "")).lower()]
    if por:
        m = por[0]
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
        except Exception:
            toks = []
        outcomes = json.loads(m.get("outcomes") or "[]") if m.get("outcomes") else []
        for i, t in enumerate(toks):
            b = get(f"https://clob.polymarket.com/book?token_id={t}")
            if b:
                dump(f"por_clob_book_{'yes' if i == 0 else str(outcomes[i])[:6]}", b)
                lvl = lambda side: [(l.get("price"), l.get("size")) for l in (b.get(side) or [])[:4]]
                print(f"token{i} {outcomes[i] if outcomes else i}: bids {lvl('bids')} asks {lvl('asks')}", flush=True)
            time.sleep(0.4)

# 3) public-search remaining sports
for q, fn in [
    ("commanders giants", "pubsearch_was_nyg"),
    ("nfl week", "pubsearch_nfl_week"),
    ("college football", "pubsearch_cfb"),
    ("ncaaf", "pubsearch_ncaaf"),
    ("ufc", "pubsearch_ufc"),
    ("boxing", "pubsearch_boxing"),
    ("formula 1", "pubsearch_f1"),
    ("f1", "pubsearch_f1b"),
    ("cricket", "pubsearch_cricket"),
]:
    d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=25&events_status=active")
    if d is not None:
        dump(fn, d)
        evs = d.get("events", []) if isinstance(d, dict) else []
        print(f"[{q}] {len(evs)} events", flush=True)
        for e in evs[:10]:
            print("   ", str(e.get("title"))[:85], str(e.get("startDate"))[:16], flush=True)
    time.sleep(0.4)

# 4) ESPN NFL scoreboards, individual dates
for dates in ["20261109", "20261112", "20261113", "20261114", "20261115", "20261116"]:
    d = get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={dates}")
    if d is not None:
        dump(f"espn_nfl_sb_{dates}", d)
        evs = d.get("events", [])
        print(dates, "NFL games:", len(evs), [str(e.get("name"))[:24] for e in evs][:8], flush=True)
print("POR45 DONE", flush=True)
