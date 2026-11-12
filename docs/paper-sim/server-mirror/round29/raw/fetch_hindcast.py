import json, urllib.request, time, re, html
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'})
    with urllib.request.urlopen(req,timeout=30) as r: return r.read().decode('utf-8','replace')
def clean(h):
    h=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>','',h)
    t=re.sub(r'<[^>]+>',' ',h); t=html.unescape(t); return re.sub(r'\s+',' ',t)
out={}
for u in ['https://hindcast.ai/disputes','https://hindcast.ai/']:
    try:
        t=clean(fetch(u))
        out[u]=t[:12000]
        print('OK',u,len(t))
        # print dispute-related lines
        for kw in ['ceasefire','Iran','Qeshm','October 31','Oct 31','dispute','UMA']:
            for m in re.finditer(kw,t,re.I):
                s=max(0,m.start()-120); print(' ...',t[s:m.start()+250].strip()[:340]); break
    except Exception as e:
        print('ERR',u,str(e)[:90])
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/hindcast.json','w'),indent=1)
