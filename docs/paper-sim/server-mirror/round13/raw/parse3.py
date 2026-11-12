import json

for tag in ["nba", "nfl", "mlb"]:
    d = json.load(open(f"/home/ubuntu/paper-sim/round13/raw/gamma_{tag}.json"))
    evs = d.get("data", [])
    evs = [e for e in evs if (e.get("volume24hr") or 0) > 5000]
    evs.sort(key=lambda e: e.get("volume24hr") or 0, reverse=True)
    print("=" * 30, tag.upper(), "events w/ vol24>5k:", len(evs))
    for ev in evs[:25]:
        vol = ev.get("volume24hr") or 0
        liq = ev.get("liquidityNum") or ev.get("liquidity") or 0
        title = ev.get("title", "?")
        end = (ev.get("endDate") or "?")[:16]
        print(f"[vol24 {vol/1000:.1f}k | liq {liq/1000:.1f}k | end {end}] {title}")
        for m in ev.get("markets", [])[:10]:
            outcomes = m.get("outcomes", "")
            prices = m.get("outcomePrices", "")
            mv = m.get("volume24hr") or 0
            if mv < 1000 and tag != "mlb":
                continue
            toks = m.get("clobTokenIds", "")
            toks = json.loads(toks) if isinstance(toks, str) else toks
            tokinfo = ""
            if toks:
                tokinfo = " tok0=" + str(toks[0])[:20] + ("" if len(toks) < 2 else " tok1=" + str(toks[1])[:20])
            print(f"    {m.get('question','?')[:80]} | outcomes={outcomes} p={prices} vol24={mv/1000:.1f}k{tokinfo}")
