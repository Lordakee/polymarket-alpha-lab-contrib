import json, sys

def best(book, side):
    """side=ask -> lowest ask; side=bid -> highest bid. returns (price, size)"""
    lv = book.get(side) or []
    if not lv: return (None, 0)
    if side == "asks":
        p = min(float(x["price"]) for x in lv); s = sum(float(x["size"]) for x in lv if float(x["price"]) <= p + 1e-9)
    else:
        p = max(float(x["price"]) for x in lv)
        s = sum(float(x["size"]) for x in lv if float(x["price"]) >= p - 1e-9)
    return (p, s)

f = sys.argv[1]
books = json.load(open(f))
for q, v in books.items():
    b = v.get("book") or {}
    if "_err" in b:
        print("%-70s ERR %s" % (q[:70], b["_err"])); continue
    ab, asz = best(b, "asks"); bb, bsz = best(b, "bids")
    print("%-72s ask=%-7s(%-7s) bid=%-7s(%-7s)" % (q[:72], ab, round(asz,1), bb, round(bsz,1)))
