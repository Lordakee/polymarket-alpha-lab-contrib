#!/usr/bin/env python3
"""Round45A fetch F: shutdown/russia/turnout books + FR createdAt + price history."""
import json, urllib.request, urllib.parse, os, time

OUT = os.path.expanduser("~/paper-sim/round45/raw")

def http_json(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-sim-round45/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retries - 1: return {"_err": repr(e)}
            time.sleep(1.5 + i)

def toks(m):
    c = m.get("clobTokenIds")
    if isinstance(c, str):
        try: c = json.loads(c)
        except Exception: c = None
    return c or [None, None]

# books: shutdown by dec 12/31, russia-ukraine talks legs, house turnout key legs
want = {
  "government-shutdown-by": "clob_shutdown_books",
  "russia-x-ukraine-peace-talks-byptptpt-20260609012540716": "clob_ru_talks_books",
  "2026-midterms-house-turnout": "clob_turnout_books",
}
for slug, name in want.items():
    d = http_json("https://gamma-api.polymarket.com/events?slug=" + slug)
    json.dump(d, open(os.path.join(OUT, "evt_%s.json" % slug[:30]), "w"), indent=1)
    bb = {}
    if d:
        for m in d[0].get("markets", []):
            t = toks(m)
            bb[m.get("question")] = {"yes_token": t[0], "book": http_json("https://clob.polymarket.com/book?token_id=" + str(t[0]))}
            time.sleep(0.3)
    json.dump(bb, open(os.path.join(OUT, name + ".json"), "w"), indent=1)

# FR advance: createdAt per leg + price history since Oct 8 for our audit legs
d = json.load(open(os.path.join(OUT, "fr_advance_event.json")))
ms = d["data"][0].get("markets", [])
meta = []
for m in ms:
    meta.append({"q": m.get("question"), "id": m.get("id"), "createdAt": m.get("createdAt"),
                 "startDate": m.get("startDate"), "clobTokenIds": m.get("clobTokenIds"), "umaResolutionStatus": m.get("umaResolutionStatus"),
                 "closed": m.get("closed"), "yes": m.get("outcomePrices")})
json.dump(meta, open(os.path.join(OUT, "fr_advance_meta.json"), "w"), indent=1)

key_names = ["Le Pen", "Mélenchon", "Lisnard", "Philippe", "Bardella", "Zemmour", "Lagarde", "Glucksmann", "Attal", "Hollande"]
hist = {}
for m in ms:
    q = m.get("question") or ""
    if not any(k in q for k in key_names): continue
    t = toks(m)
    h = http_json("https://clob.polymarket.com/prices-history?market=%s&startTs=1760000000&endTs=1762752000&fidelity=180" % str(t[0]))
    pts = (h or {}).get("history") or []
    hist[q] = [{"t": p.get("t"), "p": p.get("p")} for p in pts]
    time.sleep(0.35)
json.dump(hist, open(os.path.join(OUT, "fr_advance_history.json"), "w"), indent=1)
print("DONE batch F; history legs:", len(hist))
