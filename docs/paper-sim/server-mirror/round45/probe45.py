"""Round45 probe: find POR playoffs market via public-search; fix NFL/CFB/UFC/boxing/F1 slates."""
import json, urllib.request, urllib.parse, time, os

RAW = "/home/ubuntu/paper-sim/round45/raw"
NOW = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0)

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

# 1) public-search endpoints for POR market
for q in ["trail blazers", "blazers playoffs"]:
    d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=20&events_status=active")
    if d is not None:
        safe = q.replace(" ", "_")
        dump(f"pubsearch_{safe}", d)
        evs = d.get("events", []) if isinstance(d, dict) else []
        print(f"pubsearch [{q}]: {len(evs)} events", flush=True)
        for e in evs[:12]:
            print("   EV:", str(e.get("title"))[:90], flush=True)
    time.sleep(0.4)

# 2) alternate tag slates
for tag, fn, lo, hi in [
    ("nfl", "nfl_slate_b", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("football", "football_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("college-football", "cfb_slate2", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("ncaa-football", "cfb_slate3", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("mma", "mma_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("formula-1", "f1_slate2", "2026-11-09T00:00:00Z", "2026-11-24T00:00:00Z"),
    ("motorsport", "motorsport_slate", "2026-11-09T00:00:00Z", "2026-11-24T00:00:00Z"),
]:
    d = get(f"{G}/events?tag_slug={tag}&closed=false&start_date_min={lo}&start_date_max={hi}&limit=100&order=startDate&ascending=true")
    if d is not None:
        dump(fn, d)
        print(f"{tag}: {len(d)} events", flush=True)
        for e in d[:6]:
            print("   EV:", str(e.get("title"))[:80], str(e.get("startDate"))[:16], flush=True)
    time.sleep(0.4)

# 3) NBA tag, wide: catch season futures (playoffs markets) — paginate 4 pages
all_nba = []
for off in [0, 100, 200, 300]:
    d = get(f"{G}/events?tag_slug=nba&closed=false&limit=100&offset={off}&order=endDate&ascending=false")
    if not d:
        break
    all_nba.extend(d)
    time.sleep(0.4)
dump("nba_tag_wide", all_nba)
print("nba wide:", len(all_nba), flush=True)
for e in all_nba:
    t = str(e.get("title", ""))
    if "blazer" in t.lower() or "playoff" in t.lower():
        print("   FUT:", t[:100], e.get("id"), flush=True)
print("PROBE DONE", flush=True)
