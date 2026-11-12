import json, urllib.request, gzip, io, time

BASE = "https://gamma-api.polymarket.com"
SLUGS = [
    # near-dated matches (EPL today/tomorrow + La Liga today)
    "epl-mun-tot-2026-10-10", "epl-ips-ful-2026-10-10", "epl-che-bou-2026-10-10",
    "epl-ast-bre-2026-10-10", "epl-sun-bri-2026-10-10", "epl-cry-not-2026-10-11",
    "lal-bar-get-2026-10-10", "lal-rea-vil-2026-10-10", "lal-ala-mad-2026-10-10",
    # season futures
    "uefa-champions-league-2027-champion-20260701202025549",
    "epl-2027-champion-20260701200428749",
    "laliga-2027-champion-20260701200737375",
    "serie-a-2027-champion-20260701200118390",
    "ligue-1-2027-champion-20260701201053335",
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

out = {}
for slug in SLUGS:
    try:
        evs = get(BASE + "/events?slug=" + slug)
        if not evs:
            print("MISSING", slug); continue
        ev = evs[0]
        mk = []
        for m in ev.get("markets", []):
            if m.get("closed"): continue
            mk.append({
                "q": m.get("question"),
                "outcomes": m.get("outcomes"),
                "prices": m.get("outcomePrices"),
                "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
                "spread": m.get("spread"),
                "liq": m.get("liquidityNum") or m.get("liquidity"),
                "vol": m.get("volume"), "vol24": m.get("volume24hr"),
                "tokens": m.get("clobTokenIds"),
                "endDate": m.get("endDate"), "groupItemTitle": m.get("groupItemTitle"),
                "outcomesSdkData": None,
            })
        out[slug] = {
            "title": ev.get("title"), "gameStart": ev.get("startDate"),
            "endDate": ev.get("endDate"), "n_open": len(mk), "markets": mk,
            "tags": [t.get("slug") for t in (ev.get("tags") or [])],
        }
        print("OK", slug, "open_markets=", len(mk), "title=", ev.get("title"))
        time.sleep(0.3)
    except Exception as e:
        print("ERR", slug, e)

with open("/home/ubuntu/paper-sim/soccer/raw/candidate_events.json", "w") as f:
    json.dump(out, f, indent=1)
print("saved candidate_events.json")
