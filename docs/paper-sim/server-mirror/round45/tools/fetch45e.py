#!/usr/bin/env python3
"""Round45A fetch E: CLOB books + price history. Read-only."""
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

# --- FR advance legs: books for key set, history for all ---
d = json.load(open(os.path.join(OUT, "fr_advance_event.json")))
e = d["data"][0]
key = ["Le Pen", "Bardella", "Zemmour", "Philippe", "Lisnard", "Mélenchon", "Mélenchon", "another person", "Lagarde", "Glucksmann", "Hollande", "Attal", "Retailleau"]
books = {}
for m in e.get("markets", []):
    q = m.get("question") or ""
    t = toks(m)
    if any(k in q for k in key):
        b = http_json("https://clob.polymarket.com/book?token_id=" + t[0])
        books[q] = {"yes_token": t[0], "book": b}
        time.sleep(0.35)
json.dump(books, open(os.path.join(OUT, "clob_fr_key_books.json"), "w"), indent=1)

# --- Fed Dec decision books (all 5) ---
d = json.load(open(os.path.join(OUT, "evt_fed_dec_decision.json")))
fb = {}
for m in d["data"][0].get("markets", []):
    t = toks(m)
    fb[m.get("question")] = {"yes_token": t[0], "book": http_json("https://clob.polymarket.com/book?token_id=" + t[0])}
    time.sleep(0.35)
json.dump(fb, open(os.path.join(OUT, "clob_fed_dec_books.json"), "w"), indent=1)

# --- CPI MoM books (all 7) ---
d = json.load(open(os.path.join(OUT, "evt_cpi_mom_oct.json")))
cb = {}
for m in d["data"][0].get("markets", []):
    t = toks(m)
    cb[m.get("question")] = {"yes_token": t[0], "book": http_json("https://clob.polymarket.com/book?token_id=" + t[0])}
    time.sleep(0.35)
json.dump(cb, open(os.path.join(OUT, "clob_cpi_mom_books.json"), "w"), indent=1)
print("DONE books E")
