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

targets=[
 'Democrats lead Republicans in 5 of 7 Senate battlegrounds, new polls show',
 'On election eve, Democrats see good news in polls',
 'Polling guru',
 'Democrats lead in 5 Republican-held Senate races ahead of US midterms',
 'Michigan Senate race shifts',
 'Election',
]
seen=set(); out={}
for q in ['Democrats lead 5 of 7 Senate battlegrounds polls','election eve Democrats good news polls','polling guru midterm prediction new high final polls','Democrats lead 5 Republican-held Senate races polls','Cook Political Report Michigan Senate lean Democrat final rating']:
    for i in rss(q,8):
        if i['t'] in seen: continue
        if not any(k.lower() in i['t'].lower() for k in ['Senate','poll','forecast','prediction','midterm','Congress']): continue
        seen.add(i['t'])
        m=re.search(r'url=([^&]+)',i['link'] or '')
        if not m: continue
        u=urllib.parse.unquote(m.group(1))
        try:
            txt=clean(fetch(u))
            if len(txt)>800:
                out[i['t']]={'pub':i['d'],'url':u,'text':txt[:9000]}
                print('OK',len(txt),'|',i['d'],'|',i['t'][:80])
        except Exception as e:
            print('ERR',str(e)[:50],i['t'][:60])
        time.sleep(1.2)
        if len(out)>=7: break
    if len(out)>=7: break
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/senate_articles.json','w'),indent=1)
