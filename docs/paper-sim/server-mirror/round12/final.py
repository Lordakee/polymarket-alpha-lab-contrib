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
    cd[s]={"closes":[r[4] for r in rows],"lows":[r[1] for r in rows]}
SPOT={s:cd[s]["closes"][-1] for s in cd}
print("BTC 87d min low:",min(cd["BTC"]["lows"]),"ETH 87d min low:",min(cd["ETH"]["lows"]))
VOL={}
for s in cd:
    cl=cd[s]["closes"]
    def vol(n):
        cs=cl[-n:]; rs=[math.log(cs[i]/cs[i-1]) for i in range(1,len(cs))]
        return math.sqrt(sum(x*x for x in rs)/len(rs))*math.sqrt(4.0)
    VOL[s]={"30d":vol(120),"87d":vol(349)}

books=json.load(open(RAW+"/books_finalists.json"))
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
    avg=spent/shares if shares else None
    return avg, shares, spent, levels

print("\n=== executable fill for $330 budget ===")
jobs=[
 ("BTC dip-65k Dec31 YES token -> buying NO(=sell YES) skip; instead NO side via NO token? use YES asks for NO-buy mirror only if direct NO token unknown; we use 1-bid",
  None),
]
# For a NO buy we need the NO token (toks[1]). books_finalists stored only yes_tok; refetch full token list from discover
d=json.load(open(RAW+"/discover12.json"))
seen=set(); evs=[]
for slug in d:
    for e in d[slug]:
        if e.get("id") in seen: continue
        seen.add(e.get("id")); evs.append(e)
toks={}
for e in evs:
    for m in (e.get("markets") or []):
        q=(m.get("question") or "")
        if "dip to $65,000 by December 31, 2026" in q and "Bitcoin" in q: toks["btc65"]=m.get("clobTokenIds")
        if "dip to $80,000 October 19-25" in q and "Bitcoin" in q: toks["btc80w"]=m.get("clobTokenIds")
        if "reach $95,000 by December 31, 2026" in q and "Bitcoin" in q: toks["btc95"]=m.get("clobTokenIds")
for k in toks: toks[k]=json.loads(toks[k])

# NO buy on BTC dip-65k = buy NO token (toks[1]) at its ask
for name,pair,side in [("BTC-65k-Dec31 NO buy",toks["btc65"],"asks"),
                        ("BTC-80k-weekly YES buy",toks["btc80w"],"asks"),
                        ("BTC-95k-Dec31 NO buy",toks["btc95"],"asks")]:
    tok=pair[1] if "NO" in name else pair[0]
    avg,sh,sp,lv=fill_cost_usd(tok,side,330)
    print("%-24s avg=%.4f shares=%.0f spent=$%.0f levels=%s"%(name,avg,sh,sp,lv))

# blend-rule fair for the ETH first market
sig=VOL["ETH"]["30d"]; sig7=VOL["ETH"]["87d"]; T=70.5
for lbl,s in [("30d",sig),("87d",sig7)]:
    mu=-s*s/2
    p3000=(p_touch_up(math.log(3000/SPOT["ETH"]),0,s,T),p_touch_up(math.log(3000/SPOT["ETH"]),mu,s,T))
    p1000=(p_touch_dn(math.log(SPOT["ETH"]/1000),0,s,T),p_touch_dn(math.log(SPOT["ETH"]/1000),mu,s,T))
    for i,cn in enumerate(["A(zero-log-drift)","B(median-flat)"]):
        up=p3000[i]; dn=p1000[i]; neither=1.0-up-dn
        f1000=dn+0.5*neither; f3000=up+0.5*neither
        print("ETH-first %s %s: P(3000)=%.3f P(1000)=%.4f P(neither)=%.3f -> fair($1000)=%.3f fair($3000)=%.3f"%(lbl,cn,up,dn,neither,f1000,f3000))
print("market: $1000 bid/ask 0.26/0.35 ; $3000 executable ~0.65-0.74")

# MTM
for key,shares,cost in [("ETH dip to $2,250 by December 31, 2026",750/0.515+500/0.455,1250.0),
                          ("ETH dip to $2,000 by December 31, 2026",320/0.265,320.0)]:
    b=books[key]
    print("\nMTM %s: bid=%s ask=%s mid=%.3f | shares=%.1f value@bid=$%.0f PnL=$%+.0f (%+.1f%%)"%(
        key,b["gamma_bb"],b["gamma_ba"],(b["gamma_bb"]+b["gamma_ba"])/2,shares,shares*b["gamma_bb"],
        shares*b["gamma_bb"]-cost,100*(shares*b["gamma_bb"]-cost)/cost))
