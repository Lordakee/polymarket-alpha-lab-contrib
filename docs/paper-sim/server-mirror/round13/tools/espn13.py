"""Round-13 ESPN scoreboard sweep for Big-5 leagues + cups, Oct 22-27."""
import json, os, time, urllib.request

OUT='/home/ubuntu/paper-sim/round13/raw/espn'
def get(url, tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
        except Exception as e:
            if i==tries-1: return {'err':repr(e)}
            time.sleep(1.5)

LEAGUES=['eng.1','eng.2','esp.1','ita.1','ger.1','fra.1','eng.league_cup','eng.fa']
DATES=['20261022','20261023','20261024','20261025','20261026','20261027']
summary={}
for lg in LEAGUES:
    for dt in DATES:
        u='https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s'%(lg,dt)
        d=get(u)
        fn=os.path.join(OUT,'%s_%s.json'%(lg,dt))
        json.dump(d,open(fn,'w'))
        evs=d.get('events') or []
        if d.get('err'):
            print('%-16s %s ERR %s'%(lg,dt,d['err'][:60])); continue
        for e in evs:
            comp=e.get('competitions',[{}])[0]
            status=(comp.get('status') or {}).get('type') or {}
            teams=[]
            inj=0
            for c in comp.get('competitors',[]):
                teams.append((c.get('team') or {}).get('displayName','?'))
                inj+=len(c.get('injuries') or [])
            odds=(comp.get('odds') or [{}])[0]
            ou=odds.get('overUnder'); ml=odds.get('details')
            key='%s | %s vs %s'%(dt,teams[0] if teams else '?',teams[1] if len(teams)>1 else '?')
            summary[key]={'league':lg,'date':dt,'status':status.get('name'),'state':status.get('state'),
                          'detail':status.get('shortDetail'),'injuries_listed':inj,'ou_line':ou,
                          'venue':(comp.get('venue') or {}).get('fullName'),'id':e.get('id')}
            print('%-16s %s %-34s vs %-30s st=%-10s inj=%d OU=%s'%(lg,dt,teams[0][:34] if teams else '?',teams[1][:30] if len(teams)>1 else '?',status.get('state'),inj,ou))
        time.sleep(0.3)
json.dump(summary,open('/home/ubuntu/paper-sim/round13/raw/espn/summary.json','w'),indent=1)
print('saved summary.json events=',len(summary))
