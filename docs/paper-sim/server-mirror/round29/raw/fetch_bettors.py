import json, urllib.request, urllib.parse, time, re, html, xml.etree.ElementTree as ET
def rss(q, n=6):
    url='https://www.bing.com/news/search?'+urllib.parse.urlencode({'q':q,'format':'RSS'})
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data)
    out=[]
    for it in root.iter('item'):
        out.append((it.findtext('title'),it.findtext('pubDate'),it.findtext('link')))
        if len(out)>=n: break
    return out
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0) Chrome/120.0'})
    with urllib.request.urlopen(req,timeout=25) as r: return r.read().decode('utf-8','replace')
def clean(h):
    h=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>','',h)
    t=re.sub(r'<[^>]+>',' ',h); t=html.unescape(t); return re.sub(r'\s+',' ',t)
for t,d,l in rss('Bettors Give the Iran Ceasefire 90.5% Through the Midterms'):
    print('FOUND:',t[:100],'|',d)
    m=re.search(r'url=([^&]+)',l or '')
    if m:
        u=urllib.parse.unquote(m.group(1))
        try:
            txt=clean(fetch(u))
            json.dump({'title':t,'url':u,'text':txt[:12000]},open('/home/ubuntu/paper-sim/round29/raw/bettors_article.json','w'),indent=1)
            print(txt[:4500])
        except Exception as e:
            print('ERR',e)
    break
