import json, math, datetime, re

RAW="/home/ubuntu/paper-sim/round12/raw"
NOW=datetime.datetime(2026,10,22,12,0,tzinfo=datetime.timezone.utc)

def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))
def p_touch_up(a,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if a<=0 else 0.0
    return N((mu*T-a)/sigT)+math.exp(2*mu*a/(sig*sig))*N(-(mu*T+a)/sigT)
def p_touch_dn(x,mu,sig,T): return p_touch_up(x,-mu,sig,T)
def p_above(S,K,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if S>=K else 0.0
    return N((math.log(S/K)+mu*T)/sigT)

# ---- vols from coinbase 6h ----
cd={}
for s,f in [("ETH","eth_candles"),("BTC","btc_candles")]:
    rows=sorted(json.load(open(f"{RAW}/{f}.json")),key=lambda r:r[0])
    cd[s]={"closes":[r[4] for r in rows],"t0":rows[-1][0]}
SPOT={s:cd[s]["closes"][-1] for s in cd}
VOL={}
for s in cd:
    cl=cd[s]["closes"]
    def vol(n):
        cs=cl[-n:]; rs=[math.log(cs[i]/cs[i-1]) for i in range(1,len(cs))]
        return math.sqrt(sum(x*x for x in rs)/len(rs))*math.sqrt(4.0)
    VOL[s]={"30d":vol(120),"14d":vol(56),"7d":vol(28)}
    print(s,"spot=%.2f"%SPOT[s],{k:"%.2f%%"%(v*100) for k,v in VOL[s].items()})

SIG="30d"
def probs(sym,kind,K,T):
    S=SPOT[sym]; sig=VOL[sym][SIG]; muB=-sig*sig/2.0
    if kind=="touch_up":
        if K<=S: return (1.0,1.0)
        a=math.log(K/S); return (p_touch_up(a,0,sig,T),p_touch_up(a,muB,sig,T))
    if kind=="touch_dn":
        if K>=S: return (1.0,1.0)
        x=math.log(S/K); return (p_touch_dn(x,0,sig,T),p_touch_dn(x,muB,sig,T))
    if kind=="above":
        return (p_above(S,K,0,sig,T),p_above(S,K,muB,sig,T))
    if kind=="below":
        pa=(p_above(S,K,0,sig,T),p_above(S,K,muB,sig,T))
        return (1-pa[0],1-pa[1])
    return (None,None)

# ---- load events ----
d=json.load(open(RAW+"/discover12.json"))
seen=set(); evs=[]
for slug in d:
    for e in d[slug]:
        if e.get("id") in seen: continue
        seen.add(e.get("id")); evs.append(e)

MONTHS={m:i+1 for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}
def Kval(txt):
    m=re.search(r"\$([\d,]+(?:\.\d+)?)",txt)
    if not m: return None
    return float(m.group(1).replace(",",""))

rows=[]
def add(sym,kind,K,q,m,ev,resolve_dt,window=None):
    prs=m.get("outcomePrices")
    if isinstance(prs,str):
        try: prs=json.loads(prs)
        except Exception: prs=None
    if not prs: return
    try: p_yes=float(prs[0])
    except Exception: return
    rows.append(dict(sym=sym,kind=kind,K=K,q=q.strip(),p_yes=p_yes,
        bb=m.get("bestBid"),ba=m.get("bestAsk"),liq=m.get("liquidityNum") or 0,
        end=(m.get("endDate") or "")[:19],
        toks=m.get("clobTokenIds"),ev=ev.get("title"),
        condId=m.get("conditionId"),
        resolve=resolve_dt.isoformat() if resolve_dt else None,window=window))

for e in evs:
    t=(e.get("title") or "")
    for m in (e.get("markets") or []):
        if m.get("closed"): continue
        q=(m.get("question") or "").strip()
        mm=re.match(r"^Will (Bitcoin|Ethereum) (dip to|reach|hit) \$([\d,]+(?:\.\d+)?)\s*(?:k)?\s*(?:first)?\s*(?:in|on|by)?\s*(.*)$",q)
        mq=re.match(r"^Will the price of (Bitcoin|Ethereum) be (above|less than) \$([\d,]+(?:\.\d+)?) on (\w+ \d+)",q)
        if mm:
            sym="BTC" if mm.group(1)=="Bitcoin" else "ETH"
            verb=mm.group(2); K=Kval("$"+mm.group(3)); rest=(mm.group(4) or "").strip()
            kind="touch_dn" if verb=="dip to" else "touch_up"
            rdt=None
            mMon=re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s*(\d{4}))?",rest)
            yr=int(mMon.group(3)) if (mMon and mMon.group(3)) else 2026
            if mMon:
                rdt=datetime.datetime(yr,MONTHS[mMon.group(1)],int(mMon.group(2)),23,59,tzinfo=datetime.timezone.utc)
            mRng=re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})-(\d{1,2})",rest)
            if mRng:
                rdt=datetime.datetime(2026,MONTHS[mRng.group(1)],int(mRng.group(3)),23,59,tzinfo=datetime.timezone.utc)
            if "today" in rest.lower(): rdt=NOW+datetime.timedelta(hours=12)
            add(sym,kind,K,q,m,e,rdt,window=rest)
        elif mq:
            sym="BTC" if mq.group(1)=="Bitcoin" else "ETH"
            kind="above" if mq.group(2)=="above" else "below"
            K=Kval("$"+mq.group(3))
            parts=mq.group(4).split()
            mth=MONTHS.get(parts[0]); day=int(parts[1])
            rdt=datetime.datetime(2026,mth,day,16,0,tzinfo=datetime.timezone.utc)
            add(sym,kind,K,q,m,e,rdt)

for e in evs:
    if (e.get("title") or "").startswith("Will Ethereum hit $1,000 or $3,000 first"):
        for m in (e.get("markets") or []):
            if m.get("closed"): continue
            prs=m.get("outcomePrices")
            if isinstance(prs,str):
                try: prs=json.loads(prs)
                except Exception: prs=[]
            if prs:
                rows.append(dict(sym="ETH",kind="first",K=None,q=m.get("question"),p_yes=float(prs[0]),
                    bb=m.get("bestBid"),ba=m.get("bestAsk"),liq=m.get("liquidityNum") or 0,
                    end=(m.get("endDate") or "")[:19],toks=m.get("clobTokenIds"),ev=e.get("title"),
                    condId=m.get("conditionId"),resolve=None,window=None))

print("\nclassified markets:",len(rows))
out=[]
for r in rows:
    if not r.get("resolve") or r["K"] is None: continue
    try: rdt=datetime.datetime.fromisoformat(r["resolve"])
    except Exception: continue
    T=(rdt-NOW).total_seconds()/86400.0
    if T<=0 or T>75: continue
    if r["liq"]<10000: continue
    pA,pB=probs(r["sym"],r["kind"],r["K"],T)
    if pA is None: continue
    fair_yes=min(pA,pB) if r["kind"] in ("touch_up","above") else max(pA,pB)
    yes_ask=r["ba"] if r["ba"] is not None else min(1.0,r["p_yes"]+0.02)
    yes_bid=r["bb"] if r["bb"] is not None else max(0.0,r["p_yes"]-0.02)
    no_ask=1.0-yes_bid; no_bid=1.0-yes_ask
    edge_yes=fair_yes-yes_ask
    edge_no=(1.0-fair_yes)-no_ask
    agree_yes=(pA>yes_ask and pB>yes_ask)
    agree_no=((1-pA)>no_ask and (1-pB)>no_ask)
    out.append(dict(r=r,T=T,pA=pA,pB=pB,fair_yes=fair_yes,edge_yes=edge_yes,
                    edge_no=edge_no,agree_yes=agree_yes,agree_no=agree_no,
                    yes_ask=yes_ask,yes_bid=yes_bid))

json.dump([dict(q=x["r"]["q"][:90],sym=x["r"]["sym"],kind=x["r"]["kind"],K=x["r"]["K"],T=round(x["T"],2),
   pA=round(x["pA"],4),pB=round(x["pB"],4),fair_yes=round(x["fair_yes"],4),yes_bid=x["yes_bid"],yes_ask=x["yes_ask"],
   edge_yes=round(x["edge_yes"],4),edge_no=round(x["edge_no"],4),agree_yes=x["agree_yes"],agree_no=x["agree_no"],
   liq=round(x["r"]["liq"]),ev=x["r"]["ev"],condId=x["r"]["condId"],toks=x["r"]["toks"])
   for x in out],open(RAW+"/scan_classified.json","w"),indent=1)
print("kept (T<=75d, liq>=10k):",len(out))
print("\n%-44s %5s %8s %6s %6s %6s %6s %+7s"%("market","T(d)","K","pA","pB","fair","askY","edgeY"))
for x in sorted(out,key=lambda z:-max(z["edge_yes"],z["edge_no"]))[:55]:
    r=x["r"]
    ya=("%.3f"%x["yes_ask"]) if isinstance(x["yes_ask"],float) else str(x["yes_ask"])
    print("%-44s %5.1f %8s %6.3f %6.3f %6.3f %6s %+7.3f %s%s"%(r["q"][:44],x["T"],("%.0f"%r["K"]) if r["K"] else "-",x["pA"],x["pB"],x["fair_yes"],ya,x["edge_yes"],
       "Y!" if x["agree_yes"] and x["edge_yes"]>=0.05 else "","N!" if x["agree_no"] and x["edge_no"]>=0.05 else ""))
print("\n--- top NO-side edges ---")
for x in sorted(out,key=lambda z:-z["edge_no"])[:20]:
    r=x["r"]
    print("%-44s %5.1f fairN=%.3f noAsk=%.3f edge=%+.3f %s"%(r["q"][:44],x["T"],1-x["fair_yes"],1-x["yes_bid"],x["edge_no"],"AGREE" if x["agree_no"] else ""))
