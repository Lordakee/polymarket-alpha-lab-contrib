import json

d = json.load(open("/home/ubuntu/paper-sim/round45/raw/fr_event_next-french-presidential-elect.json"))
e = d["data"][0]
print("EVENT:", e.get("slug"), "| title:", e.get("title"), "| end:", e.get("endDate"), "| markets:", len(e.get("markets", [])))
for m in e.get("markets", []):
    q = (m.get("question") or "?")[:85]
    p = m.get("outcomePrices")
    liq = m.get("liquidityNum"); vol = m.get("volumeNum")
    print("  %-85s | p=%s | liq=%s | vol=%s | closed=%s | gid=%s" % (q, p, liq, vol, m.get("closed"), (m.get("id") or "")[:8]))
