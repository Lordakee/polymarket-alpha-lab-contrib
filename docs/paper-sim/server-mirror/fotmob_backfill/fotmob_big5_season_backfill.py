#!/usr/bin/env python3
"""WP-P5 bridge data backfill: complete Big-5 seasons 2023/24 + 2024/25
(+ the 2025/26 overlap season) from FotMob, in Understat wire format.

Library path (2026-11-10 dispatch): polymarket_alpha_lab.papersim.fotmob -
fetch_fotmob_league / fetch_match_details (module-wide polite spacing 1.3 s,
4 attempts with backoff) + fotmob_to_understat (pure, fail-closed transform
with per-league max_round / team_count). This runner adds the server-side
on-disk cache (resume-safe, same pattern as paper-sim/tools/fotmob_adapter.py)
and atomic tmp+rename writes.

Writes ONLY under ~/paper-sim/fotmob_backfill/. No repo changes, no DB, no
credentials, production understat_latest.json pointer untouched.

Outputs per season: big5_<season>.json ({League}_{season}: {teams, dates}}
blocks, Understat wire shape, FotMob team ids) + big5_<season>.json.meta.json.
Season key convention (project standard): 2023 -> FotMob '2023/2024',
2024 -> '2024/2025', 2025 -> '2025/2026'.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_SRC = '/home/ubuntu/polymarket-alpha-lab/src'
sys.path.insert(0, REPO_SRC)

import polymarket_alpha_lab.papersim.fotmob as fm  # noqa: E402

BASE = Path('/home/ubuntu/paper-sim/fotmob_backfill')
MD_DIR = BASE / 'cache' / 'md'
FX_DIR = BASE / 'cache' / 'fixtures'

# (fotmob_id, expected details.name, block key, max_round, team_count, expected_kept)
LEAGUES = (
    (47, 'Premier League', 'EPL', 38, 20, 380),
    (87, 'LaLiga', 'La_liga', 38, 20, 380),
    (55, 'Serie A', 'Serie_A', 38, 20, 380),
    (54, 'Bundesliga', 'Bundesliga', 34, 18, 306),
    (53, 'Ligue 1', 'Ligue_1', 34, 18, 306),
)
SEASONS = ('2023', '2024', '2025')  # 2025 = overlap season for the G1 scale check


def log(msg: str) -> None:
    print('[{}] {}'.format(datetime.now(timezone.utc).strftime('%H:%M:%S'), msg), flush=True)


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    shutil.move(str(tmp), str(path))


def season_param(season_key: str) -> str:
    y = int(season_key)
    return '{}/{}'.format(y, y + 1)


def provider_info(md: dict) -> dict:
    out = {}
    general = md.get('general') or {}
    if isinstance(general, dict):
        for k in ('dataProvider', 'data_provider'):
            if general.get(k):
                out['general.' + k] = str(general[k])
    header = md.get('header') or {}
    if isinstance(header, dict) and header.get('dataProvider'):
        out['header.dataProvider'] = str(header['dataProvider'])
    return out


def main() -> int:
    run_started = datetime.now(timezone.utc)
    for d in (BASE, MD_DIR, FX_DIR):
        d.mkdir(parents=True, exist_ok=True)
    log('backfill start utc={} library={} sleep={}s'.format(
        run_started.strftime('%Y-%m-%dT%H:%M:%SZ'), fm.__name__, fm.SLEEP_S))

    counters = {'fetches': 0, 'cache_hits': 0}
    seasons_meta = {}

    def get_md(mid: str) -> dict:
        cf = MD_DIR / (mid + '.json')
        if cf.exists():
            counters['cache_hits'] += 1
            return json.loads(cf.read_text())
        payload = fm.fetch_match_details(mid)
        atomic_write(cf, json.dumps(payload))
        counters['fetches'] += 1
        return payload

    for season in SEASONS:
        t_season = time.monotonic()
        snapshot = {}
        league_meta = {}
        sparam = season_param(season)
        for lid, expected_name, key, max_round, team_count, exp_kept in LEAGUES:
            t0 = time.monotonic()
            fx_cache = FX_DIR / ('leagues_{}_{}.json'.format(lid, season))
            if fx_cache.exists():
                fixtures = json.loads(fx_cache.read_text())
                counters['cache_hits'] += 1
            else:
                fixtures = fm.fetch_fotmob_league(lid, sparam)
                atomic_write(fx_cache, json.dumps(fixtures))
                counters['fetches'] += 1
            name = (fixtures.get('details') or {}).get('name')
            selected = (fixtures.get('details') or {}).get('selectedSeason')
            if name != expected_name or selected != sparam:
                league_meta[key] = {
                    'error': 'league id/name/season mismatch: name={!r} (want {!r}), '
                             'selectedSeason={!r} (want {!r})'.format(
                                 name, expected_name, selected, sparam)}
                log('season {}: {}: ERROR: {}'.format(season, key, league_meta[key]['error']))
                continue
            matches = fixtures['fixtures']['allMatches']
            parts = fm._partition_matches(matches, max_round)
            kept = parts['kept']
            log('season {}: {} fixtures={} kept={} playoff={} cancelled={} unfinished={} (expected kept {})'.format(
                season, key, len(matches), len(kept), len(parts['playoff']),
                len(parts['cancelled']), len(parts['unfinished']), exp_kept))

            details = {}
            failed = {}
            for i, m in enumerate(kept, 1):
                mid = str(m['id'])
                try:
                    details[mid] = get_md(mid)
                except fm.FotMobError as exc:
                    failed[mid] = str(exc)[:200]
                    log('  md FAILED {} {}: {}'.format(season, mid, str(exc)[:120]))
                if i % 50 == 0 or i == len(kept):
                    log('  season {}: {}/{} md done ({} new fetches, {} cache hits so far)'.format(
                        season, key, i, len(kept), counters['fetches'], counters['cache_hits']))
            if failed:
                log('season {}: {} retrying {} failed mds after 30 s backoff'.format(
                    season, key, len(failed)))
                time.sleep(30.0)
                still = {}
                for mid in list(failed):
                    try:
                        details[mid] = get_md(mid)
                    except fm.FotMobError as exc:
                        still[mid] = str(exc)[:200]
                failed = still

            providers = {}
            for md in details.values():
                for k, v in provider_info(md).items():
                    providers.setdefault(k, {}).setdefault(v, 0)
                    providers[k][v] += 1

            try:
                block_map = fm.fotmob_to_understat(
                    {'fixtures': fixtures, 'details': details},
                    key, season, max_round=max_round, team_count=team_count)
            except (fm.FotMobSchemaError, fm.FotMobError) as exc:
                league_meta[key] = {'error': 'transform fail-closed: ' + str(exc)[:400],
                                    'kept_finished_numeric': len(kept),
                                    'md_fetch_failures': failed}
                log('season {}: {}: TRANSFORM ERROR: {}'.format(season, key, str(exc)[:200]))
                continue
            block = block_map['{}_{}'.format(key, season)]
            dates_ids = {d['id'] for d in block['dates']}
            skipped_ids = [str(m['id']) for m in kept if str(m['id']) not in dates_ids]
            snapshot.update(block_map)
            league_meta[key] = {
                'fotmob_id': lid, 'api_name': name, 'selected_season': selected,
                'league_dataProvider': (fixtures.get('details') or {}).get('dataProvider'),
                'fixtures_total': len(matches),
                'kept_finished_numeric': len(kept),
                'expected_kept': exp_kept,
                'count_ok': len(kept) == exp_kept,
                'excluded_playoff': len(parts['playoff']),
                'excluded_playoff_rounds': sorted({str(m.get('round')) for m in parts['playoff']}),
                'excluded_cancelled': len(parts['cancelled']),
                'excluded_cancelled_ids': [str(m['id']) for m in parts['cancelled']],
                'excluded_cancelled_matches': [
                    {'id': str(m['id']), 'round': str(m.get('round')),
                     'home': (m.get('home') or {}).get('name'),
                     'away': (m.get('away') or {}).get('name'),
                     'utc': (m.get('status') or {}).get('utcTime'),
                     'cancelled': (m.get('status') or {}).get('cancelled'),
                     'reason_longKey': ((m.get('status') or {}).get('reason') or {}).get('longKey'),
                     'finished': (m.get('status') or {}).get('finished')}
                    for m in parts['cancelled']],
                'excluded_unfinished': len(parts['unfinished']),
                'matches_with_xg': len(block['dates']),
                'skipped_no_xg_ids': skipped_ids,
                'teams': len(block['teams']),
                'expected_teams': team_count,
                'history_len_minmax': (
                    min((len(t['history']) for t in block['teams'].values()), default=0),
                    max((len(t['history']) for t in block['teams'].values()), default=0)),
                'md_fetch_failures': failed,
                'dates_range': ([block['dates'][0]['datetime'], block['dates'][-1]['datetime']]
                                if block['dates'] else None),
                'providers_seen': providers,
                'elapsed_s': round(time.monotonic() - t0, 1),
            }
            log('season {}: {} block ok - {} dates, {} teams, {} skipped, {} md failures, {:.0f}s'.format(
                season, key, len(block['dates']), len(block['teams']), len(skipped_ids),
                len(failed), time.monotonic() - t0))

        out_path = BASE / ('big5_{}.json'.format(season))
        meta_path = BASE / ('big5_{}.json.meta.json'.format(season))
        atomic_write(out_path, json.dumps(snapshot, indent=1) + '\n')
        seasons_meta[season] = {
            'season_key': season, 'api_season_param': sparam,
            'blocks': sorted(snapshot.keys()), 'leagues': league_meta,
            'league_md_counts': {k: v.get('matches_with_xg') for k, v in league_meta.items()},
            'total_matches_with_xg': sum(v.get('matches_with_xg', 0) for v in league_meta.values()),
        }
        meta = {
            'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'season_elapsed_s': round(time.monotonic() - t_season, 1),
            'purpose': ('WP-P5 two-season bridge backfill: complete Big-5 season xG '
                        'from FotMob (2023/24+2024/25 bridge revalidation; 2025/26 overlap)'),
            'provider': ('fotmob.com/api/data (unofficial, no key); per-match provider '
                         'fingerprints in leagues.*.providers_seen'),
            'library': ('polymarket_alpha_lab.papersim.fotmob '
                        '(fetch_fotmob_league/fetch_match_details/fotmob_to_understat), '
                        'polite spacing {:.1f}s'.format(fm.SLEEP_S)),
            'wire_format': ('Understat snapshot shape consumed by '
                            'polymarket_alpha_lab.papersim.xg (FotMob team ids; '
                            'Understat-id mapping is downstream)'),
            'leagues': league_meta,
            'counters': dict(counters),
            'notes': ['history xG/xGA/npxG/npxGA floats; dates xG.h/xG.a strings; '
                      'scored/missed are ACTUAL goals; datetime UTC',
                      'cancelled/abandoned fixtures excluded (explicit flag + cancel/abort reason keys)',
                      'playoff/non-numeric rounds excluded'],
        }
        atomic_write(meta_path, json.dumps(meta, indent=1) + '\n')
        log('season {}: WROTE {} ({} bytes) + meta | running total fetches={} hits={}'.format(
            season, out_path.name, out_path.stat().st_size, counters['fetches'],
            counters['cache_hits']))

    run_ended = datetime.now(timezone.utc)
    summary = {
        'generated_utc': run_ended.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'run_started_utc': run_started.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'duration_s': round((run_ended - run_started).total_seconds(), 1),
        'seasons': seasons_meta,
        'counters': counters,
    }
    atomic_write(BASE / 'backfill_summary.json', json.dumps(summary, indent=1) + '\n')
    log('backfill DONE duration={:.0f}s fetches={} cache_hits={}'.format(
        summary['duration_s'], counters['fetches'], counters['cache_hits']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
