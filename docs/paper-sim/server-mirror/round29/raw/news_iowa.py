import json, urllib.request, urllib.parse, time, xml.etree.ElementTree as ET
def rss(q, n=10):
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
for q in ['Iowa Senate final poll Turek Hinson Des Moines Register Selzer','Iowa Senate race final days Turek Hinson']:
    items=rss(q)
    out[q]=items
    print('=== '+q+' ===')
    for i in items[:10]:
        print(i['d'],'|',i['t'][:115])
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/news_iowa.json','w'),indent=1)
