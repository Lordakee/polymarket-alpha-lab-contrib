import json

for tag in ["nba", "nfl", "mlb"]:
    d = json.load(open(f"/home/ubuntu/paper-sim/round13/raw/gamma_{tag}.json"))
    evs = d.get("data", d if isinstance(d, list) else [])
    print("=" * 30, tag.upper(), "events:", len(evs))
    for ev in evs[:45]:
        vol = ev.get("volume24hr") or 0
        liq = ev.get("liquidityNum") or ev.get("liquidity") or 0
        title = ev.get("title", "?")
        end = ev.get("endDate", "?")
        print(f"[{vol/1000:.1f}k vol24 | liq {liq/1000:.1f}k | end {end[:10]}] {title} (id={ev.get('id')})")
        for m in ev.get("markets", [])[:8]:
            outcomes = m.get("outcomes", "")
            prices = m.get("outcomePrices", "")
            tokens = m.get("clobTokenIds", "")
            mv = m.get("volume24hr") or 0
            print(f"    mkt: {m.get('question','?')[:70]} | p={prices} | vol24={mv/1000:.1f}k | tokens={tokens[:120]}")
