import json, urllib.request, urllib.parse, time

RAW='/home/ubuntu/paper-sim/round7/raw'
res=json.load(open(RAW+'/discover7.json'))
BASE='https://gamma-api.polymarket.com'
def get(url,tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(1.5)

def show(e,maxm=14,filt=None):
    print('==',e.get('title'),'liq=$%d'%(e.get('liquidity') or 0))
    for m in (e.get('markets') or [])[:maxm]:
        if m.get('closed'): continue
        if filt and not filt(m): continue
        pr=json.loads(m.get('outcomePrices') or '[]')
        print('   %-72s pr=%s ask=%s liq=$%d' % ((m.get('question') or '')[:72], pr, m.get('bestAsk'), m.get('liquidityNum') or 0))

# 1. FOMC October
print('#'*20,'FOMC OCTOBER')
for e in res.get('fed',[]):
    if 'October' in (e.get('title') or ''):
        show(e,20)

# 2. French 2nd round field coherence
print('#'*20,'FRENCH 2ND ROUND ADVANCE')
for e in res.get('politics',[]):
    t=e.get('title') or ''
    if 'advance to the 2' in t or 'on the ballot' in t:
        mkts=[m for m in (e.get('markets') or []) if not m.get('closed')]
        tot=0
        rows=[]
        for m in mkts:
            pr=json.loads(m.get('outcomePrices') or '[]')
            p=float(pr[0]) if pr else 0
            rows.append((p,m.get('question') or m.get('groupItemTitle') or ''))
            tot+=p
        rows.sort(reverse=True)
        for p,q in rows[:12]: print('   %.3f %s'%(p,q[:70]))
        print('   TOTAL YES SUM=%.3f over %d markets'%(tot,len(mkts)))

# 3. Amapa / Brazil runoff
print('#'*20,'AMAPA / BRAZIL RUNOFF')
for e in res.get('politics',[]):
    t=(e.get('title') or '')
    if 'map' in t.lower() and ('Governor' in t or 'runoff' in t.lower()):
        show(e,10)
for e in res.get('politics',[]):
    t=e.get('title') or ''
    if 'Brazil Presidential' in t and ('Second Round' in t or t=='Brazil Presidential Election'):
        show(e,8)

# 4. NBA openers moneylines
print('#'*20,'NBA OPENERS (Oct 20)')
for e in res.get('nba',[]):
    g=None
    for m in e.get('markets') or []:
        if m.get('gameStartTime'): g=m['gameStartTime']; break
    if not g or not g.startswith('2026-10-20'): continue
    if (e.get('liquidity') or 0)<100000: continue
    show(e,6,filt=lambda m:(m.get('question') or '').startswith(('Celtics','Pistons','76ers','Knicks','Thunder','Spurs')) or m.get('sportsMarketType') in ('moneyline','spread'))
    pp=[m for m in (e.get('markets') or []) if 'player' in (m.get('slug') or '') or (m.get('sportsMarketType') or '')=='player_prop']
    print('   (markets total=%d)'%len(e.get('markets') or []))

# 5. POR make playoffs
print('#'*20,'TRAIL BLAZERS PLAYOFFS')
for tag in ['nba','basketball']:
    for e in res.get(tag,[]):
        t=(e.get('title') or '')
        if 'Playoffs' in t or 'make the playoffs' in t.lower() or 'playoffs' in t.lower():
            for m in (e.get('markets') or []):
                if m.get('closed'): continue
                q=(m.get('groupItemTitle') or m.get('question') or '')
                if 'Portland' in q or 'Trail Blazers' in q:
                    pr=json.loads(m.get('outcomePrices') or '[]')
                    print('   %-30s pr=%s ask=%s liq=$%d'%(q[:30],pr,m.get('bestAsk'),m.get('liquidityNum') or 0))

# 6. MLB World Series + Rays-Guardians
print('#'*20,'MLB')
for e in res.get('mlb',[]):
    if 'World Series Champion' in (e.get('title') or ''):
        mk=[m for m in (e.get('markets') or []) if not m.get('closed')]
        rows=[]
        for m in mk:
            pr=json.loads(m.get('outcomePrices') or '[]')
            rows.append((float(pr[0]) if pr else 0,(m.get('groupItemTitle') or m.get('question') or '')[:30],m.get('bestAsk')))
        rows.sort(reverse=True)
        tot=sum(r[0] for r in rows)
        for p,q,a in rows[:8]: print('   %.3f ask=%s %s'%(p,a,q))
        print('   TOTAL=%.3f'%tot)

# 7. UFC 333 method markets
print('#'*20,'UFC 333')
for e in res.get('ufc',[]):
    t=e.get('title') or ''
    if 'UFC 333' in t and ('Volkanovski' in t or 'Dvalishvili' in t):
        show(e,30,filt=lambda m:any(k in (m.get('question') or '').lower() for k in ['ko','submiss','decision','method','distance']))

# 8. NHL Tuesday moneylines
print('#'*20,'NHL Oct 20-21')
for e in res.get('nhl',[]):
    g=None
    for m in e.get('markets') or []:
        if m.get('gameStartTime'): g=m['gameStartTime']; break
    if not g or not (g.startswith('2026-10-20') or g.startswith('2026-10-21')): continue
    if (e.get('liquidity') or 0)<150000: continue
    mls=[m for m in (e.get('markets') or []) if m.get('sportsMarketType')=='moneyline']
    s=' '.join('%s:%s/%s'%((m.get('groupItemTitle') or '?')[:12],m.get('bestBid'),m.get('bestAsk')) for m in mls)
    print('   %-40s %s'%( (e.get('title') or '')[:40], s))

# 9. CLOB depth: COM-MUN Como ML id 5409727, LEV-ATH O/U id 4183827
print('#'*20,'CLOB BOOKS for top candidates')
try:
    for name,mid in [('COMO ML 5409727','5409727'),('LEV-ATH OU25 4183827','4183827')]:
        m=get(BASE+'/markets/%s'%mid)
        c=json.loads(m.get('clobTokenIds') or '[]')
        print('==',name,'|',m.get('question'))
        print('   desc:', (m.get('description') or '')[:400].replace('\n',' '))
        for tid in c[:2]:
            try:
                b=get('https://clob.polymarket.com/book?token_id=%s'%tid)
                bids=b.get('bids') or []; asks=b.get('asks') or []
                print('   token %s... bids(top3)=%s asks(top3)=%s'%(tid[:10],[(x['price'],x['size']) for x in sorted(bids,key=lambda y:-float(y['price']))[:3]],[(x['price'],x['size']) for x in sorted(asks,key=lambda y:float(y['price']))[:3]]))
            except Exception as ex: print('   book ERR',ex)
        time.sleep(0.4)
except Exception as ex:
    print('ERR',ex)

# 10. Bitcoin above $K on Oct 20/21 daily markets (check above-side)
print('#'*20,'BTC/ETH daily ABOVE markets')
for e in res.get('crypto',[])+res.get('eth',[])+res.get('btc',[]):
    t=e.get('title') or ''
    if not t.endswith(('October 20?','October 21?')): continue
    if 'above' not in t: continue
    for m in (e.get('markets') or []):
        if m.get('closed'): continue
        q=m.get('question') or ''
        pr=json.loads(m.get('outcomePrices') or '[]')
        liq=m.get('liquidityNum') or 0
        if liq<10000: continue
        print('   %-55s pr=%s ask=%s liq=$%d'%(q[:55],pr,m.get('bestAsk'),liq))
