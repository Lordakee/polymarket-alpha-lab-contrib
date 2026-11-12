import json, urllib.request, gzip, time, datetime

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
SLUGS = [
    "epl-mun-tot-2026-10-10", "epl-ips-ful-2026-10-10", "epl-che-bou-2026-10-10",
    "epl-ast-bre-2026-10-10", "epl-sun-bri-2026-10-10", "epl-cry-not-2026-10-11",
    "lal-bar-get-2026-10-10", "lal-rea-vil-2026-10-10", "lal-ala-mad-2026-10-10",
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

now = datetime.datetime.now(datetime.timezone.utc)
print("UTC now:", now.isoformat())

books = {}
for slug in SLUGS:
    evs = get(BASE + "/events?slug=" + slug)
    ev = evs[0]
    ev_books = {"title": ev.get("title"), "gameStart": None, "markets": []}
    for m in ev.get("markets", []):
        if m.get("closed"): continue
        g = m.get("gameStartTime")
        if g and (ev_books["gameStart"] is None or g < ev_books["gameStart"]):
            ev_books["gameStart"] = g
        toks = m.get("clobTokenIds")
        try: toks = json.loads(toks) if isinstance(toks, str) else toks
        except Exception: pass
        outcomes = m.get("outcomes")
        try: outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        except Exception: pass
        prices = m.get("outcomePrices")
        try: prices = json.loads(prices) if isinstance(prices, str) else prices
        except Exception: pass
        entry = {"q": m.get("question"), "outcomes": outcomes, "gamma_prices": prices,
                 "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
                 "tokens": toks, "book": None}
        # fetch CLOB book for each token
        tok_books = []
        for tok in (toks or []):
            try:
                b = get(CLOB + "/book?token_id=" + tok)
                bids = sorted(b.get("bids", []), key=lambda x: -float(x["price"]))[:3]
                asks = sorted(b.get("asks", []), key=lambda x: float(x["price"]))[:3]
                tok_books.append({"bids": bids, "asks": asks})
            except Exception as e:
                tok_books.append({"err": str(e)})
            time.sleep(0.25)
        entry["book"] = tok_books
        ev_books["markets"].append(entry)
        time.sleep(0.2)
    books[slug] = ev_books
    gs = ev_books["gameStart"]
    status = "UNKNOWN"
    if gs:
        try:
            dt = datetime.datetime.fromisoformat(gs.replace("Z", "+00:00"))
            status = "IN_PLAY" if dt <= now else "PRE_MATCH(in %.1fh)" % ((dt - now).total_seconds() / 3600)
        except Exception:
            status = "PARSE_ERR"
    print("%-28s start=%s %s  markets=%d" % (slug, gs, status, len(ev_books["markets"])))
    for mk in ev_books["markets"]:
        bb = mk["book"][0]["bids"][0]["price"] if mk["book"] and mk["book"][0].get("bids") else "?"
        ba = mk["book"][0]["asks"][0]["price"] if mk["book"] and mk["book"][0].get("asks") else "?"
        print("    %-55s bid=%s ask=%s gamma=%s" % (str(mk["q"])[:55], bb, ba, mk["gamma_prices"]))

with open("/home/ubuntu/paper-sim/soccer/raw/match_books.json", "w") as f:
    json.dump(books, f, indent=1)
print("saved match_books.json")
