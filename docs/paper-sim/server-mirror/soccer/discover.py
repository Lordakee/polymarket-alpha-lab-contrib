import json, urllib.request, time, os

TAGS = ["soccer","epl","premier-league","champions-league","la-liga","world-cup"]
BASE = "https://gamma-api.polymarket.com"
os.makedirs("/home/ubuntu/paper-sim/soccer/raw", exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent":"research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

all_events = {}
tag_of = {}
for tag in TAGS:
    offset = 0
    n = 0
    while True:
        url = BASE + "/events?tag_slug=" + tag + "&closed=false&limit=100&offset=" + str(offset) + "&order=volume24hr&ascending=false"
        try:
            batch = get(url)
        except Exception as e:
            print(tag, "offset", offset, "ERROR", e, "- stopping this tag (API offset cap)")
            break
        if not batch:
            break
        for ev in batch:
            eid = ev.get("id")
            if eid not in all_events:
                all_events[eid] = ev
                tag_of[eid] = tag
        n += len(batch)
        if len(batch) < 100:
            break
        offset += 100
        time.sleep(0.35)
    print("tag=" + tag + " fetched=" + str(n) + " unique_total=" + str(len(all_events)))

with open("/home/ubuntu/paper-sim/soccer/raw/events_open_all_tags.json","w") as f:
    json.dump(list(all_events.values()), f)

rows = []
for ev in all_events.values():
    liq = 0.0
    vol24 = 0.0
    nmk = 0
    best_end = ""
    for m in ev.get("markets", []):
        try: liq += float(m.get("liquidityNum") or m.get("liquidity") or 0)
        except Exception: pass
        try: vol24 += float(m.get("volume24hr") or 0)
        except Exception: pass
        nmk += 1
        ed = m.get("endDate") or ""
        if ed and (best_end == "" or ed < best_end):
            best_end = ed
    rows.append({
        "id": ev.get("id"), "slug": ev.get("slug"), "title": ev.get("title"),
        "discover_tag": tag_of.get(ev.get("id")),
        "n_markets": nmk, "liq_sum": round(liq,2), "vol24_sum": round(vol24,2),
        "end_min": best_end[:10],
        "tags": [t.get("slug") for t in (ev.get("tags") or [])][:8],
    })
rows.sort(key=lambda r: -r["liq_sum"])
with open("/home/ubuntu/paper-sim/soccer/events_summary.json","w") as f:
    json.dump(rows, f, indent=1)
print()
print("TOP 50 by summed liquidity:")
for r in rows[:50]:
    line = format(r["liq_sum"], ",.0f").rjust(12) + " v24=" + format(r["vol24_sum"], ",.0f").rjust(10) + " nmk=" + str(r["n_markets"]).rjust(3) + " end=" + str(r["end_min"]).ljust(10) + " [" + str(r["discover_tag"]) + "] " + r["slug"][:64]
    print(line)
