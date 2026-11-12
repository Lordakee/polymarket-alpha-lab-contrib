import json, urllib.request, gzip, time

def get(url, referer):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': referer,
        'Accept-Encoding': 'gzip',
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return json.loads(data.decode())

CANDS = ['Eredivisie','Liga_portugal','Primeira_Liga','Premier_League','Serie_B','Super_Lig','Jupiler_League','Scottish_Premiership','Championship','EFL_Championship','Bundesliga_2','Segunda_Division','La_liga_2','MLS','Saudi_League','Turkish_League','Belgian_League','K_League','J_League','A_League','Liga_MX','Brasileirao']
ok={}
for lg in CANDS:
    for se in ['2026','2025']:
        try:
            d = get('https://understat.com/getLeagueData/'+lg+'/'+se, 'https://understat.com/league/'+lg+'/'+se)
            teams=d.get('teams',{})
            n=sum(len(t.get('history',[])) for t in teams.values())
            print('OK %-22s %s teams=%d matches=%d'%(lg,se,len(teams),n//2),flush=True)
            ok['%s_%s'%(lg,se)]=d
            break
        except Exception as e:
            msg=repr(e)[:80]
            print('-- %-22s %s %s'%(lg,se,msg),flush=True)
        time.sleep(0.6)
json.dump(ok,open('/home/ubuntu/paper-sim/round10/raw/xg_probe.json','w'))
print('SAVED',list(ok.keys()))
