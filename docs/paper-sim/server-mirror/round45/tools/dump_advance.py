import json

def parse_p(p):
    if p is None: return None
    if isinstance(p, str):
        try: p = json.loads(p)
        except Exception: return None
    try: return (float(p[0]), float(p[1]))
    except Exception: return None

d = json.load(open("/home/ubuntu/paper-sim/round45/raw/fr_advance_event.json"))
e = d["data"][0]
ms = e.get("markets", [])
print("EVENT:", e.get("slug"), "| end:", e.get("endDate"), "| markets:", len(ms))
yes_sum = 0.0; n_priced = 0
for m in ms:
    q = m.get("question") or "?"
    pp = parse_p(m.get("outcomePrices"))
    liq = m.get("liquidityNum"); vol = m.get("volumeNum"); closed = m.get("closed"); mid = m.get("id")
    if pp is None:
        print("%-95s | NO-PRICE | closed=%s | %s" % (q[:95], closed, mid)); continue
    yes, no = pp
    if yes > 0.0004 or "another" in q.lower():
        yes_sum += yes; n_priced += 1
    print("%-95s | YES=%-7s NO=%-7s liq=%-9s vol=%-12s closed=%s | %s" % (q[:95], round(yes,4), round(no,4), liq, vol, closed, mid))
print()
print("count YES>0.0004-or-another:", n_priced, " sum YES:", round(yes_sum,4))
