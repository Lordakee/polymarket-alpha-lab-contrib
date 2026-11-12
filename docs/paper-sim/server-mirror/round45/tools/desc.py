import json, glob, sys

def load(f):
    d = json.load(open(f))
    return d["data"] if isinstance(d, dict) else d

patterns = sys.argv[1:]
for f in glob.glob("/home/ubuntu/paper-sim/round45/raw/evt_*.json"):
    try: evs = load(f)
    except Exception: continue
    if not isinstance(evs, list) or not evs: continue
    e = evs[0]
    for m in e.get("markets", []):
        q = m.get("question") or ""
        if any(p in q for p in patterns):
            print("FILE:", f.split("/")[-1])
            print("###", q)
            print("DESC:", (m.get("description") or "")[:1000].replace("\n", " "))
            print("SRC:", (m.get("resolutionSource") or "")[:250])
            print("---")
