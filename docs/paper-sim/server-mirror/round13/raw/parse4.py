import json

# NFL: dump all events with any volume
d = json.load(open("/home/ubuntu/paper-sim/round13/raw/gamma_nfl.json"))
evs = d.get("data", [])
print("NFL total events:", len(evs))
for ev in evs:
    vol = ev.get("volume24hr") or 0
    tv = ev.get("volume") or 0
    liq = ev.get("liquidityNum") or ev.get("liquidity") or 0
    title = ev.get("title", "?")
    end = (ev.get("endDate") or "?")[:10]
    if vol > 500 or tv > 20000 or "Week 7" in title or "week-7" in (ev.get("slug") or ""):
        print(f"[vol24 {vol/1000:.1f}k | tot {tv/1000:.1f}k | liq {liq/1000:.1f}k | end {end}] {title}")
        for m in ev.get("markets", [])[:4]:
            if (m.get("volume24hr") or 0) > 300:
                print(f"    {m.get('question','?')[:75]} | p={m.get('outcomePrices')} | vol24={(m.get('volume24hr') or 0)/1000:.1f}k")

print()
print("=" * 30, "MLB all events")
d2 = json.load(open("/home/ubuntu/paper-sim/round13/raw/gamma_mlb.json"))
for ev in d2.get("data", []):
    title = ev.get("title", "?")
    liq = ev.get("liquidityNum") or ev.get("liquidity") or 0
    end = (ev.get("endDate") or "?")[:16]
    vol = ev.get("volume24hr") or 0
    if liq > 20000 or vol > 3000:
        print(f"[vol24 {vol/1000:.1f}k | liq {liq/1000:.1f}k | end {end}] {title}")
        for m in ev.get("markets", [])[:3]:
            print(f"    {m.get('question','?')[:75]} | p={m.get('outcomePrices')} | vol24={(m.get('volume24hr') or 0)/1000:.1f}k")
