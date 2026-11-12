"""Round-23: CLOB books for gate-shortlisted markets + full gate evaluation.
Early-entry gates: var<=6c, worst>=+4c, exec>=+5c, liq>=$5k. match_winner SUSPENDED,
spreads flag-only. Exec = $250 ask-side VWAP walk (r20-r22 convention)."""
import json, time, urllib.request

M = json.load(open('/home/ubuntu/paper-sim/round23/raw/seriea_model23.json'))

def get(url, tries=4):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(1.5+i)
    return {'err': repr(last)}

def walk_ask(levels, dollars=250.0):
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

# Pass 1: mid edges, decide shortlist
shortlist=[]  # (match_rec, q, rec, side_idx, side_name, mid0, side_mid, mid_edge)
for mr in M['matches']:
    for q, rec in mr['markets'].items():
        kind = rec['kind']
        if kind.startswith('spread'):
            is_spread=True; kside=0
        else:
            is_spread=False
        prices=rec['prices']
        if isinstance(prices,str):
            try: prices=json.loads(prices)
            except Exception: prices=None
        p0=float(prices[0]) if prices else None
        bb, ba = rec['bestBid'], rec['bestAsk']
        if bb is not None and ba is not None:
            mid0=(float(bb)+float(ba))/2.0
        elif p0 is not None:
            mid0=p0
        else:
            continue
        # model prob corresponds to outcome 0 (Over/Yes/cover)
        med0=rec['p0_med']
        e0=med0-mid0            # Over/Yes side
        e1=(1-med0)-(1-mid0)    # == -e0 for Under/No side... but p for Under side is 1-p0
        # side 1 model prob:
        med1=1-med0; mid1=1-mid0; edge1=med1-mid1  # = -e0
        liq=rec['liq'] or 0
        for sidx,sname,sedge,smed in ((0,'side0',e0,med0),(1,'side1',edge1,med1)):
            if sedge is None: continue
            if liq>=5000 and sedge>=0.025:
                shortlist.append({'match':mr['label'],'match_rec':mr,'q':q,'rec':rec,'side_idx':sidx,
                                  'side_name':sname,'mid':round((mid0 if sidx==0 else 1-mid0),4),
                                  'p_med':round(smed,4),'mid_edge':round(sedge,4),'liq':liq})
print('shortlist (liq>=5k, mid_edge>=2.5c):', len(shortlist))
for s in sorted(shortlist,key=lambda x:-x['mid_edge']):
    kind=s['rec']['kind']
    side='Over/Yes' if s['side_idx']==0 else 'Under/No'
    print('  %-22s %-58s %-9s mid %.3f p %.3f edge %+.3f liq %8.0f' % (
        s['match'], s['q'][:58], side, s['mid'], s['p_med'], s['mid_edge'], s['liq']))

# Pass 2: fetch books (dedupe by market+side token)
books={}
for s in shortlist:
    key=(s['q'], s['side_idx'])
    if key in books: continue
    toks=s['rec']['tokens']
    if isinstance(toks,str): toks=json.loads(toks)
    if not toks: continue
    tok=toks[s['side_idx'] if s['side_idx']<len(toks) else 0]
    b=get('https://clob.polymarket.com/book?token_id='+tok)
    books[key]={'token':tok,'book':b}
    time.sleep(1.05)
json.dump({('%s||%d'%k):{'token':v['token'],'ts':v['book'].get('timestamp'),
    'asks':v['book'].get('asks'),'bids':v['book'].get('bids')} for k,v in books.items()},
    open('/home/ubuntu/paper-sim/round23/raw/clob_books23.json','w'), indent=1)
print('books fetched:', len(books))
