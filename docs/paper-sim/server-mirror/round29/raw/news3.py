import json, urllib.request, urllib.parse, time, xml.etree.ElementTree as ET
def rss(q, n=20, when=''):
    url='https://www.bing.com/news/search?'+urllib.parse.urlencode({'q':q,'format':'RSS'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    items=[]
    for it in root.iter('item'):
        items.append({'t':it.findtext('title'),'d':it.findtext('pubDate'),'desc':(it.findtext('description') or '')[:300]})
        if len(items)>=n: break
    return items
out={}
for q in ['Qeshm explosions October','IRGC drone Qeshm MQM-170','US secret strikes Iran weeks commercial shipping','Iran explosions Bandar Lengeh']:
    try:
        items=rss(q)
        out[q]=items
        print('=== '+q+' ===')
        for i in items[:12]:
            print(i['d'],'|',i['t'][:105])
    except Exception as e:
        print(q,'ERR',e)
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/news_bing_qeshm.json','w'),indent=1)
