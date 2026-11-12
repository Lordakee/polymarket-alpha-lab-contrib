#!/usr/bin/env python3
import json, urllib.request, urllib.parse, os, time

OUT = os.path.expanduser("~/paper-sim/round45/raw")

def http_json(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-sim-round45/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == 2: return {"_err": repr(e)}
            time.sleep(1.5 + i)

d = json.load(open(os.path.join(OUT, "fr_advance_event.json")))
key_names = ["Le Pen", "Mélenchon", "Lisnard", "Philippe", "Bardella", "Zemmour", "Lagarde", "another person"]
res = {}
for m in d["data"][0].get("markets", []):
    q = m.get("question") or ""
    if not any(k in q for k in key_names): continue
    cid = m.get("conditionId")
    tr = http_json("https://data-api.polymarket.com/trades?market=%s&limit=500" %% cid) or []
    res[q] = [{"ts": t.get("time"), "side": t.get("side"), "price": t.get("price"), "size": t.get("size")} for t in tr]
    time.sleep(0.4)
json.dump(res, open(os.path.join(OUT, "fr_key_trades.json"), "w"), indent=1)

ENTRY = 1762721587
for q, tr in res.items():
    if not tr: continue
    name = q.replace("Will ", "").replace(" advance to the second round of the next French presidential election?", "")[:22]
    before = [t for t in tr if t["ts"] <= ENTRY]
    after = [t for t in tr if t["ts"] > ENTRY]
    entry_p = before[-1]["price"] if before else None
    print("%-24s n=%-4d entry_last_trade=%-7s | first_after=%-7s | last=%-7s @%s" % (
        name, len(tr), entry_p, after[0]["price"] if after else None, tr[-1]["price"],
        time.strftime("%m-%d", time.gmtime(tr[-1]["ts"]))))
