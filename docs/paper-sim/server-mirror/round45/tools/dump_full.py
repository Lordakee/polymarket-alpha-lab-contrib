import json, sys

def parse_p(p):
    if p is None: return None
    if isinstance(p, str):
        try: p = json.loads(p)
        except Exception: return None
    try: return (float(p[0]), float(p[1]))
    except Exception: return None

f = sys.argv[1]
d = json.load(open(f))
evs = d["data"]
for e in (evs if isinstance(evs, list) else [evs]):
    ms = e.get("markets") or []
    print("EVT:", e.get("slug"), "| end:", (e.get("endDate") or "")[:10], "| liq:", e.get("liquidityNum"), "| mkts:", len(ms))
    for m in ms:
        pp = parse_p(m.get("outcomePrices"))
        yes = pp[0] if pp else None
        print("   %-88s YES=%-7s liq=%-9s vol=%-10s closed=%s" % ((m.get("question") or "?")[:88], round(yes,4) if yes is not None else "None", m.get("liquidityNum"), m.get("volumeNum"), m.get("closed")))
    print()
