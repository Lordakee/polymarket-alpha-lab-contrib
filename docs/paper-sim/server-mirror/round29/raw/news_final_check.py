import json, urllib.request, urllib.parse, time, xml.etree.ElementTree as ET
def rss(q, n=12):
    url='https://www.bing.com/news/search?'+urllib.parse.urlencode({'q':q,'format':'RSS'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    out=[]
    for it in root.iter('item'):
        out.append((it.findtext('pubDate'),it.findtext('title')))
        if len(out)>=n: break
    return out
out={}
for q in ['Iran','Qeshm October 29 strike','Bandar-e Jask missiles naval facility','US strikes Iran before deadline ceasefire market']:
    print('=== '+q)
    items=rss(q)
    out[q]=[{'d':d,'t':t} for d,t in items]
    for d,t in items[:12]:
        print(d,'|',t[:115])
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/news_final_check.json','w'),indent=1)
