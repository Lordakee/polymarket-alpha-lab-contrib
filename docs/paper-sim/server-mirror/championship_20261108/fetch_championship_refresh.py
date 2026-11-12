"""Championship xG snapshot refresh (2026-11-08): clears the staleness gap.

The round-31 Championship snapshot ends 2026-11-03, missing the Tue Nov-4
midweek round and the Sat Nov-7 round. This refresh uses the LIBRARY
fetch/transform path (polymarket_alpha_lab.papersim.fotmob) with
FotMobLeague.CHAMPIONSHIP constants (id 48, 46 numeric rounds, 24 teams),
the Phase-1 on-disk matchDetails cache (incremental: only matches missing
from the cache are fetched, polite 1.3s spacing), and atomic tmp+rename
publish. Both season blocks required by the xg rating path:
Championship_2026 (current 2026/27) and Championship_2025 (prior 2025/26).

Writes a NEW snapshot file in its own directory; does NOT modify
round31/raw/xg_fotmob_championship.json and does NOT touch
~/paper-sim/understat_latest.json (Big-5 merge pointer) or any pointer.
Paper-only, no credentials, read-only on the repo.
"""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/polymarket-alpha-lab/src')
from polymarket_alpha_lab.papersim import fotmob

MD_DIR = Path('/home/ubuntu/paper-sim/tools/fotmob_cache/md')
FX_DIR = Path('/home/ubuntu/paper-sim/tools/fotmob_cache/fixtures')
OUT_DIR = Path('/home/ubuntu/paper-sim/championship_20261108')
OUT = OUT_DIR / 'xg_fotmob_championship.json'
META = OUT.with_name(OUT.name + '.meta.json')
MD_DIR.mkdir(parents=True, exist_ok=True)
FX_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

LG = fotmob.FotMobLeague.CHAMPIONSHIP
SEASONS = (('2026', None), ('2025', '2025/2026'))

def log(msg):
    print('[%s] %s' % (datetime.now(timezone.utc).strftime('%H:%M:%S'), msg), flush=True)

def atomic_write(path, text):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    tmp.rename(path)

snapshot = {}
meta = {'fetched_utc': None, 'league': 'Championship', 'league_id': 48,
        'library_constants': {'max_round': 46, 'team_count': 24},
        'refresh_reason': ('round-31 snapshot ended 2026-11-03; adds the '
                           '2026-11-04 midweek round and the Sat 2026-11-07 round'),
        'replaces_without_modifying': '/home/ubuntu/paper-sim/round31/raw/xg_fotmob_championship.json',
        'pointer_note': 'understat_latest.json untouched (Big-5 merge); no pointers moved',
        'seasons': {}}
new_fetches = 0
for season_key, season_param in SEASONS:
    payload = fotmob.fetch_fotmob_league(LG, season=season_param)
    fx_cache = FX_DIR / ('leagues_48_%s.json' % season_key)
    atomic_write(fx_cache, json.dumps(payload))
    matches = payload.get('fixtures', {}).get('allMatches', [])
    parts = fotmob._partition_matches(matches, LG.max_round)
    kept = parts['kept']
    rounds = sorted({int(m['round']) for m in kept})
    log('season %s: total=%d kept=%d playoff=%d cancelled=%d unfinished=%d kept_rounds=%s..%s' % (
        season_key, len(matches), len(kept), len(parts['playoff']),
        len(parts['cancelled']), len(parts['unfinished']),
        rounds[0] if rounds else -1, rounds[-1] if rounds else -1))
    details = {}
    for i, m in enumerate(kept, 1):
        mid = str(m['id'])
        cf = MD_DIR / ('%s.json' % mid)
        if cf.exists():
            details[mid] = json.loads(cf.read_text())
            continue
        time.sleep(fotmob.SLEEP_S)
        md = fotmob.fetch_match_details(mid)
        atomic_write(cf, json.dumps(md))
        details[mid] = md
        new_fetches += 1
        if new_fetches % 25 == 0:
            log('  season %s: %d/%d matchDetails (%d new fetches)' % (
                season_key, i, len(kept), new_fetches))
    block_bundle = {'fixtures': payload, 'details': details}
    block = fotmob.fotmob_to_understat(block_bundle, LG, season_key)
    snapshot.update(block)
    b = list(block.values())[0]
    meta['seasons'][season_key] = {
        'kept_finished_numeric': len(kept),
        'playoff': len(parts['playoff']), 'cancelled': len(parts['cancelled']),
        'unfinished': len(parts['unfinished']),
        'dates': len(b['dates']), 'teams': len(b['teams']),
        'skipped_no_xg': len(kept) - len(b['dates']),
        'kept_round_range': [rounds[0], rounds[-1]] if rounds else [],
        'dates_range': [b['dates'][0]['datetime'], b['dates'][-1]['datetime']]
            if b['dates'] else [],
    }
    log('season %s: block built, %d dates, %d teams' % (
        season_key, len(b['dates']), len(b['teams'])))

meta['fetched_utc'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
meta['new_matchdetails_fetches'] = new_fetches
atomic_write(OUT, json.dumps(snapshot, indent=1) + '\n')
atomic_write(META, json.dumps(meta, indent=1) + '\n')
log('WROTE %s (blocks: %s, new fetches %d)' % (OUT, sorted(snapshot), new_fetches))
