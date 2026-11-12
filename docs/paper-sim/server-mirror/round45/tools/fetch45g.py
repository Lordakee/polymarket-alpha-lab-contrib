#!/usr/bin/env python3
import json, urllib.request, os, time

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

meta = json.load(open(os.path.join(OUT, "fr_advance_meta.json")))
key_names = ["Le Pen", "Mélenchon", "Lisnard", "Philippe", "Bardella", "Zemmour", "Lagarde", "Glucksmann", "Attal", "Hollande", "another person"]
WINDOWS = [(1760007600, 1760526000), (1760526000, 1761044400), (1761044400, 1761562800), (1761562800, 1762081200), (1762081200, 1762600000), (1762600000, 1762752000)]
hist = {}
for m in meta:
    q = m.get("q") or ""
    if not any(k in q for k in key_names): continue
    t = json.loads(m["clobTokenIds"]) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
    if not t or not t[0]: continue
    pts = []
    for (a, b) in WINDOWS:
        h = http_json("https://clob.polymarket.com/prices-history?market=%s&startTs=%d&endTs=%d&fidelity=240" % (t[0], a, b))
        pts += (h or {}).get("history") or []
        time.sleep(0.3)
    pts = sorted({(p["t"], p["p"]) for p in pts})
    hist[q] = [{"t": t_, "p": p_} for (t_, p_) in pts]
json.dump(hist, open(os.path.join(OUT, "fr_advance_history.json"), "w"), indent=1)
print("legs:", len(hist), "total pts:", sum(len(v) for v in hist.values()))
