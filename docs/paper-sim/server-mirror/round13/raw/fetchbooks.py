import json, subprocess, os

tm = json.load(open("/home/ubuntu/paper-sim/round13/raw/token_map.json"))
os.makedirs("/home/ubuntu/paper-sim/round13/raw/books", exist_ok=True)
out = {}
for name, tok in tm.items():
    fn = f"/home/ubuntu/paper-sim/round13/raw/books/{name}.json"
    subprocess.run(["curl", "-s", f"https://clob.polymarket.com/book?token_id={tok}", "-o", fn], check=False)
    try:
        b = json.load(open(fn))
        bids = sorted(b.get("bids", []), key=lambda x: -float(x["price"]))
        asks = sorted(b.get("asks", []), key=lambda x: float(x["price"]))
        bb = float(bids[0]["price"]) if bids else None
        ba = float(asks[0]["price"]) if asks else None
        print(f"{name:28s} bid={bb}  ask={ba}  (top bid sz {float(bids[0]['size']) if bids else 0:.0f}, top ask sz {float(asks[0]['size']) if asks else 0:.0f})")
        out[name] = {"best_bid": bb, "best_ask": ba,
                     "bid_ladder": [(float(x["price"]), float(x["size"])) for x in bids[:4]],
                     "ask_ladder": [(float(x["price"]), float(x["size"])) for x in asks[:4]]}
    except Exception as ex:
        print(f"{name:28s} ERR {ex} raw={open(fn).read()[:80]}")

json.dump(out, open("/home/ubuntu/paper-sim/round13/raw/clob_books.json", "w"), indent=1)
print("saved clob_books.json")
