import json, urllib.request, time

RAW="/home/ubuntu/paper-sim/round12/raw"
def get(url):
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out={"crypto":[]}
for slug in ["crypto","ethereum","bitcoin"]:
    out[slug]=[]
    for off in range(0,1000,100):
        try:
            d=get(f"https://gamma-api.polymarket.com/events/pagination?limit=100&offset={off}&active=true&order=volume24hr&ascending=false&tag_slug={slug}")
        except Exception as ex:
            print(slug,off,"ERR",ex); break
        evs=d.get("data") or []
        if not evs: break
        out[slug].extend(evs)
        print(slug,off,"got",len(evs),"cum",len(out[slug]),flush=True)
        time.sleep(0.4)

json.dump(out,open(RAW+"/discover12.json","w"))
# dedupe events by id, list titles mentioning BTC/ETH price
seen=set(); n=0
for slug in out:
    for e in out[slug]:
        eid=e.get("id")
        if eid in seen: continue
        seen.add(eid); n+=1
print("total unique events:",n)
