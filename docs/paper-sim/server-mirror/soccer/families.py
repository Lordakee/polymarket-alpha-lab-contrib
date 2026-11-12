import json, urllib.request, gzip, time

BASE = "https://gamma-api.polymarket.com"
SLUGS = [
    "epl-mun-tot-2026-10-10-more-markets", "epl-mun-tot-2026-10-10-exact-score",
    "epl-cry-not-2026-10-11-more-markets", "epl-cry-not-2026-10-11-exact-score",
    "lal-bar-get-2026-10-10-more-markets", "lal-bar-get-2026-10-10-exact-score",
    "lal-rea-vil-2026-10-10-more-markets", "lal-rea-vil-2026-10-10-exact-score",
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

out = {}
for slug in SLUGS:
    try:
        evs = get(BASE + "/events?slug=" + slug)
        if not evs:
            print("MISSING", slug); continue
        ev = evs[0]
        mk = []
        for m in ev.get("markets", []):
            if m.get("closed"): continue
            outcomes = m.get("outcomes"); prices = m.get("outcomePrices")
            try: outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
            except Exception: pass
            try: prices = json.loads(prices) if isinstance(prices, str) else prices
            except Exception: pass
            mk.append({
                "q": m.get("question"), "groupItemTitle": m.get("groupItemTitle"),
                "outcomes": outcomes, "prices": prices,
                "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
                "liq": m.get("liquidityNum") or m.get("liquidity"),
                "vol24": m.get("volume24hr"), "tokens": m.get("clobTokenIds"),
            })
        out[slug] = {"title": ev.get("title"), "markets": mk}
        print("OK", slug, "open=", len(mk))
        time.sleep(0.3)
    except Exception as e:
        print("ERR", slug, e)

with open("/home/ubuntu/paper-sim/soccer/raw/family_events.json", "w") as f:
    json.dump(out, f, indent=1)

# print structured view
for slug, ev in out.items():
    print()
    print("=== " + slug + " (" + str(ev["title"]) + ") ===")
    yes_sum = 0.0
    for m in ev["markets"]:
        oc = m["outcomes"] or []
        pr = m["prices"] or []
        bid, ask = m["bestBid"], m["bestAsk"]
        try:
            bid = float(bid) if bid not in (None, "") else None
            ask = float(ask) if ask not in (None, "") else None
        except Exception:
            bid = ask = None
        ypr = None
        if oc and pr and oc[0].lower() in ("yes", "true"):
            try: ypr = float(pr[0])
            except Exception: pass
        if ypr is not None: yes_sum += ypr
        print("  %-70s yes=%s bid=%s ask=%s liq=%s" % (str(m["q"])[:70], ypr, bid, ask, m["liq"]))
    print("  SUM(yes mids) = %.4f" % yes_sum)
