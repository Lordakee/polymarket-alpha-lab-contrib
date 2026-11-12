import json, urllib.request, time

RAW='/home/ubuntu/paper-sim/round6/raw'
META=json.load(open(RAW+'/meta6.json'))
M6=json.load(open(RAW+'/model6.json'))

def get(url,tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=15) as r: return json.load(r)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.5)

def ask(b,dollars=300.0):
    asks=sorted(b.get('asks',[]),key=lambda l: float(l['price']))
    if not asks: return None,None
    best=float(asks[0]['price'])
    cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size'])
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return best, round(cash/sh,4) if sh>0 else best

RANGES={
 'MON-CAG Oct19 SEA': {'hm15':M6['MON-CAG Oct19 SEA']['ranges']['hm15'],'am15':M6['MON-CAG Oct19 SEA']['ranges']['am15'],
                       'hm25':M6['MON-CAG Oct19 SEA']['ranges']['hm25'],'am25':M6['MON-CAG Oct19 SEA']['ranges']['am25']},
 'PAR-TOR Oct19 SEA': {'hm15':M6['PAR-TOR Oct19 SEA']['ranges']['hm15'],'am15':M6['PAR-TOR Oct19 SEA']['ranges']['am15'],
                       'hm25':M6['PAR-TOR Oct19 SEA']['ranges']['hm25'],'am25':M6['PAR-TOR Oct19 SEA']['ranges']['am25']},
 'GET-RAY Oct19 LAL': {'hm15':M6['GET-RAY Oct19 LAL']['ranges']['hm15'],'am15':M6['GET-RAY Oct19 LAL']['ranges']['am15'],
                       'hm25':M6['GET-RAY Oct19 LAL']['ranges']['hm25'],'am25':M6['GET-RAY Oct19 LAL']['ranges']['am25']},
}
HOMEKEY={'MON-CAG Oct19 SEA':('AC Monza','hm15','hm25'),'PAR-TOR Oct19 SEA':('Parma','hm15','hm25'),'GET-RAY Oct19 LAL':('Getafe','hm15','hm25')}
AWAYKEY={'MON-CAG Oct19 SEA':('Cagliari','am15','am25'),'PAR-TOR Oct19 SEA':('Torino','am15','am25'),'GET-RAY Oct19 LAL':('Rayo','am15','am25')}

flags=[]
for label in RANGES:
    for mid,d in META.items():
        q=d.get('q') or ''
        if not q.startswith('Spread:'): continue
        if d.get('liq') is None or d.get('liq')<30000: continue
        # only spreads for our 3 fixtures: match by question team token
        hk=HOMEKEY[label]; ak=AWAYKEY[label]
        is25=q.endswith('(-2.5)')
        if hk[0] in q: side,rk=('H',hk[2] if is25 else hk[1])
        elif ak[0] in q: side,rk=('A',ak[2] if is25 else ak[1])
        else: continue
        outs=d['outcomes']; toks=d['tokens']
        for lab,tok in zip(outs,toks):
            b=get('https://clob.polymarket.com/book?token_id='+tok); time.sleep(0.12)
            best,vw=ask(b)
            if best is None: continue
            # cover prob range for the team named in outcome label
            if hk[0] in lab: pr=RANGES[label][rk]  # home cover range
            else: pr=[1-RANGES[label][rk][1],1-RANGES[label][rk][0]]  # other side nocover
            edge=pr[0]-best
            mark='FLAG' if edge>=0.05 else ''
            if edge>=0.05: flags.append((label,q,round(edge,3),best,mid))
            print('%-17s | %-42s | %-28s ask %.3f vw %s | model [%.3f-%.3f] edge %+.3f %s'%(label,q[:42],lab,best,vw,pr[0],pr[1],edge,mark),flush=True)
print()
print('SPREAD FLAGS:')
for f in flags: print(' ',f)
