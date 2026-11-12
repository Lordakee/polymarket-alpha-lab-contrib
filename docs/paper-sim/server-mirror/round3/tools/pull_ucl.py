import json, urllib.request, time, datetime

GAMMA = "https://gamma-api.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

now = datetime.datetime.now(datetime.timezone.utc)
print("UTC now:", now.isoformat())

# UCL MD3 fixtures Oct 13-14
slugs = [
    "atletico-madrid-manchester-united-2026-10-13",
    "arsenal-lille-2026-10-13",
    "inter-club-brugge-2026-10-14",
    "galatasaray-barcelona-2026-10-14",
    "atletico-manchester-united-2026-10-13",
    "manchester-united-atletico-madrid-2026-10-13",
]
# discover via tag + date range to be safe
evs = []
for tag in ["champions-league", "ucl"]:
    off = 0
    while True:
        u = ("%s/events?tag_slug=%s&closed=false&end_date_min=2026-10-12&end_date_max=2026-10-16&order=volume24hr&ascending=false&limit=100&offset=%d" % (GAMMA, tag, off))
        try:
            batch = get(u)
        except Exception as e:
            print("ERR", tag, off, e); break
        if not batch: break
        evs.extend(batch)
        if len(batch) < 100: break
        off += 100
        time.sleep(0.3)
seen = {}
for e in evs:
    seen[e["id"]] = e
print("unique UCL-window events:", len(seen))
json.dump(list(seen.values()), open("/home/ubuntu/paper-sim/round3/raw/ucl_events.json", "w"), indent=1)
# print top by liquidity
def liq(e):
    try: return sum(float(m.get("liquidityNum") or 0) for m in e.get("markets", []))
    except: return 0.0
rows = sorted(seen.values(), key=lambda e: -liq(e))[:40]
for e in rows:
    print("%-8s %-60s %s liq=%.0f mkts=%d" % (str(e.get("id"))[:8], e.get("slug","")[:60], str(e.get("startDate"))[:16], liq(e), len(e.get("markets",[]))))
