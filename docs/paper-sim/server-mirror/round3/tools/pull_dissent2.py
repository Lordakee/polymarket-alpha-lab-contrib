import json, urllib.request, time, datetime

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
d = json.load(open("/home/ubuntu/paper-sim/round3/raw/dissent_markets.json"))
for slug in ["how-many-dissent-at-the-january-fed-meeting-20260730001232359",
             "how-many-dissent-at-the-december-fed-meeting-20260730000304473"]:
    try:
        e = get(GAMMA + "/events?slug=" + slug)[0]
        d["events"][slug] = e
    except Exception as ex:
        print("ERR", slug, ex); continue
    print()
    print("=== %s | %s | end %s" % (slug, e.get("title"), str(e.get("endDate"))[:10]))
    sa = 0.0; sm = 0.0
    for m in e.get("markets", []):
        raw = m.get("clobTokenIds")
        try: toks = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception: toks = []
        b = a = None; dep = {}
        if len(toks) == 2:
            try:
                bk = get(CLOB + "/book?token_id=" + toks[0])
                bids = sorted(bk.get("bids", []), key=lambda x: -float(x["price"]))[:4]
                asks = sorted(bk.get("asks", []), key=lambda x: float(x["price"]))[:4]
                b = bids[0]["price"] if bids else None
                a = asks[0]["price"] if asks else None
                dep = {"bids": bids, "asks": asks}
                d["books"]["%s|%s" % (slug, m["id"])] = {"q": m.get("question"), "tok": toks[0], "dep": dep}
            except Exception as ex:
                print("  book ERR", ex)
            time.sleep(0.3)
        if a: sa += float(a)
        bid = float(b) if b else 0; ask = float(a) if a else 0
        sm += (bid + ask) / 2.0
        print("  %-58s bid=%-6s ask=%-6s liq=%s" % (str(m.get("question"))[:58], b, a, m.get("liquidityNum")))
    print("  SUM asks: %.4f  SUM mids: %.4f" % (sa, sm))
json.dump(d, open("/home/ubuntu/paper-sim/round3/raw/dissent_markets.json", "w"), indent=1)
print()
print("saved dissent_markets.json")
