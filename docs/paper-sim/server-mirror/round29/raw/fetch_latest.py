import json, urllib.request, time, datetime, urllib.parse, xml.etree.ElementTree as ET
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
tok='67102598924726349989742049657609063097299442010642912942032681022413402597017'
end=int(time.time()); start=end-2*3600
h=get(f'https://clob.polymarket.com/prices-history?market={tok}&startTs={start}&endTs={end}&fidelity=1')
pts=h.get('history',[])
print('last points:')
for p in pts[-25:]:
    print(datetime.datetime.fromtimestamp(p['t'],datetime.timezone.utc).strftime('%H:%M:%S'),p['p'])
json.dump(h,open('/home/ubuntu/paper-sim/round29/raw/ceasefire_last2h.json','w'))
time.sleep(1.2)
# fresh news
def rss(q, n=12):
    url='https://www.bing.com/news/search?'+urllib.parse.urlencode({'q':q,'format':'RSS'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    items=[]
    for it in root.iter('item'):
        items.append({'t':it.findtext('title'),'d':it.findtext('pubDate')})
        if len(items)>=n: break
    return items
for q in ['Qeshm strike resolution','US Iran strike October 31 deadline','Polymarket Iran ceasefire resolve']:
    print('=== '+q)
    for i in rss(q):
        print(i['d'],'|',i['t'][:110])
    time.sleep(1.3)
