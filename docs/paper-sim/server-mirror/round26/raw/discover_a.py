"""Round-26 scan A: Gamma discovery of today's 9 Serie A / La Liga fixtures (paper-only).
Fetch open events for the Nov-1 window, match to the fixture list, dump raw events
plus a flat market table (q, id, outcomes, gamma prices, tokens, liquidity)."""
import json, time, urllib.request

BASE = "https://gamma-api.polymarket.com"
RAW = "/home/ubuntu/paper-sim/round26/raw"

FIXTURES = [
    ("Serie_A", "Como", "Venezia", ["como"], ["venezia"], "2026-11-01T11:30:00Z"),
    ("Serie_A", "Frosinone", "Torino", ["frosinone"], ["torino"], "2026-11-01T14:00:00Z"),
    ("Serie_A", "Lazio", "Cagliari", ["lazio"], ["cagliari"], "2026-11-01T14:00:00Z"),
    ("Serie_A", "Lecce", "Genoa", ["lecce"], ["genoa"], "2026-11-01T17:00:00Z"),
    ("Serie_A", "Juventus", "Napoli", ["juventus"], ["napoli"], "2026-11-01T19:45:00Z"),
    ("La_liga", "Getafe", "Sevilla", ["getafe"], ["sevilla"], "2026-11-01T13:00:00Z"),
    ("La_liga", "Racing Santander", "Real Madrid", ["racing"], ["real madrid"], "2026-11-01T15:15:00Z"),
    ("La_liga", "Elche", "Valencia", ["elche"], ["valencia"], "2026-11-01T17:30:00Z"),
    ("La_liga", "Athletic Club", "Real Sociedad", ["athletic"], ["real sociedad"], "2026-11-01T20:00:00Z"),
]

def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e; time.sleep(1.5 + i)
    return {"__err__": repr(last)}

events = {}
for tag in ("serie-a", "la-liga", "soccer"):
    offset = 0
    while True:
        url = (BASE + "/events?tag_slug=" + tag + "&closed=false&limit=100&offset=" + str(offset)
               + "&start_date_min=2026-11-01T00:00:00Z&start_date_max=2026-11-02T04:00:00Z")
        batch = get(url)
        if not isinstance(batch, list) or not batch:
            err = batch.get("__err__") if isinstance(batch, dict) else "empty"
            print(tag, "offset", offset, "stop:", err)
            break
        for ev in batch:
            events[ev.get("id")] = ev
        if len(batch) < 100:
            break
        offset += 100
        time.sleep(0.4)
    print("tag", tag, "cum unique events", len(events))

with open(RAW + "/events_a.json", "w") as f:
    json.dump({"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "events": list(events.values())}, f)

def norm(s):
    return " ".join(str(s or "").lower().split())

matched = []
for lg, home, away, hkeys, akeys, ko in FIXTURES:
    hits = []
    for ev in events.values():
        t = norm(ev.get("title"))
        if any(k in t for k in hkeys) and any(k in t for k in akeys):
            hits.append(ev)
    hits.sort(key=lambda e: -(float(e.get("liquidityNum") or 0) or 0))
    if not hits:
        print("NO EVENT:", home, "vs", away)
        matched.append({"fixture": home + "-" + away, "league": lg, "kickoff_utc": ko, "event": None, "markets": []})
        continue
    ev = hits[0]
    mk_rows = []
    for m in ev.get("markets", []):
        try:
            prices = json.loads(m.get("outcomePrices") or "[]")
        except Exception:
            prices = []
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
        except Exception:
            toks = []
        mk_rows.append({
            "q": m.get("question"), "id": m.get("id"),
            "outcomes": json.loads(m.get("outcomes") or "[]"),
            "prices": prices, "tokens": toks,
            "best_ask": m.get("bestAsk"), "best_bid": m.get("bestBid"),
            "liq": float(m.get("liquidityNum") or 0),
            "vol24": float(m.get("volume24hr") or 0),
            "spread": m.get("spread"), "oneDayPriceChange": m.get("oneDayPriceChange"),
        })
    matched.append({"fixture": home + "-" + away, "league": lg, "kickoff_utc": ko,
                    "event": {"id": ev.get("id"), "title": ev.get("title"), "slug": ev.get("slug"),
                              "start": ev.get("startDate"), "liq": float(ev.get("liquidityNum") or 0)},
                    "alt_events": [{"id": h.get("id"), "title": h.get("title")} for h in hits[1:4]],
                    "markets": mk_rows})
    print("MATCHED:", home, "vs", away, "->", ev.get("title"), "| markets:", len(mk_rows))

with open(RAW + "/markets_a.json", "w") as f:
    json.dump({"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "fixtures": matched}, f, indent=1)
print("wrote", RAW + "/markets_a.json")
