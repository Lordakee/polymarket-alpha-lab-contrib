import json, glob, datetime

NOW = datetime.datetime(2026, 10, 23, 0, 55, tzinfo=datetime.timezone.utc)
events = {}
for fn in glob.glob("/home/ubuntu/paper-sim/round13/raw/nfl_p*.json"):
    d = json.load(open(fn))
    for e in d.get("data", []):
        events[e.get("id")] = e

def end_dt(e):
    s = e.get("endDate") or ""
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

rows = []
for e in events.values():
    ed = end_dt(e)
    if not ed or ed < NOW - datetime.timedelta(hours=6):
        continue
    rows.append((ed, e))
rows.sort(key=lambda x: x[0])
print("NFL upcoming events:", len(rows))
for ed, e in rows[:40]:
    vol = e.get("volume24hr") or 0
    liq = e.get("liquidityNum") or e.get("liquidity") or 0
    print(f"[vol24 {vol/1000:.1f}k | liq {liq/1000:.1f}k | end {ed.strftime('%m-%d %H:%M')}] {e.get('title','?')}")
    for m in e.get("markets", [])[:3]:
        mv = m.get("volume24hr") or 0
        if mv > 500:
            print(f"    {m.get('question','?')[:78]} | p={m.get('outcomePrices')} | vol24={mv/1000:.1f}k | tokens={m.get('clobTokenIds','')[:100]}")

# POR playoffs search across all raw files
print()
print("==== POR PLAYOFFS SEARCH ====")
for fn in glob.glob("/home/ubuntu/paper-sim/round13/raw/gamma_*.json") + glob.glob("/home/ubuntu/paper-sim/round13/raw/nfl_p*.json"):
    d = json.load(open(fn))
    for e in d.get("data", []):
        t = e.get("title") or ""
        for m in e.get("markets") or []:
            q = m.get("question") or ""
            if "Trail Blazers" in q and ("playoff" in q.lower() or "playoff" in t.lower() or "Playoffs" in t):
                print("FILE:", fn.split("/")[-1])
                print("EVENT:", t, "| end:", e.get("endDate"), "| event liq:", e.get("liquidityNum") or e.get("liquidity"))
                print("  MKT:", q, "| p=", m.get("outcomePrices"), "| vol24=", m.get("volume24hr"), "| tokens=", m.get("clobTokenIds"))
