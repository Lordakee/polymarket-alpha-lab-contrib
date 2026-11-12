import json, urllib.request, time, datetime

GAMMA = "https://gamma-api.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
evs = []
seen = set()
for q in ["fed dissent", "FOMC dissent", "fed october", "fed january", "fomc", "fed meeting"]:
    off = 0
    while True:
        u = "%s/events?closed=false&limit=100&offset=%d&order=volume24hr&ascending=false&q=%s" % (GAMMA, off, urllib.parse.quote(q))
        try:
            batch = get(u)
        except Exception as e:
            print("ERR", q, off, e); break
        if not batch: break
        for e in batch:
            if e["id"] not in seen:
                seen.add(e["id"]); evs.append(e)
        if len(batch) < 100: break
        off += 100
        time.sleep(0.3)
print("unique events:", len(evs))
def liq(e):
    try: return sum(float(m.get("liquidityNum") or 0) for m in e.get("markets", []))
    except: return 0.0
for e in sorted(evs, key=lambda x: -liq(x))[:25]:
    t = (e.get("title") or "")[:70]
    if any(k in t.lower() for k in ["fed", "fomc", "dissent", "rate", "powell", "chair"]):
        print("%-10s %-70s end=%s liq=%.0f nm=%d" % (str(e["id"])[:10], t, str(e.get("endDate"))[:10], liq(e), len(e.get("markets", []))))
json.dump(evs, open("/home/ubuntu/paper-sim/round3/raw/fed_search_events.json", "w"), indent=1)
print("saved fed_search_events.json")
