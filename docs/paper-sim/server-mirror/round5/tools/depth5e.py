import json, urllib.request, time

def get(u,tries=3):
    for i in range(tries):
        try:
            r=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(r,timeout=15) as f: return json.load(f)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.2)

def walk(b,dollars=400.0):
    asks=sorted(b.get('asks',[]),key=lambda l: float(l['price']))
    if not asks: return None,None,0
    best=float(asks[0]['price'])
    cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size'])
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return best, round(cash/sh,4) if sh>0 else best, round(sh)

# candidates: (label, mid, outcome-label, note)
CAND=[('PFC-REN O/U2.5 Over','5314283','Over'),
      ('TOT-COV O/U2.5 Under','5364567','Under'),
      ('TOT-COV 1X2 A (Coventry ML)','5362519','Yes'),
      ('TOT-COV spread: Coventry +1.5','5364544','Coventry City FC'),
      ('LYO-OGC spread: Lyon -1.5','5314029','Olympique Lyonnais')]
for label,mid,lab in CAND:
    m=get('https://gamma-api.polymarket.com/markets/'+mid)
    toks=m.get('clobTokenIds')
    if isinstance(toks,str): toks=json.loads(toks)
    o=m.get('outcomes')
    if isinstance(o,str): o=json.loads(o)
    idx=o.index(lab) if lab in o else 0
    b=get('https://clob.polymarket.com/book?token_id='+toks[idx])
    best,vw,sh=walk(b)
    bids=sorted(b.get('bids',[]),key=lambda l: -float(l['price']))
    bb=float(bids[0]['price']) if bids else None
    print('%-32s ask %.3f vwap@400 %.4f shares@400 %5d bestbid %s | %s' % (label,best,vw,sh,('%.3f'%bb) if bb else 'none',(m.get('question') or '')[:40]))
    time.sleep(0.2)
