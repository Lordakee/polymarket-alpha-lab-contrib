import json, urllib.request, time

RAW='/home/ubuntu/paper-sim/round5/raw'
DISC=json.load(open(RAW+'/discover5d3.json'))
RES=json.load(open(RAW+'/model_round5d.json'))
report=RES['report']; flags=[tuple(f) for f in RES['flags']]
# remove the stale NFO-ARS X1_away flag (was the mislabeled Forest market)
flags=[f for f in flags if not (f[0]=='NFO-ARS' and f[1]=='X1_away')]

def get(url,tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r: return json.load(r)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.0)
def ask_side(b,dollars=400.0):
    asks=sorted(b.get('asks',[]),key=lambda l: float(l['price']))
    if not asks: return None,None,False
    best=float(asks[0]['price']); cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size']); take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return best, round(cash/sh,4) if sh>0 else best, cash>=dollars-1e-6

FIXHOME={'BOU-SUN':'Bournemouth','MIL-ATA':'AC Milan','LEE-MUN':'Leeds','NFO-ARS':'Nottingham Forest',
         'BHA-CRY':'Brighton','JUV-LAZ':'Juventus','ANG-OM':'Angers'}

for tag,h in FIXHOME.items():
    spreads={}
    for ev in DISC[tag]:
        if ' - More Markets' in (ev['title'] or ''):
            for m in ev['markets']:
                q=m['q'] or ''
                if q.startswith('Spread:') and ('(-1.5)' in q or '(-2.5)' in q):
                    spreads[m['id']]=m
    for mid,m in spreads.items():
        outs=m['outcomes']; toks=m['tokens']
        q=m['q'] or ''
        # 'Spread: <Team> (-1.5)' ; outs[0]=covering side, outs[1]=other side
        import re
        mm=re.match(r'Spread: (.+) \((-[\d.]+)\)$',q)
        team=mm.group(1); line=float(mm.group(2))
        is_home=team.lower().startswith(h.lower()[:8])
        key='SPREAD_%s_%s'%('H' if is_home else 'A',str(line).replace('-','m'))
        ab,av,aok=ask_side(get('https://clob.polymarket.com/book?token_id='+toks[0]))
        time.sleep(0.15)
        bb,bv,bok=ask_side(get('https://clob.polymarket.com/book?token_id='+toks[1]))
        time.sleep(0.15)
        M=report[tag]['markets'].get(key)
        if M is None: continue
        mn,md,mx=M['model']
        e_cov = mn-ab if ab is not None else None
        e_fail = (1-mx)-bb if bb is not None else None
        fl='COVER' if (e_cov is not None and e_cov>=0.05) else ('FAIL' if (e_fail is not None and e_fail>=0.05) else '')
        M.update({'cover_ask':ab,'cover_vwap':av,'fail_ask':bb,'fail_vwap':bv,
                  'edge_cover':round(e_cov,4) if e_cov is not None else None,
                  'edge_fail':round(e_fail,4) if e_fail is not None else None,'flag':fl})
        if fl: flags.append((tag,key,fl))
        print('%-8s %-42s cov_ask=%-6s fail_ask=%-6s model[%s-%s] eCov=%-7s eFail=%-7s %s'%(
            tag,q[:42],ab,bb,mn,mx,M['edge_cover'],M['edge_fail'],'*** '+fl if fl else ''))

json.dump({'report':report,'flags':[list(f) for f in flags]},open(RAW+'/model_round5d.json','w'),indent=1)
print()
print('FINAL FLAGS:',flags if flags else 'NONE')
