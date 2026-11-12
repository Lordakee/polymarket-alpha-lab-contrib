import json, urllib.request, gzip, time

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return json.loads(data.decode())

OUT = {}
# NFL: week 5 MNF (Oct 12) + week 6 (Oct 15-19)
for label, dates in [('nfl_wk5_tail','20261012-20261013'),('nfl_wk6','20261015-20261020')]:
    url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + dates
    try:
        d = get(url)
        OUT[label] = d
        print('===', label)
        for ev in d.get('events', []):
            comp = ev['competitions'][0]
            home = away = None
            for c in comp['competitors']:
                if c.get('home'): home = c['team']['abbreviation']
                else: away = c['team']['abbreviation']
            od = comp.get('odds', [])
            ostr = ''
            if od:
                o = od[0]
                ostr = ' prov=%s spread=%s ou=%s awml=%s hml=%s' % (
                    o.get('provider',{}).get('name'), o.get('spread'), o.get('overUnder'),
                    o.get('awayTeamOdds',{}).get('moneyLine'), o.get('homeTeamOdds',{}).get('moneyLine'))
            print('  %s: %s @ %s %s%s' % (ev.get('date')[:16], away, home, ev['name'][:34], ostr))
    except Exception as e:
        print('ERR', label, e)
    time.sleep(0.5)

# MLB today/tomorrow
for label, dates in [('mlb_today','20261012'),('mlb_tomorrow','20261013')]:
    url = 'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=' + dates
    try:
        d = get(url)
        OUT[label] = d
        print('===', label)
        for ev in d.get('events', []):
            comp = ev['competitions'][0]
            home = away = None
            for c in comp['competitors']:
                if c.get('home'): home = c['team']['abbreviation']
                else: away = c['team']['abbreviation']
            od = comp.get('odds', [])
            ostr = ''
            if od:
                o = od[0]
                ostr = ' prov=%s awml=%s hml=%s ou=%s' % (
                    o.get('provider',{}).get('name'),
                    o.get('awayTeamOdds',{}).get('moneyLine'), o.get('homeTeamOdds',{}).get('moneyLine'), o.get('overUnder'))
            print('  %s: %s @ %s %s%s' % (ev.get('date')[:16], away, home, ev['name'][:34], ostr))
    except Exception as e:
        print('ERR', label, e)
    time.sleep(0.5)

# NHL today + tomorrow
for label, dates in [('nhl_today','20261012'),('nhl_tomorrow','20261013')]:
    url = 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=' + dates
    try:
        d = get(url)
        OUT[label] = d
        print('===', label)
        for ev in d.get('events', []):
            comp = ev['competitions'][0]
            home = away = None
            for c in comp['competitors']:
                if c.get('home'): home = c['team']['abbreviation']
                else: away = c['team']['abbreviation']
            od = comp.get('odds', [])
            ostr = ''
            if od:
                o = od[0]
                ostr = ' prov=%s awml=%s hml=%s ou=%s' % (
                    o.get('provider',{}).get('name'),
                    o.get('awayTeamOdds',{}).get('moneyLine'), o.get('homeTeamOdds',{}).get('moneyLine'), o.get('overUnder'))
            print('  %s: %s @ %s %s%s' % (ev.get('date')[:16], away, home, ev['name'][:34], ostr))
    except Exception as e:
        print('ERR', label, e)
    time.sleep(0.5)

json.dump(OUT, open('/home/ubuntu/paper-sim/round2/raw/espn_odds.json','w'), indent=1)
print('saved espn_odds.json')
