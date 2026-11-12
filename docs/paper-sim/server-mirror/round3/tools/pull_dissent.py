import json, urllib.request, time, datetime

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
out = {}
for slug in ["how-many-dissent-at-the-october-fed-meeting",
             "how-many-dissent-at-the-january-fed-meeting",
             "fed-dissent-january-2027",
             "how-many-dissent-at-the-december-fed-meeting"]:
    try:
        e = get(GAMMA + "/events?slug=" + slug)
        if e:
            out[slug] = e[0]
            print("FOUND", slug)
    except Exception as ex:
        print("ERR", slug, ex)
    time.sleep(0.3)
# also search events endpoint for january dissent via related tag
try:
    rel = get(GAMMA + "/events?closed=false&limit=100&q=" + urllib.parse.quote("dissent"))
    for e in rel:
        if e["id"] not in [x.get("id") for x in out.values()]:
            t = (e.get("title") or "").lower()
            if "dissent" in t:
                out[e["slug"]] = e
                print("SEARCH-HIT", e["slug"], "|", e.get("title"))
except Exception as ex:
    print("ERR search", ex)

books = {}
for slug, e in out.items():
    print()
    print("=== %s | %s | end %s" % (slug, e.get("title"), str(e.get("endDate"))[:10]))
    sa = 0.0
    for m in e.get("markets", []):
        raw = m.get("clobTokenIds")
        try: toks = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception: toks = []
        oc = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else (m.get("outcomes") or [])
        b = a = None
        dep = {}
        if len(toks) == 2:
            try:
                bk = get(CLOB + "/book?token_id=" + toks[0])
                bids = sorted(bk.get("bids", []), key=lambda x: -float(x["price"]))[:4]
                asks = sorted(bk.get("asks", []), key=lambda x: float(x["price"]))[:4]
                b = bids[0]["price"] if bids else None
                a = asks[0]["price"] if asks else None
                dep = {"bids": bids, "asks": asks}
                books["%s|%s" % (slug, m["id"])] = {"q": m.get("question"), "tok": toks[0], "dep": dep}
            except Exception as ex:
                print("  book ERR", ex)
            time.sleep(0.3)
        if a: sa += float(a)
        print("  %-58s bid=%-6s ask=%-6s gbid=%-6s gask=%-6s liq=%s" % (
            str(m.get("question"))[:58], b, a, m.get("bestBid"), m.get("bestAsk"), m.get("liquidityNum")))
    print("  SUM of CLOB asks: %.3f" % sa)
json.dump({"events": {k: v for k, v in out.items()}, "books": books},
          open("/home/ubuntu/paper-sim/round3/raw/dissent_markets.json", "w"), indent=1)
print("saved dissent_markets.json")
