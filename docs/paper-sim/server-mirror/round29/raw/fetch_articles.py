import json, urllib.request, time, re, html

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'})
    with urllib.request.urlopen(req,timeout=30) as r: return r.read().decode('utf-8','replace')

def clean(h):
    h=re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>','',h)
    t=re.sub(r'<[^>]+>',' ',h)
    t=html.unescape(t)
    t=re.sub(r'\s+',' ',t)
    return t

links=json.load(open('/home/ubuntu/paper-sim/round29/raw/news_iran.json'))
targets=[]
for q,items in links.items():
    for i in items:
        t=i['t'].lower()
        if any(k in t for k in ['qeshm','defensive strikes','eve of midterm','wants a settlement','powerful response']):
            targets.append(i)
seen=set(); out={}
for i in targets:
    if i['t'] in seen: continue
    seen.add(i['t'])
    try:
        txt=clean(fetch(i['link']))[:6000]
        out[i['t']]={'src':i['s'],'pub':i['d'],'text':txt}
        print('=== ',i['s'],'|',i['d'],'|',i['t'][:80])
        # print sentences with keywords
        for kw in ['Qeshm','Strait','strike','Struck','defensive','timing','Monday','Sunday','Tuesday','overnight','deadline','ceasefire']:
            for mth in re.finditer(kw,txt):
                s=max(0,mth.start()-150); print('  ...',txt[s:mth.start()+200].strip()[:350])
                break
    except Exception as e:
        print(i['t'][:60],'ERR',e)
    time.sleep(1.3)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/iran_articles.json','w'),indent=1)
