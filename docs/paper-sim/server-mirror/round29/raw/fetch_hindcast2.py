import json, urllib.request, time, re, html
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'})
    with urllib.request.urlopen(req,timeout=30) as r: return r.read().decode('utf-8','replace')
def clean(h):
    h=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>','',h)
    t=re.sub(r'<[^>]+>',' ',h); t=html.unescape(t); return re.sub(r'\s+',' ',t)
out={}
for u in ['https://hindcast.ai/radar','https://hindcast.ai/disputes']:
    try:
        t=clean(fetch(u))
        out[u]=t[:20000]
        print('=== ',u,len(t))
        if u.endswith('radar'):
            print(t[:3500])
    except Exception as e:
        print('ERR',u,str(e)[:90])
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/hindcast2.json','w'),indent=1)
