import json, glob, datetime

now = datetime.datetime(2026, 10, 22)
cutoff = now + datetime.timedelta(days=45)
seen = {}
for f in glob.glob("events_*.json"):
    tag = f.replace("events_", "").replace(".json", "")
    d = json.load(open(f))
    evs = d.get("data", d) if isinstance(d, dict) else d
    for e in evs:
        t = e.get("title", "")
        if t not in seen:
            seen[t] = (tag, e)

rows = []
for t, (tag, e) in seen.items():
    ed = e.get("endDate", "")
    try:
        end = datetime.datetime.strptime(ed[:10], "%Y-%m-%d")
    except Exception:
        end = None
    if not end or end > cutoff:
        continue
    vol = e.get("volume24hr", 0) or 0
    liq = e.get("liquidityNum", 0) or e.get("liquidity", 0) or 0
    if not isinstance(liq, (int, float)):
        try:
            liq = float(liq)
        except Exception:
            liq = 0
    rows.append((vol, liq, t, tag, ed, e.get("markets", [])))
rows.sort(reverse=True)

out = []
for vol, liq, t, tag, ed, ms in rows:
    mks = []
    for m in ms[:10]:
        try:
            prices = json.loads(m.get("outcomePrices") or "[]")
            p = round(float(prices[0]) * 100) if prices else None
        except Exception:
            p = None
        mks.append({
            "q": (m.get("question") or "")[:80],
            "yes1h": p,
            "tokens": m.get("clobTokenIds", ""),
            "liq": m.get("liquidityNum", 0),
            "vol": m.get("volumeNum", 0),
        })
    out.append({"event": t, "tag": tag, "endDate": ed[:10], "vol24h": round(vol),
                "liq": round(liq), "markets": mks})

json.dump(out, open("/home/ubuntu/paper-sim/round12/raw/summary_45d.json", "w"), indent=1)
print("events ending <= %s: %d" % (cutoff.date(), len(out)))
for r in out[:50]:
    print("%10d %9d %s [%s] %s" % (r["vol24h"], r["liq"], r["endDate"], r["tag"][:6], r["event"][:75]))
