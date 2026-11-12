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

# Sunday late + Monday events only, with main markets
rows = []
for e in events.values():
    ed = end_dt(e)
    if not ed or ed < NOW:
        continue
    t = e.get("title") or ""
    if " - " in t:  # props sub-events
        continue
    rows.append((ed, e))
rows.sort(key=lambda x: x[0])
print("== NFL main game events upcoming ==")
for ed, e in rows:
    vol = e.get("volume24hr") or 0
    liq = e.get("liquidityNum") or e.get("liquidity") or 0
    print(f"[vol24 {vol/1000:.1f}k | liq {liq/1000:.1f}k | end {ed.strftime('%a %m-%d %H:%M')}] {e.get('title','?')}")
    for m in e.get("markets", []):
        q = m.get("question") or ""
        if q == e.get("title") or (" vs" in q and "Spread" not in q and "O/U" not in q and "First" not in q and "Quarter" not in q and "race" not in q.lower()):
            mv = m.get("volume24hr") or 0
            toks = m.get("clobTokenIds", "")
            print(f"    MAIN: {q[:70]} | p={m.get('outcomePrices')} | vol24={mv/1000:.1f}k")
            print(f"         tokens={toks}")

print()
print("== WS TB@MIL event full markets ==")
d = json.load(open("/home/ubuntu/paper-sim/round13/raw/gamma_mlb.json"))
for e in d.get("data", []):
    if e.get("title") == "Tampa Bay Rays vs. Milwaukee Brewers":
        for m in e.get("markets", []):
            print(f"    {m.get('question','?')[:85]} | p={m.get('outcomePrices')} | vol24={m.get('volume24hr')} | close={m.get('endDate')}")
            print(f"        tokens={m.get('clobTokenIds','')[:150]}")
