import json, urllib.request, urllib.parse, time, datetime

BASE='https://gamma-api.polymarket.com'
def get(url,tries=3):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(2)
    print('  GETFAIL',url.split('?')[0],repr(last),flush=True)
    return None

NOW=datetime.datetime(2026,10,21,11,0,tzinfo=datetime.timezone.utc)
seen={}
def harvest(tag):
    found=0
    for off in range(0,800,100):
        p={'tag_slug':tag,'closed':'false','order':'liquidity','ascending':'false','offset':off,'limit':100}
        b=get(BASE+'/events?'+urllib.parse.urlencode(p))
        if b is None: break
        for ev in b:
            sl=ev.get('slug') or ''
            if not sl or sl in seen: continue
            end=ev.get('endDate') or ''
            try: ed=datetime.datetime.strptime(end[:19],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=datetime.timezone.utc)
            except Exception: ed=None
            liq=ev.get('liquidityNum') or 0
            # keep anything not clearly over; soccer events end within days
            seen[sl]={'title':ev.get('title'),'slug':sl,'endDate':end,'liq':liq,'vol24':ev.get('volume24hr'),
                      'tags':sorted(set([t.get('slug') for t in (ev.get('tags') or []) if t.get('slug')])),
                      'ed':ed.isoformat() if ed else None,'markets':[]}
            found+=1
        if len(b)<100: break
        time.sleep(0.25)
    print('tag %-28s events=%d (new)'%(tag,found),flush=True)

TAGS=['europa-league','europa-conference-league','conference-league','uel','uecl','uefa-europa-league',
      'eredivisie','primeira-liga','liga-portugal','portuguese-liga','super-lig','super-lig-turkey','turkish-super-lig',
      'belgian-pro-league','jupiler-pro-league','scottish-premiership','spfl','championship','efl-championship',
      'fa-cup','carabao-cup','efl-cup','copa-del-rey','dfb-pokal','coppa-italia','copa-italia',
      'wsf','womens-super-league','nwsl','womens-soccer','women-soccer','ucl-w','champions-league-women',
      'mls','liga-mx','brasileirao','a-league','j-league','k-league','primera-division','laliga-santander',
      'world-cup','friendlies','international-friendlies','nations-league','world-cup-qualifying',
      'copa-libertadores','copa-america','afcon','asian-cup','saudi-pro-league','serie-a-brasil','liga-profesional-argentina']
for t in TAGS:
    harvest(t); time.sleep(0.4)

# broad soccer sweep ordered by liquidity (catch-all)
harvest('soccer')
time.sleep(0.5)

# enrich: fetch markets per event where liq>=5000 or ed within 7d
out=[]
kept=0
for sl,e in seen.items():
    ed=e.get('ed')
    try: edt=datetime.datetime.fromisoformat(ed) if ed else None
    except Exception: edt=None
    recent = edt is not None and (NOW-datetime.timedelta(hours=10)) <= edt <= (NOW+datetime.timedelta(days=8))
    if not recent and (e['liq'] or 0)<3000: continue
    mk=[]
    d=get(BASE+'/events?slug='+urllib.parse.quote(sl))
    time.sleep(0.15)
    if d:
        ev=d[0] if isinstance(d,list) and d else {}
        for m in (ev.get('markets') or []):
            if m.get('closed'): continue
            toks=m.get('clobTokenIds')
            if isinstance(toks,str):
                try: toks=json.loads(toks)
                except: toks=None
            outs=m.get('outcomes')
            if isinstance(outs,str):
                try: outs=json.loads(outs)
                except: outs=None
            mk.append({'id':m.get('id'),'q':m.get('question') or m.get('groupItemTitle'),'slug':m.get('slug'),
                       'outcomes':outs,'tokens':toks,'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),
                       'prices':m.get('outcomePrices')})
        e['title']=ev.get('title') or e['title']
        e['tags']=sorted(set([t.get('slug') for t in (ev.get('tags') or []) if t.get('slug')])) or e['tags']
    e['markets']=mk
    out.append(e); kept+=1
    if kept%20==0: print('enriched',kept,flush=True)

json.dump(out,open('/home/ubuntu/paper-sim/round10/raw/discover10.json','w'),indent=1)
print('TOTAL events kept:',len(out))
