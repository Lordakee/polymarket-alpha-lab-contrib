import json, datetime

res=json.load(open('/home/ubuntu/paper-sim/round9/raw/discover9.json'))
NOW=datetime.datetime(2026,10,21,3,50,tzinfo=datetime.timezone.utc)

out=[]
for e in res.get('soccer',[]):
    t=(e.get('title') or '')
    end=e.get('endDate') or ''
    try:
        ed=datetime.datetime.strptime(end[:19],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=datetime.timezone.utc)
    except Exception: continue
    if ed < NOW - datetime.timedelta(hours=8): continue
    if ed > NOW + datetime.timedelta(days=6): continue
    for m in e.get('markets',[]):
        if m.get('closed'): continue
        q=(m.get('question') or m.get('groupItemTitle') or '')
        pr=json.loads(m.get('outcomePrices') or '[]')
        vol=m.get('volumeNum') or 0
        ml=m.get('liquidityNum') or 0
        if ml<2000: continue
        out.append(dict(ev=t,end=end[:16],q=q,pr=pr,vol=int(vol),liq=int(ml),slug=m.get('slug'),
                        desc=(m.get('description') or '')[:600]))

json.dump(out,open('/home/ubuntu/paper-sim/round9/raw/soccer_markets9.json','w'),indent=1)
print('total soccer markets:',len(out))
for r in out:
    ev=r['ev']
    if any(g in ev for g in ['Como','München','Real Madrid','Levante']):
        print('%-50s %-16s %-60s px=%s vol=%d' % (ev[:50],r['end'],r['q'][:60],r['pr'],r['vol']))
