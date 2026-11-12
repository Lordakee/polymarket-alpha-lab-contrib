import json, urllib.request, time, datetime

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
FIX = ["ucl-atm-mnu-2026-10-13", "ucl-ars-lil-2026-10-13", "ucl-int-bru-2026-10-13", "ucl-gal-fcb-2026-10-13"]
out = {}
for slug in FIX:
    fam = {}
    for s in [slug, slug + "-more-markets"]:
        try:
            e = get(GAMMA + "/events?slug=" + s)
            if e: fam[s] = e[0]
        except Exception as ex:
            print("ERR", s, ex)
        time.sleep(0.3)
    out[slug] = fam
    print()
    print("=== %s : %s" % (slug, fam.get(slug, {}).get("title", "?")))
    for s, e in fam.items():
        for m in e.get("markets", []):
            grp = str(m.get("group") or "")
            q = str(m.get("q") or m.get("question") or "")
            oc = m.get("outcomes") or []
            if ("O/U" in grp or "Goals" in q or "goals" in q or "Total" in q or "Both Teams" in grp) or (s.endswith("more-markets") and False):
                toks = m.get("tokens")
                try: toks = json.loads(toks) if isinstance(toks, str) else toks
                except Exception: toks = []
                print("  %-42s %-24s out=%s bid=%s ask=%s liq=%s" % (grp[:42], q[:24], ",".join(oc), m.get("bestBid"), m.get("bestAsk"), m.get("liquidityNum")))
json.dump(out, open("/home/ubuntu/paper-sim/round3/raw/ou25_events.json", "w"), indent=1)
print()
print("saved ou25_events.json")
