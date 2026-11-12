import json, sys

f = sys.argv[1]
d = json.load(open(f))
evs = d["data"].get("events", [])
print("file:", f.split("/")[-1], "| events:", len(evs))
for e in evs[:15]:
    ms = e.get("markets") or []
    print("EVT:", (e.get("slug") or "")[:70], "|", (e.get("title") or "")[:60], "| end:", (e.get("endDate") or "")[:10], "| mkts:", len(ms))
    for m in ms[:4]:
        print("    -", (m.get("question") or "?")[:75], "| p=", m.get("outcomePrices"))
