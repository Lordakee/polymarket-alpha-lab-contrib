import json, math, datetime, re, urllib.request

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
    cd[s]={"closes":[r[4] for r in rows]}
SPOT={s:cd[s]["closes"][-1] for s in cd}
VOL={}
for s in cd:
    cl=cd[s]["closes"]
    def vol(n):
        cs=cl[-n:]; rs=[math.log(cs[i]/cs[i-1]) for i in range(1,len(cs))]
        return math.sqrt(sum(x*x for x in rs)/len(rs))*math.sqrt(4.0)
    VOL[s]={"30d":vol(120),"60d":vol(240),"87d":vol(349)}
print("SPOT",SPOT); print("VOL", {s:{k:round(v,4) for k,v in VOL[s].items()} for s in VOL})

def jget(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)

d=json.load(open(RAW+"/discover12.json"))
seen=set(); evs=[]
for slug in d:
    for e in d[slug]:
        if e.get("id") in seen: continue
        seen.add(e.get("id")); evs.append(e)

WANT=[
 ("BTC","dip to $80,000 October 19-25"),
 ("ETH","dip to $2,300 October 19-25"),
 ("BTC","reach $95,000 by December 31, 2026"),
 ("BTC","dip to $65,000 by December 31, 2026"),
 ("BTC","reach $90,000 by December 31, 2026"),
 ("ETH","reach $3,000 by December 31, 2026"),
 ("ETH","dip to $2,250 by December 31, 2026"),
 ("ETH","dip to $2,000 by December 31, 2026"),
 ("BTC","dip to $81,000 on October 22"),
 ("BTC","dip to $80,000 on October 22"),
 ("ETH","hit $1,000 or $3,000 first"),
]
found={}
for e in evs:
    for m in (e.get("markets") or []):
        if m.get("closed"): continue
        q=(m.get("question") or "").strip()
        for sym,pat in WANT:
            full=(sym+" "+pat)
            if pat.lower() in q.lower() and (("Bitcoin" if sym=="BTC" else "Ethereum") in q or "$1,000" in q):
                key=full
                if key not in found or (m.get("liquidityNum") or 0)>(found[key].get("liquidityNum") or 0):
                    m2=dict(m); m2["_ev"]=e.get("title")
                    found[key]=m2
print("found keys:",sorted(found.keys()))
out={}
for key,m in found.items():
    try: toks=json.loads(m.get("clobTokenIds") or "[]")
    except Exception: toks=[]
    yes_tok=toks[0] if toks else None
    book=None
    if yes_tok:
        try: book=jget("https://clob.polymarket.com/book?token_id=%s"%yes_tok)
        except Exception as ex: print("book err",key,ex)
    # depth within 3c of best
    def side_levels(which):
        lv=book.get(which) or [] if book else []
        if not lv: return (None,0.0)
        p0=float(lv[0]["price"])
        tot=sum(float(l["size"]) for l in lv if abs(float(l["price"])-p0)<=0.03)
        return (p0,tot)
    ba,qa=side_levels("asks"); bb,qb=side_levels("bids")
    prs=m.get("outcomePrices")
    if isinstance(prs,str):
        try: prs=json.loads(prs)
        except Exception: prs=None
    out[key]=dict(q=m.get("question"),ev=m["_ev"],
        p_yes=float(prs[0]) if prs else None,
        gamma_bb=m.get("bestBid"),gamma_ba=m.get("bestAsk"),
        liq=m.get("liquidityNum"),vol24=m.get("volume24hr"),
        end=(m.get("endDate") or "")[:19],yes_tok=yes_tok,
        book_ask=ba,book_ask_sz_3c=round(qa,1) if qa else 0,
        book_bid=bb,book_bid_sz_3c=round(qb,1) if qb else 0,
        desc=(m.get("description") or "")[:600])
    b=out[key]
    print("\n== %s\n  Q: %s | ev=%s"%(key,b["q"],b["ev"]))
    print("  p_yes=%s bb=%s ba=%s liq=%s end=%s"%(b["p_yes"],b["gamma_bb"],b["gamma_ba"],round(b["liq"] or 0),b["end"]))
    print("  BOOK ask=%s (x%s within 3c) bid=%s (x%s within 3c)"%(b["book_ask"],b["book_ask_sz_3c"],b["book_bid"],b["book_bid_sz_3c"]))
    if b["desc"]: print("  DESC:",b["desc"][:350].replace("\n"," "))

json.dump(out,open(RAW+"/books_finalists.json","w"),indent=1)

# corrected model on finalists
def model(sym,kind,K,rdt,vol_key="30d"):
    T=(rdt-NOW).total_seconds()/86400.0
    sig=VOL[sym][vol_key]; mu=-sig*sig/2; S=SPOT[sym]
    if kind=="touch_dn":
        x=math.log(S/K); p=(p_touch_dn(x,0,sig,T),p_touch_dn(x,mu,sig,T))
    else:
        a=math.log(K/S); p=(p_touch_up(a,0,sig,T),p_touch_up(a,mu,sig,T))
    return T,p
print("\n\n==== corrected conservative model on finalists (30d / 60d / 87d vol) ====")
targets=[
 ("BTC dip-to-80k Oct19-25","BTC","touch_dn",80000,datetime.datetime(2026,10,25,16,0,tzinfo=datetime.timezone.utc)),
 ("ETH dip-to-2300 Oct19-25","ETH","touch_dn",2300,datetime.datetime(2026,10,25,16,0,tzinfo=datetime.timezone.utc)),
 ("BTC reach-95k Dec31","BTC","touch_up",95000,datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)),
 ("BTC dip-65k Dec31","BTC","touch_dn",65000,datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)),
 ("BTC reach-90k Dec31","BTC","touch_up",90000,datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)),
 ("ETH reach-3000 Dec31","ETH","touch_up",3000,datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)),
 ("ETH dip-2250 Dec31 (MTM)","ETH","touch_dn",2250,datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)),
 ("ETH dip-2000 Dec31 (MTM)","ETH","touch_dn",2000,datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)),
]
for name,sym,kind,K,rdt in targets:
    T,p30=model(sym,kind,K,rdt,"30d"); _,p60=model(sym,kind,K,rdt,"60d"); _,p87=model(sym,kind,K,rdt,"87d")
    fairY_30=min(p30); fairN_30=1-max(p30)
    print("%-26s T=%5.2f  pA/pB 30d=%.3f/%.3f 60d=%.3f/%.3f 87d=%.3f/%.3f | cons fairYES=%.3f fairNO=%.3f (30d)"%(
        name,T,p30[0],p30[1],p60[0],p60[1],p87[0],p87[1],fairY_30,fairN_30))
