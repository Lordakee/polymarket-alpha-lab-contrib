"""ROUND-44C probe 2: (a) Gamma without active=true filter + start_date_min
horizon; (b) direct title searches for known next-weekend fixtures; (c)
extract the expected Nov 13-15 slate from FotMob snapshot schedules
(unfinished matches). PAPER ONLY."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
HOME = '/home/ubuntu/paper-sim'
CHAMP = f'{HOME}/championship_20261108/xg_fotmob_championship.json'
ERED = f'{HOME}/round39/raw/xg_fotmob_eredivisie.json'
BIG5 = f'{HOME}/round41/raw/xg_fotmob_big5_merged.json'
LO, HI = '2026-11-13T00:00:00Z', '2026-11-16T00:00:00Z'


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400, 422):
                return {'__http_error__': e.code}
            last = e
            time.sleep(1.5 + i)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    if last:
        raise last
    return None


def probe_inactive():
    # per-league horizon WITHOUT active filter
    for tag in ('epl', 'efl-championship', 'bundesliga', 'la-liga', 'sea',
                'ligue-1', 'ere'):
        try:
            resp = get(BASE + '/events?' + urllib.parse.urlencode({
                'limit': 100, 'tag_slug': tag, 'closed': 'false',
                'start_date_min': '2026-11-10T00:00:00Z',
                'order': 'startDate', 'ascending': 'false'}))
            batch = resp.get('data') if isinstance(resp, dict) else resp
            if not isinstance(batch, list):
                print('inactive-probe tag=%s -> %r' % (tag, resp))
                continue
            print('no-active-filter tag=%-18s n=%d' % (tag, len(batch)))
            for e in batch[:6]:
                print('   %s  %-48s active=%s' % (
                    str(e.get('startDate'))[:16], str(e.get('title'))[:48],
                    e.get('active')))
        except Exception as e:
            print('inactive-probe tag=%s FAILED %r' % (tag, e))
        time.sleep(0.5)


def search_fixture(title):
    try:
        resp = get(BASE + '/public-search?' + urllib.parse.urlencode({
            'query': title, 'limit_per_type': 8}))
        events = (resp or {}).get('events') or []
        for ev in events:
            print('   search-hit id=%s  %-52s  %s' % (
                ev.get('id'), str(ev.get('title'))[:52], ev.get('startDate')))
        return events
    except Exception as e:
        print('   search %r FAILED %r' % (title, e))
        return []


def slate_from_snapshot(path, label):
    """FotMob raw snapshot: find scheduled (unfinished) league matches with
    kickoff in Nov 13-15 window."""
    try:
        raw = json.load(open(path))
    except Exception as e:
        print('%s: load failed %r' % (label, e))
        return []
    out = []

    def walk_matches(obj):
        if isinstance(obj, dict):
            if 'matches' in obj and isinstance(obj['matches'], list):
                for m in obj['matches']:
                    yield m
            for v in obj.values():
                yield from walk_matches(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk_matches(v)

    seen = set()
    for m in walk_matches(raw):
        if not isinstance(m, dict):
            continue
        status = (m.get('status') or {})
        if isinstance(status, dict):
            if status.get('finished') or status.get('started'):
                continue
        else:
            continue
        utc = (m.get('utcTime') or '').replace('T', ' ')[:16]
        if not utc:
            continue
        if not ('2026-11-13 00:00' <= utc <= '2026-11-15 23:59'):
            continue
        home = (((m.get('home') or {}).get('name')))
        away = (((m.get('away') or {}).get('name')))
        key = (utc, home, away)
        if key in seen:
            continue
        seen.add(key)
        out.append((utc, home, away, m.get('id')))
    out.sort()
    print('%s: scheduled Nov 13-15 matches = %d' % (label, len(out)))
    for utc, h, a, mid in out:
        print('   %s  %s vs %s  (fotmob %s)' % (utc, h, a, mid))
    return out


def main():
    print('UTC now:', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    print('--- (a) Gamma horizon without active filter ---')
    probe_inactive()

    print('--- (b) FotMob snapshot schedules for Nov 13-15 ---')
    slate = {}
    slate['Championship'] = slate_from_snapshot(CHAMP, 'Championship')
    slate['Eredivisie'] = slate_from_snapshot(ERED, 'Eredivisie')
    slate['Big5'] = slate_from_snapshot(BIG5, 'Big5-merged')

    print('--- (c) Gamma title searches for sample next-weekend fixtures ---')
    samples = []
    for lg in ('Big5', 'Championship', 'Eredivisie'):
        for utc, h, a, mid in slate.get(lg, [])[:3]:
            samples.append((lg, utc, h, a))
    for lg, utc, h, a in samples:
        title = '%s vs. %s' % (h, a)
        print('   [%s] %s %s' % (lg, utc, title))
        search_fixture(title)
        time.sleep(0.6)

    json.dump({lg: [{'utc': u, 'home': h, 'away': a, 'fotmob_id': mid}
                    for u, h, a, mid in rows]
               for lg, rows in slate.items()},
              open(f'{HOME}/round44/raw/fotmob_slate_44c.json', 'w'), indent=1)
    print('saved fotmob_slate_44c.json')


if __name__ == '__main__':
    main()
