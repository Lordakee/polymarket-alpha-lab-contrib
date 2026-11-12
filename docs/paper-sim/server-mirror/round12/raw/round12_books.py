import json, urllib.request

def book(tid):
    try:
        with urllib.request.urlopen("https://clob.polymarket.com/book?token_id=%s" % tid, timeout=20) as r:
            b = json.load(r)
        bids = sorted([(float(x["price"]), float(x["size"])) for x in b.get("bids", [])], reverse=True)
        asks = sorted([(float(x["price"]), float(x["size"])) for x in b.get("asks", [])])
        best_b = bids[0] if bids else None
        best_a = asks[0] if asks else None
        bdepth = sum(s for p, s in bids if p >= 0.5)  # depth for YES side proxy
        return {"best_bid": best_b, "best_ask": best_a, "n_bids": len(bids), "n_asks": len(asks)}
    except Exception as ex:
        return {"error": str(ex)}

tokens = {
  "spy740_low_oct_YES": "71311715749969956220881538596899029017947486228167686230855150261949942110158",
  "spy740_low_oct_NO": "52091564294406918879078560382571275669174153247020106446363800145824842641569",
  "fed_nochange_YES": "111061902544814266207267295505639408607400625795891618462682726460921782993748",
  "fed_hike25_YES": "55159722761418013044126414276680602270318000841690689684819994448621694923050",
  "senate_D_YES": "113287701564209339913693347405685749986285999146352375265161592243948562084773",
  "senate_R_YES": "51939490109676186832507970701169130490548061087912630009168726706475001411420",
  "house_D_YES": "83247781037352156539108067944461291821683755894607244160607042790356561625563",
}
out = {k: book(v) for k, v in tokens.items()}
json.dump(out, open("/home/ubuntu/paper-sim/round12/raw/books.json", "w"), indent=1)
for k, v in out.items():
    print(k, "->", v)

# Senate race level markets from elections tag
d = json.load(open("events_elections.json"))
evs = d.get("data", d) if isinstance(d, dict) else d
races = {}
for e in evs:
    t = e.get("title", "")
    if "Senate Election Winner" in t or "Senate Election" in t:
        ms = []
        for m in e.get("markets", []):
            try:
                p = round(float(json.loads(m.get("outcomePrices") or "[]")[0]) * 100)
            except Exception:
                p = None
            ms.append(((m.get("question") or "")[:60], p, m.get("clobTokenIds","")))
        races[t] = ms
print("\n=== Senate races ===")
for t, ms in sorted(races.items()):
    print("--", t)
    for q, p, tok in ms[:8]:
        print("   %-62s %s" % (q, p))
json.dump(races, open("/home/ubuntu/paper-sim/round12/raw/senate_races.json", "w"), indent=1)
