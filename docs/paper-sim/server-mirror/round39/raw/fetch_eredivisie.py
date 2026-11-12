"""Round-39A: Eredivisie xG snapshot fetch (WP-P3 pattern, Eredivisie run).

Uses the LIBRARY fetch/transform path (polymarket_alpha_lab.papersim.fotmob)
with FotMobLeague.EREDIVISIE constants (id 57, 34 rounds, 18 teams), plus the
Phase-1 on-disk matchDetails cache so an interrupted run resumes. Both season
blocks required by the xg rating path: Eredivisie_2026 (current 2026/27) and
Eredivisie_2025 (prior 2025/26). Paper-only, no credentials, polite spacing.
"""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/polymarket-alpha-lab/src')
from polymarket_alpha_lab.papersim import fotmob

MD_DIR = Path('/home/ubuntu/paper-sim/tools/fotmob_cache/md')
FX_DIR = Path('/home/ubuntu/paper-sim/tools/fotmob_cache/fixtures')
OUT = Path('/home/ubuntu/paper-sim/round39/raw/xg_fotmob_eredivisie.json')
META = OUT.with_name(OUT.name + '.meta.json')
MD_DIR.mkdir(parents=True, exist_ok=True)
FX_DIR.mkdir(parents=True, exist_ok=True)

LG = fotmob.FotMobLeague.EREDIVISIE
SEASONS = (('2026', None), ('2025', '2025/2026'))

def log(msg):
    print('[%s] %s' % (datetime.now(timezone.utc).strftime('%H:%M:%S'), msg), flush=True)

def atomic_write(path, text):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    tmp.rename(path)

snapshot = {}
meta = {'fetched_utc': None, 'league': 'Eredivisie', 'league_id': 57,
        'seasons': {}, 'library_constants': {'max_round': 34, 'team_count': 18}}
new_fetches = 0
for season_key, season_param in SEASONS:
    payload = fotmob.fetch_fotmob_league(LG, season=season_param)
    fx_cache = FX_DIR / ('leagues_57_%s.json' % season_key)
    atomic_write(fx_cache, json.dumps(payload))
    matches = payload.get('fixtures', {}).get('allMatches', [])
    parts = fotmob._partition_matches(matches, LG.max_round)
    kept = parts['kept']
    log('season %s: total=%d kept=%d playoff=%d cancelled=%d unfinished=%d' % (
        season_key, len(matches), len(kept), len(parts['playoff']),
        len(parts['cancelled']), len(parts['unfinished'])))
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
        if new_fetches % 50 == 0:
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
        'dates_range': [b['dates'][0]['datetime'], b['dates'][-1]['datetime']]
            if b['dates'] else [],
        'new_md_fetches_this_run': None,
    }
    log('season %s: block built, %d dates, %d teams' % (
        season_key, len(b['dates']), len(b['teams'])))

meta['fetched_utc'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
meta['new_matchdetails_fetches'] = new_fetches
atomic_write(OUT, json.dumps(snapshot, indent=1) + '\n')
atomic_write(META, json.dumps(meta, indent=1) + '\n')
log('WROTE %s (blocks: %s, new fetches %d)' % (OUT, sorted(snapshot), new_fetches))
