import json, urllib.request, urllib.parse, time, xml.etree.ElementTree as ET

def rss(q, n=15):
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'en-US','gl':'US','ceid':'US:en'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    items=[]
    for it in root.iter('item'):
        items.append({'t':it.findtext('title'),'d':it.findtext('pubDate'),'s':it.findtext('source'),'link':it.findtext('link')})
        if len(items)>=n: break
    return items

out={}
for q in ['US strikes Iran','Iran United States attack','US Iran ceasefire']:
    try:
        items=rss(q)
        out[q]=items
        print('=== '+q+' ===')
        for i in items:
            print(i['d'],'|',i['s'],'|',i['t'][:110])
    except Exception as e:
        print(q,'ERR',e)
    time.sleep(1.2)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/news_iran.json','w'),indent=1)
