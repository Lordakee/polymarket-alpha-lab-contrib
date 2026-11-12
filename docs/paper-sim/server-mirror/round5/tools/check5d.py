import json, urllib.request, time

RAW='/home/ubuntu/paper-sim/round5/raw'
DISC=json.load(open(RAW+'/discover5d3.json'))
RES=json.load(open(RAW+'/model_round5d.json'))

# 1) inspect one spread market outcome names + raw book
spread=None
for ev in DISC['LEE-MUN']:
    if ' - More Markets' in (ev['title'] or ''):
        for m in ev['markets']:
            if (m['q'] or '').startswith('Spread: Leeds United FC (-1.5)'):
                spread=m
print('spread outcomes:', spread['outcomes'], 'liq:', spread.get('liq'), 'vol24:', spread.get('vol24'))
tok=spread['tokens'][spread['outcomes'].index('Yes')] if 'Yes' in spread['outcomes'] else spread['tokens'][0]
req=urllib.request.Request('https://clob.polymarket.com/book?token_id='+tok,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
with urllib.request.urlopen(req,timeout=15) as r: b=json.load(r)
print('Yes book: bids=%d asks=%d'%(len(b.get('bids',[])),len(b.get('asks',[]))))
print('  top bids:',sorted(b.get('bids',[]),key=lambda l:-float(l['price']))[:2])
print('  top asks:',sorted(b.get('asks',[]),key=lambda l:float(l['price']))[:2])
# No side
tok2=spread['tokens'][spread['outcomes'].index('No')] if 'No' in spread['outcomes'] else spread['tokens'][1]
req=urllib.request.Request('https://clob.polymarket.com/book?token_id='+tok2,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
with urllib.request.urlopen(req,timeout=15) as r: b2=json.load(r)
print('No  book: bids=%d asks=%d'%(len(b2.get('bids',[])),len(b2.get('asks',[]))))
time.sleep(0.2)

# 2) liquidity/depth summary for key flagged markets + spread liq across all fixtures
print()
print('--- spread market liquidity across fixtures (gamma liq / vol24) ---')
for tag in DISC:
    for ev in DISC[tag]:
        if ' - More Markets' in (ev['title'] or ''):
            for m in ev['markets']:
                q=m['q'] or ''
                if q.startswith('Spread:') and '(-1.5)' in q:
                    print('%-8s %-55s liq=%s vol24=%s'%(tag,q[:55],m.get('liq'),m.get('vol24')))
            break

# 3) decision-card details from saved results
print()
for tag,mk in [('BHA-CRY','BTTS'),('BOU-SUN','1H_OU25'),('NFO-ARS','X1_home'),('BOU-SUN','OU25_POS')]:
    M=RES['report'][tag]['markets'][mk]
    print(tag,mk,json.dumps(M))

# 4) 1H share sensitivity for BOU-SUN and BHA-CRY BTTS check via simple poisson closed form
import math
def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def pge3(lam): return 1-pois(lam,0)-pois(lam,1)-pois(lam,2)
for share in [0.42,0.45,0.48]:
    lh,la=1.95,1.17
    # total 1H goals approx Poisson(lh*share+la*share)
    print('BOU-SUN 1H O2.5 share=%.2f P(>=3)=%.4f'%(share,pge3((lh+la)*share)))
