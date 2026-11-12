import json, glob, datetime

NOW = datetime.datetime(2026, 10, 22, 12, 0, tzinfo=datetime.timezone.utc)
WINDOW_END = NOW + datetime.timedelta(days=7)

pages = []
for fn in glob.glob("/home/ubuntu/paper-sim/round12/raw/*_p*.json"):
    d = json.load(open(fn))
    pages.extend(d.get("data", []))

events = {}
for e in pages:
    events[e.get("id")] = e

def end_dt(e):
    s = e.get("endDate") or ""
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def sport_of(e):
    slugs = set((t.get("slug") or "").lower() for t in (e.get("tags") or []))
    for s in ("nba", "nfl", "mlb"):
        if s in slugs:
            return s
    return None

buckets = {"nba": [], "nfl": [], "mlb": []}
for e in events.values():
    s = sport_of(e)
    if not s:
        continue
    ed = end_dt(e)
    buckets[s].append((ed, e))

out = {}
for s, lst in buckets.items():
    lst2 = [x for x in lst if x[0]]
    upcoming = [x for x in lst2 if x[0] > NOW - datetime.timedelta(hours=6)]
    in_window = sorted([x for x in upcoming if x[0] <= WINDOW_END], key=lambda x: x[0])
    beyond = sorted([x for x in upcoming if x[0] > WINDOW_END], key=lambda x: -(x[1].get("volume24hr") or 0))
    out[s] = {"total": len(lst), "upcoming": len(upcoming), "in_window": len(in_window), "beyond": len(beyond)}
    print("==== %s: total=%d upcoming=%d in7d=%d beyond=%d ====" % (s, len(lst), len(upcoming), len(in_window), len(beyond)))
    print("-- IN 7-DAY WINDOW (top 30 by vol) --")
    for ed, e in sorted(in_window, key=lambda x: -(x[1].get("volume24hr") or 0))[:30]:
        print("[%9.0f] %-55s end:%s" % (e.get("volume24hr") or 0, (e.get("title") or "")[:55], str(e.get("endDate"))[:16]))
    print("-- BEYOND WINDOW, top 12 by vol (futures) --")
    for ed, e in beyond[:12]:
        print("[%9.0f] %-55s end:%s" % (e.get("volume24hr") or 0, (e.get("title") or "")[:55], str(e.get("endDate"))[:16]))

# POR playoffs market search
print("\n==== POR SEARCH ====")
for e in events.values():
    t = (e.get("title") or "")
    for m in (e.get("markets") or []):
        q = (m.get("question") or "")
        if "Trail Blazers" in q or "Trail Blazers" in t:
            if "playoffs" in q.lower() or "playoffs" in t.lower():
                print("EVENT:", t, "| end:", e.get("endDate"))
                print("  Q:", q, "| prices:", m.get("outcomePrices"), "| liq:", m.get("liquidityNum") or m.get("liquidity"))
                print("  tokens:", m.get("clobTokenIds"))
                print("  vol:", m.get("volume"), "vol24:", m.get("volume24hr"))

json.dump({s: {"counts": out[s]} for s in out}, open("/home/ubuntu/paper-sim/round12/raw/counts.json", "w"), indent=1)
print("\ncounts saved")
