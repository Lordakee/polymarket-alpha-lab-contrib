"""ROUND-44C probe: why zero in-scope league events in the Nov 13-15
window? Enumerate ALL events per league-tag variant (epl, premier-league,
efl-championship, championship, bundesliga, la-liga, sea, ligue-1, ere),
bucket by kickoff (event startDate / market gameStartTime), and try
ascending-date pagination to see the listing horizon. Also probe the
/events endpoint (non-pagination) with start_date_min. PAPER ONLY."""
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    if last:
        raise last


def norm_ts(ts):
    s = str(ts or '').strip()
    if not s:
        return ''
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return ''


def sweep_all(tag, order='volume24hr', ascending='false', max_offset=3000):
    out, offset = [], 0
    while True:
        params = {'limit': 100, 'active': 'true', 'closed': 'false',
                  'order': order, 'ascending': ascending, 'offset': offset,
                  'tag_slug': tag}
        resp = get(BASE + '/events/pagination?' + urllib.parse.urlencode(params))
        batch = resp.get('data') if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100 or offset + 100 >= max_offset:
            return out
        offset += 100
        time.sleep(0.6)


def horizon(tag):
    evs = sweep_all(tag)
    buckets = Counter()
    examples = {}
    for e in evs:
        sd = norm_ts(e.get('startDate'))[:10] or 'nodate'
        buckets[sd] += 1
        examples.setdefault(sd, (e.get('title'), e.get('id'),
                                  [t.get('slug') for t in (e.get('tags') or [])][:4]))
    print('== tag %-20s total=%d' % (tag, len(evs)))
    for d in sorted(buckets, reverse=True)[:12]:
        print('   %s  n=%-3d  e.g. %s %s %s' % (d, buckets[d], examples[d][0][:44],
                                                examples[d][1], examples[d][2]))
    return evs


def main():
    for tag in ('epl', 'premier-league', 'efl-championship', 'championship',
                'bundesliga', 'la-liga', 'sea', 'ligue-1', 'ere'):
        try:
            horizon(tag)
        except Exception as e:
            print('== tag %-20s FAILED %r' % (tag, e))
        time.sleep(0.5)

    # ascending-by-startDate soccer sweep: find the farthest-future listed
    evs = sweep_all('soccer', order='startDate', ascending='true')
    fut = []
    for e in evs:
        sd = norm_ts(e.get('startDate'))
        if sd and sd >= '2026-11-13':
            tags = [t.get('slug') for t in (e.get('tags') or [])]
            fut.append((sd, e.get('title'), tags[:5]))
    fut.sort()
    print('\n== soccer tag, startDate-ascending sweep: total=%d  >=Nov-13: %d'
          % (len(evs), len(fut)))
    for sd, title, tags in fut[:40]:
        print('   %s  %-46s %s' % (sd, str(title)[:46], tags))
    # horizon of the ascending sweep (last 5 events by startDate)
    allsd = sorted(x for x in (norm_ts(e.get('startDate')) for e in evs) if x)
    print('   ascending-sweep date horizon (max 5):', allsd[-5:])

    # /events endpoint with start_date_min (non-pagination)
    for tag in ('epl', 'soccer'):
        try:
            resp = get(BASE + '/events?' + urllib.parse.urlencode({
                'limit': 20, 'tag_slug': tag, 'closed': 'false',
                'start_date_min': '2026-11-13T00:00:00Z'}))
            batch = resp.get('data') if isinstance(resp, dict) else resp
            print('\n== /events start_date_min probe tag=%s -> %d' % (tag, len(batch or [])))
            for e in (batch or [])[:12]:
                print('   %s  %-44s %s' % (norm_ts(e.get('startDate'))[:16],
                                           str(e.get('title'))[:44],
                                           [t.get('slug') for t in (e.get('tags') or [])][:4]))
        except Exception as e:
            print('== /events probe tag=%s FAILED %r' % (tag, e))


if __name__ == '__main__':
    main()
