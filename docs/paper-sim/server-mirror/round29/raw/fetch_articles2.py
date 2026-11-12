import json, urllib.request, urllib.parse, time, re, html

def fetch(url, timeout=25):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return r.read().decode('utf-8','replace')

def clean(h):
    h=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>','',h)
    t=re.sub(r'<[^>]+>',' ',h); t=html.unescape(t); return re.sub(r'\s+',' ',t)

d=json.load(open('/home/ubuntu/paper-sim/round29/raw/news_bing_iran.json'))
urls=[]
for q,items in d.items():
    for i in items:
        m=re.search(r'url=([^&]+)',i['link'])
        if m:
            u=urllib.parse.unquote(m.group(1))
            if u not in urls: urls.append((u,i['t'],i['d']))

out={}
for u,t,dt in urls[:14]:
    try:
        txt=clean(fetch(u))
        out[u]={'title':t,'pub':dt,'text':txt[:9000]}
        print('OK',len(txt),u[:100])
    except Exception as e:
        print('ERR',str(e)[:60],u[:100])
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/iran_articles2.json','w'),indent=1)
