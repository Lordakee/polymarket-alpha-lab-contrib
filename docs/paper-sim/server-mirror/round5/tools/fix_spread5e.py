import json, urllib.request, time

def get(u,tries=3):
    for i in range(tries):
        try:
            r=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(r,timeout=15) as f: return json.load(f)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.2)

def ask(b,dollars=400.0):
    asks=sorted(b.get('asks',[]),key=lambda l: float(l['price']))
    if not asks: return None
    best=float(asks[0]['price'])
    cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size'])
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return best

M=json.load(open('/home/ubuntu/paper-sim/round5/raw/model_round5e.json'))
out=M['out']
# spread market ids per fixture: (label, sph, spa, hm2 rng, am2 rng)
SP=[('MOE-HOF Oct18 Bund','5314041','5314046'),('PFC-REN Oct18 L1','5314271','5314272'),
    ('LYO-OGC Oct18 L1','5314029','5314030'),('HAC-AJA Oct18 L1','5314511','5314512'),
    ('TOT-COV Oct19 EPL','5364544','5364546'),('PSG-FCB Oct20 UCL','5409997','5409998'),
    ('BAY-ARS Oct21 UCL','5437363','5437364')]
for label,sph,spa in SP:
    for side,mid in [('H',sph),('A',spa)]:
        m=get('https://gamma-api.polymarket.com/markets/'+mid)
        toks=m.get('clobTokenIds')
        if isinstance(toks,str): toks=json.loads(toks)
        o=m.get('outcomes')
        if isinstance(o,str): o=json.loads(o)
        d=out.get(label,{}).get('SPH' if side=='H' else 'SPA')
        if d is None: continue
        mn,mx=d['rng']
        # token0 = named team covers -1.5 ; token1 = other side (+1.5)
        b0=get('https://clob.polymarket.com/book?token_id='+toks[0])
        b1=get('https://clob.polymarket.com/book?token_id='+toks[1])
        a_cover=ask(b0); a_nocov=ask(b1)
        e_cov=mn-a_cover if a_cover else None
        e_noc=(1-mx)-a_nocov if a_nocov else None
        d['cover_ask']=a_cover; d['nocov_ask']=a_nocov
        d['e_cover']=round(e_cov,3) if e_cov is not None else None
        d['e_nocov']=round(e_noc,3) if e_noc is not None else None
        fl=[]
        if e_cov is not None and e_cov>=0.05: fl.append('COVER +%.3f'%e_cov)
        if e_noc is not None and e_noc>=0.05: fl.append('NOCOV +%.3f'%e_noc)
        print('%-18s %s -1.5 cover [%.3f-%.3f] ask %.3f edge %+.3f | other(+1.5) [%.3f-%.3f] ask %.3f edge %+.3f %s'%(
            label,side,mn,mx,a_cover or -1,e_cov or 0,1-mx,1-mn,a_nocov or -1,e_noc or 0,'FLAG '+','.join(fl) if fl else 'NO'))
        time.sleep(0.2)
    # clear stale flags for spreads
M['flags']=[f for f in M['flags'] if '-1.5' not in f[1]]
for label,sph,spa in SP:
    for key,side in [('SPH','H'),('SPA','A')]:
        d=out.get(label,{}).get(key)
        if not d: continue
        if d.get('e_cover') is not None and d['e_cover']>=0.05: M['flags'].append((label,side+' -1.5 COVER',d['e_cover']))
        if d.get('e_nocov') is not None and d['e_nocov']>=0.05: M['flags'].append((label,side+' +1.5 (nocov)',d['e_nocov']))
json.dump(M,open('/home/ubuntu/paper-sim/round5/raw/model_round5e.json','w'),indent=1)
print()
print('FLAGS:',M['flags'] or 'NONE')
