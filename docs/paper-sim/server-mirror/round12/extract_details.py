import json, glob

pages = []
for fn in glob.glob("/home/ubuntu/paper-sim/round12/raw/*_p*.json"):
    pages.extend(json.load(open(fn)).get("data", []))
events = {e.get("id"): e for e in pages}

WANT = [
    "MLB World Series Champion 2026",
    "Tampa Bay Rays vs. Cleveland Guardians",
    "Tampa Bay Rays vs. Milwaukee Brewers",
    "Bengals vs. Ravens",
    "49ers vs. Falcons",
    "Browns vs. Titans",
    "Chiefs vs. Seahawks",
    "Packers vs. Lions",
    "Cowboys vs. Eagles",
    "Giants vs. Texans",
    "Steelers vs. Saints",
    "Rams vs. Raiders",
    "Colts vs. Vikings",
    "Buccaneers vs. Panthers",
    "Cavaliers vs. 76ers",
    "Nuggets vs. Thunder",
    "Trail Blazers vs. Kings",
    "Knicks vs. Celtics",
]

out = []
for e in events.values():
    t = (e.get("title") or "").strip()
    if t in WANT or ("Starting QB" in t):
        rec = {"event": t, "endDate": e.get("endDate"), "volume24hr": e.get("volume24hr"), "markets": []}
        for m in (e.get("markets") or []):
            q = (m.get("question") or "")
            # keep main moneyline / series / spread-adjacent only
            keep = False
            if t == "MLB World Series Champion 2026":
                prices = json.loads(m.get("outcomePrices") or "[]")
                try:
                    yes = float(prices[0])
                except Exception:
                    yes = 0
                if yes > 0.02:
                    keep = True
            elif "Starting QB" in t:
                keep = True
            else:
                # main market question == title, or contains 'win' / series phrasing
                if q.strip() == t or q.startswith("Will ") is False:
                    keep = q.strip() == t
                else:
                    keep = q.strip() == t
            if keep:
                rec["markets"].append({
                    "q": q,
                    "outcomes": json.loads(m.get("outcomes") or "[]"),
                    "prices": json.loads(m.get("outcomePrices") or "[]"),
                    "spread": m.get("spread"),
                    "liq": m.get("liquidityNum"),
                    "tokens": json.loads(m.get("clobTokenIds") or "[]"),
                    "vol24": m.get("volume24hr"),
                    "bestBid": m.get("bestBid"),
                    "bestAsk": m.get("bestAsk"),
                })
        out.append(rec)

json.dump(out, open("/home/ubuntu/paper-sim/round12/raw/shortlist.json", "w"), indent=1)
for r in out:
    print("==== %s | end %s | vol24 %.0f" % (r["event"], r["endDate"], r["volume24hr"] or 0))
    for m in r["markets"][:14]:
        pr = m["prices"]
        print("   %-70s %s | liq %s | bid/ask %s/%s" % (m["q"][:70], pr, m["liq"], m["bestBid"], m["bestAsk"]))
