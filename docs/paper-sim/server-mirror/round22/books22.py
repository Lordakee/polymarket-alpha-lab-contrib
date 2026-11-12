"""Round-22: CLOB real books for Everton-Newcastle target markets + Americas prices capture."""
import json, time, urllib.request

def get(url, tries=4):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(1.5+i)
    return {'err': repr(last)}

def walk(levels, dollars=250.0):
    lv=sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x:x[0])
    if not lv: return {'best':None,'vwap':None,'filled':False,'depth2c':0.0,'depth5c':0.0}
    best=lv[0][0]
    near2=sum(p*sz for p,sz in lv if p<=best+0.02)
    near5=sum(p*sz for p,sz in lv if p<=best+0.05)
    cash=0.0; sh=0.0
    for p,sz in lv:
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return {'best':round(best,4),'vwap':round((cash/sh) if sh>0 else best,4),
            'filled':cash>=dollars-1e-6,'depth2c':round(near2,0),'depth5c':round(near5,0)}

def walk_bids(bids, dollars=250.0):
    lv=sorted(((float(l['price']), float(l['size'])) for l in bids), key=lambda x:-x[0])
    if not lv: return {'best':None,'vwap':None,'filled':False,'depth2c':0.0,'depth5c':0.0}
    best=lv[0][0]
    near2=sum(p*sz for p,sz in lv if p>=best-0.02)
    near5=sum(p*sz for p,sz in lv if p>=best-0.05)
    cash=0.0; sh=0.0
    for p,sz in lv:
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return {'best':round(best,4),'vwap':round((cash/sh) if sh>0 else best,4),
            'filled':cash>=dollars-1e-6,'depth2c':round(near2,0),'depth5c':round(near5,0)}

d=json.load(open('/home/ubuntu/paper-sim/round22/raw/gamma_sweep22.json'))
# find EVE-NEW More Markets event
ev=None
for e in d['tag_efl-cup']:
    if 'More Markets' in (e['title'] or '') and 'Everton' in e['title']:
        ev=e; break
WANT=['Everton FC vs. Newcastle United FC: O/U 1.5',
      'Everton FC vs. Newcastle United FC: O/U 2.5',
      'Everton FC vs. Newcastle United FC: O/U 3.5',
      'Everton FC vs. Newcastle United FC: O/U 4.5',
      'Everton FC vs. Newcastle United FC: Both Teams to Score',
      'Everton FC vs. Newcastle United FC: Everton FC O/U 1.5',
      'Everton FC vs. Newcastle United FC: Newcastle United FC O/U 1.5']
books={}
for m in ev['markets']:
    q=m['q']
    if q in WANT:
        toks=m['tokens']
        if isinstance(toks,str): toks=json.loads(toks)
        rec={'q':q,'liq_gamma':m['liq'],'bestBid':m['bestBid'],'bestAsk':m['bestAsk']}
        for i,tok in enumerate(toks[:2]):
            b=get('https://clob.polymarket.com/book?token_id='+tok)
            if 'err' in b: rec['tok%d'%i]={'err':b['err']}
            else:
                rec['tok%d'%i]={'ask':walk(b.get('asks') or []),'bid':walk_bids(b.get('bids') or []),
                                'ts':b.get('timestamp'),'hash':b.get('hash')}
        books[q]=rec
        print(q, '| gammaLiq', rec['liq_gamma'], '| gamma', rec['bestBid'], rec['bestAsk'])
        for i in (0,1):
            if 'err' in rec.get('tok%d'%i,{'err':1}): continue
            a=rec['tok%d'%i]['ask']; bb=rec['tok%d'%i]['bid']
            print('   tok%d ask best=%s 2c=$%s | bid best=%s 2c=$%s' % (i, a['best'], a['depth2c'], bb['best'], bb['depth2c']))
        time.sleep(1.1)
json.dump(books, open('/home/ubuntu/paper-sim/round22/raw/evemodel_books22.json','w'), indent=1)
print('saved evemodel_books22.json')
