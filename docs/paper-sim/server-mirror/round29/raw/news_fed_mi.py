import json, urllib.request, urllib.parse, time, xml.etree.ElementTree as ET
def rss(q, n=14):
    url='https://www.bing.com/news/search?'+urllib.parse.urlencode({'q':q,'format':'RSS'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    out=[]
    for it in root.iter('item'):
        out.append({'t':it.findtext('title'),'d':it.findtext('pubDate'),'link':it.findtext('link')})
        if len(out)>=n: break
    return out
out={}
for q in ['Fed December rate hike FOMC October','Federal Reserve December meeting hike inflation oil','Michigan Senate El-Sayed Rogers poll','Peltola Sullivan Alaska Senate ballot']:
    try:
        items=rss(q)
        out[q]=items
        print('=== '+q+' ===')
        for i in items[:12]:
            print(i['d'],'|',i['t'][:112])
    except Exception as e:
        print(q,'ERR',e)
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/news_fed_mi.json','w'),indent=1)
