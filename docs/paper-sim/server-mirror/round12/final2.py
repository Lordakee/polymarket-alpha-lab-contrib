import json, math, datetime, urllib.request

RAW="/home/ubuntu/paper-sim/round12/raw"
NOW=datetime.datetime(2026,10,22,12,0,tzinfo=datetime.timezone.utc)
def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))
def p_touch_up(a,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if a<=0 else 0.0
    return N((mu*T-a)/sigT)+math.exp(2*mu*a/(sig*sig))*N(-(mu*T+a)/sigT)
def p_touch_dn(x,mu,sig,T): return p_touch_up(x,-mu,sig,T)

cd={}
for s,f in [("ETH","eth_candles"),("BTC","btc_candles")]:
    rows=sorted(json.load(open(f"{RAW}/{f}.json")),key=lambda r:r[0])
    cd[s]={"closes":[r[4] for r in rows],"lows":[r[1] for r in rows],"highs":[r[2] for r in rows],"ts":[r[0] for r in rows]}
SPOT={s:cd[s]["closes"][-1] for s in cd}

def extrema_since(s,since_dt):
    i0=next((i for i,t in enumerate(cd[s]["ts"]) if t>=since_dt.timestamp()),0)
    lo=min(cd[s]["lows"][i0:]); hi=max(cd[s]["highs"][i0:])
    tlo=cd[s]["ts"][i0+cd[s]["lows"][i0:].index(lo)]
    thi=cd[s]["ts"][i0+cd[s]["highs"][i0:].index(hi)]
    return lo,hi,datetime.datetime.fromtimestamp(tlo,datetime.timezone.utc),datetime.datetime.fromtimestamp(thi,datetime.timezone.utc)

lo,hi,tlo,thi=extrema_since("BTC",NOW-datetime.timedelta(days=87))
print("BTC 87d: min low %.0f at %s | max high %.0f at %s"%(lo,tlo,hi,thi))
lo,hi,tlo,thi=extrema_since("ETH",NOW-datetime.timedelta(days=87))
print("ETH 87d: min low %.0f at %s | max high %.0f at %s"%(lo,tlo,hi,thi))

d=json.load(open(RAW+"/discover12.json"))
seen=set(); evs=[]
for slug in d:
    for e in d[slug]:
        if e.get("id") in seen: continue
        seen.add(e.get("id")); evs.append(e)

PATS={
 "btc65":"dip to $65,000 by December 31, 2026",
 "btc80w":"dip to $80,000 October 19-25",
 "btc95":"reach $95,000 by December 31, 2026",
 "eth3000":"reach $3,000 by December 31, 2026",
 "eth2250":"dip to $2,250 by December 31, 2026",
 "eth2000":"dip to $2,000 by December 31, 2026",
 "eth1000first":"hit $1,000 or $3,000 first",
}
best={}
for e in evs:
    for m in (e.get("markets") or []):
        q=(m.get("question") or "")
        for k,p in PATS.items():
            if p in q and (("Bitcoin" if k.startswith("btc") else "Ethereum") in q):
                if k not in best or (m.get("liquidityNum") or 0)>(best[k].get("liquidityNum") or 0):
                    best[k]=m
def jget(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
def fill_cost_usd(token, side, usd_budget):
    b=jget("https://clob.polymarket.com/book?token_id=%s"%token)
    lv=sorted(b.get(side) or [],key=lambda l: float(l["price"]) if side=="asks" else -float(l["price"]))
    spent=0.0; shares=0.0; levels=[]
    for l in lv:
        p=float(l["price"]); sz=float(l["size"])
        take=min(sz*p, usd_budget-spent)
        if take<=0: break
        q=take/p; shares+=q; spent+=take; levels.append((p,round(q)))
        if spent>=usd_budget-1e-9: break
    return (spent/shares if shares else None), shares, spent, levels

toks={k:json.loads(m["clobTokenIds"]) for k,m in best.items()}
print("\n=== creation dates + barrier check since creation ===")
BARR={"btc65":("BTC","dn",65000),"btc95":("BTC","up",95000),"eth3000":("ETH","up",3000),
      "eth2250":("ETH","dn",2250),"eth2000":("ETH","dn",2000),"btc80w":("BTC","dn",80000)}
for k,(sym,dirn,L) in BARR.items():
    m=best[k]
    ca=m.get("createdAt") or ""
    cad=datetime.datetime.strptime(ca[:19],"%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc) if ca else None
    if cad:
        lo,hi,tlo,thi=extrema_since(sym,max(cad,NOW-datetime.timedelta(days=87)))
        touched = (hi>=L) if dirn=="up" else (lo<=L)
        print("%-8s created=%s | since creation: low=%.0f(%s) high=%.0f(%s) | barrier %s %s TOUCHED since creation: %s"%(
            k,ca[:10],lo,tlo.strftime("%m-%d"),hi,thi.strftime("%m-%d"),dirn,L,touched))

print("\n=== executable fills ($330 budget) ===")
fills={}
for name,k,side,isno in [("BTC-65k-Dec31 NO","btc65","asks",True),
                          ("BTC-80k-weekly YES","btc80w","asks",False),
                          ("BTC-95k-Dec31 NO","btc95","asks",True),
                          ("ETH-3000-Dec31 NO","eth3000","asks",True)]:
    tok=toks[k][1] if isno else toks[k][0]
    try:
        avg,sh,sp,lv=fill_cost_usd(tok,side,330)
        fills[name]=dict(avg=round(avg,4),shares=round(sh),spent=round(sp),levels=lv)
        print("%-20s avg=%.4f shares=%.0f spent=$%.0f levels=%s"%(name,avg,sh,sp,lv))
    except Exception as ex:
        print(name,"ERR",ex)

json.dump({"fills":fills,"best":{k:dict(q=best[k].get("question"),created=best[k].get("createdAt"),
    liq=best[k].get("liquidityNum"),bb=best[k].get("bestBid"),ba=best[k].get("bestAsk"),
    pr=best[k].get("outcomePrices"),condId=best[k].get("conditionId")) for k in best}},
    open(RAW+"/finals_fills.json","w"),indent=1)
print("\nwrote",RAW+"/finals_fills.json")
