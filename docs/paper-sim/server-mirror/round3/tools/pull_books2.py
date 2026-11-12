import json, urllib.request, time, datetime

CLOB = "https://clob.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
d = json.load(open("/home/ubuntu/paper-sim/round3/raw/ou25_events.json"))
out = {}
for slug in d:
    mm = d[slug].get(slug + "-more-markets", {}).get("markets", [])
    for m in mm:
        q = str(m.get("question") or "")
        keep = None
        if q.endswith(": O/U 2.5"): keep = "OU25"
        elif q.endswith(": O/U 1.5"): keep = "OU15"
        elif q.endswith(": O/U 3.5"): keep = "OU35"
        elif q.endswith("Both Teams to Score"): keep = "BTTS"
        if not keep: continue
        raw = m.get("clobTokenIds")
        try: toks = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception: toks = []
        oc = json.loads(m["outcomes"]) if isinstance(m.get("outcomes"), str) else (m.get("outcomes") or [])
        if len(toks) != 2: continue
        key = "%s|%s" % (slug, keep)
        row = {"q": q, "outcomes": oc, "gamma_bid": m.get("bestBid"), "gamma_ask": m.get("bestAsk"), "books": []}
        for tok, oname in zip(toks, oc):
            try:
                b = get(CLOB + "/book?token_id=" + tok)
                bids = sorted(b.get("bids", []), key=lambda x: -float(x["price"]))[:5]
                asks = sorted(b.get("asks", []), key=lambda x: float(x["price"]))[:5]
                row["books"].append({"token": tok, "outcome": oname, "bids": bids, "asks": asks})
            except Exception as e:
                row["books"].append({"err": str(e)})
            time.sleep(0.3)
        out[key] = row
        for bk in row["books"]:
            if "err" in bk: print("  ERR", key, bk["err"]); continue
            b = bk["bids"][0] if bk["bids"] else None
            a = bk["asks"][0] if bk["asks"] else None
            print("%-14s %-8s %-6s bid=%-6s x%-8s ask=%-6s x%s" % (
                slug.replace("ucl-","")[:14], keep, str(bk.get("outcome"))[:6],
                b["price"] if b else "-", (b["size"] if b else ""),
                a["price"] if a else "-", (a["size"] if a else "")))
json.dump(out, open("/home/ubuntu/paper-sim/round3/raw/ou25_books.json", "w"), indent=1)
print("saved ou25_books.json with", len(out), "rows")
