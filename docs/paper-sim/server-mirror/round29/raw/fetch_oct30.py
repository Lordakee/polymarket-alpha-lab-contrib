import json, urllib.request, urllib.parse, time, re, html, xml.etree.ElementTree as ET
def rss(q, n=10):
    url='https://www.bing.com/news/search?'+urllib.parse.urlencode({'q':q,'format':'RSS'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    items=[]
    for it in root.iter('item'):
        items.append({'t':it.findtext('title'),'d':it.findtext('pubDate'),'link':it.findtext('link')})
        if len(items)>=n: break
    return items
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0) Chrome/120.0'})
    with urllib.request.urlopen(req,timeout=25) as r: return r.read().decode('utf-8','replace')
def clean(h):
    h=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>','',h)
    t=re.sub(r'<[^>]+>',' ',h); t=html.unescape(t); return re.sub(r'\s+',' ',t)

out={}
for q in ['Qeshm Island hit by explosions Iran reports naval base attack October 30','Iran naval base attack Qeshm October','Iran coast explosions October 30 naval base']:
    items=rss(q)
    print('=== '+q)
    for i in items[:8]:
        print(i['d'],'|',i['t'][:100])
        m=re.search(r'url=([^&]+)',i['link'] or '')
        u=urllib.parse.unquote(m.group(1)) if m else None
        if u:
            try:
                txt=clean(fetch(u))
                out[i['t']]={'pub':i['d'],'url':u,'text':txt[:8000]}
                print('    fetched',len(txt))
            except Exception as e:
                print('    ERR',str(e)[:50])
        time.sleep(1.2)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/oct30_articles.json','w'),indent=1)
