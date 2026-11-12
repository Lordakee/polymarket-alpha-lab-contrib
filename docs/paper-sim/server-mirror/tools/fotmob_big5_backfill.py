#!/usr/bin/env python3
"""WP round36 data recovery: FotMob Big-5 backfill (Understat outage).

Understat has been down since Oct 31 (round25 snapshot). Fetches the
Nov 1 -> now completed Big-5 league matches from FotMob's public
unofficial API (same transport/cache policy as fotmob_adapter.py) and
emits standalone Understat-wire-format blocks keyed by Understat league
keys (EPL_2026, La_liga_2026, ...) with FOTMOB team ids. The
Understat-id merge happens separately (fotmob_big5_merge.py).

League ids verified against payload details.name at run time
(fail-closed). Verified 2026-11-05: 47=Premier League, 55=Serie A,
87=LaLiga, 53=Ligue 1, 54=Bundesliga.

Also fetches the N most recent completed matches BEFORE the window per
league (--verify-pre) for provider/xG-quality verification only; they
are recorded in the meta, never merged.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/paper-sim/tools')
import fotmob_adapter as fa  # noqa: E402  (transport + extraction, Phase 1 validated)

# (fotmob_id, expected_name, understat_league_key, max_round, team_count)
LEAGUES = (
    (47, 'Premier League', 'EPL', 38, 20),
    (87, 'LaLiga', 'La_liga', 38, 20),
    (55, 'Serie A', 'Serie_A', 38, 20),
    (54, 'Bundesliga', 'Bundesliga', 34, 18),
    (53, 'Ligue 1', 'Ligue_1', 34, 18),
)
WINDOW_START = '2026-11-01T00:00:00Z'
SEASON_KEY = '2026'


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    shutil.move(str(tmp), str(path))


def md_provider_info(md: dict) -> dict:
    """Best-effort provider fingerprint from a matchDetails payload."""
    out = {}
    general = md.get('general') or {}
    if isinstance(general, dict):
        for k in ('dataProvider', 'data_provider'):
            if general.get(k):
                out['general.' + k] = general[k]
    header = md.get('header') or {}
    if isinstance(header, dict):
        if header.get('dataProvider'):
            out['header.dataProvider'] = header['dataProvider']
        out['header.id'] = header.get('id')
        out['header.name'] = header.get('name')
    return out


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', type=Path,
                        default=Path('/home/ubuntu/paper-sim/round36/raw'))
    parser.add_argument('--cache-dir', type=Path, default=here / 'fotmob_cache')
    parser.add_argument('--sleep', type=float, default=fa.SLEEP_S)
    parser.add_argument('--verify-pre', type=int, default=2,
                        help='pre-window completed matches per league for verification')
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    now_s = started.strftime('%Y-%m-%dT%H:%M:%SZ')
    md_dir = args.cache_dir / 'md'
    fx_dir = args.cache_dir / 'fixtures'
    md_dir.mkdir(parents=True, exist_ok=True)
    fx_dir.mkdir(parents=True, exist_ok=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    ip = {'ip': fa.doh_resolve(fa.HOST)}
    fa.log('DoH {} -> {}'.format(fa.HOST, ip['ip']))

    snapshot = {}
    fetches = 0
    cache_hits = 0
    league_meta = {}
    providers_seen = {}

    def get_md(mid: str) -> dict:
        nonlocal fetches, cache_hits
        cf = md_dir / (mid + '.json')
        if cf.exists():
            cache_hits += 1
            return json.loads(cf.read_text())
        time.sleep(args.sleep)
        payload = fa.fetch_json(
            'https://{}/api/data/matchDetails?matchId={}'.format(fa.HOST, mid), ip)
        atomic_write(cf, json.dumps(payload))
        fetches += 1
        return payload

    for lid, expected_name, key, max_round, team_count in LEAGUES:
        url = 'https://{}/api/data/leagues?id={}'.format(fa.HOST, lid)
        league = fa.fetch_json(url, ip)
        name = (league.get('details') or {}).get('name')
        selected = (league.get('details') or {}).get('selectedSeason')
        if name != expected_name:
            raise fa.AdapterError(
                'league id {} returned name {!r}, expected {!r}'.format(lid, name, expected_name))
        if selected != '2026/2027':
            raise fa.AdapterError(
                'league id {} selectedSeason {!r}, expected 2026/2027'.format(lid, selected))
        atomic_write(fx_dir / ('leagues_{}_2026.json'.format(lid)), json.dumps(league))
        matches = league['fixtures']['allMatches']
        parts = fa.partition_matches(matches)

        def in_window(m):
            return m['status']['utcTime'] >= WINDOW_START and m['status']['utcTime'] <= now_s

        window = [m for m in parts['kept'] if in_window(m)]
        window.sort(key=lambda m: m['status']['utcTime'])
        pre = [m for m in parts['kept'] if m['status']['utcTime'] < WINDOW_START]
        pre.sort(key=lambda m: m['status']['utcTime'])
        pre_verify = pre[-args.verify_pre:] if args.verify_pre else []

        fa.log('{} (id {}): {} window matches, {} pre-window verify'.format(
            key, lid, len(window), len(pre_verify)))

        details = {}
        for m in window + pre_verify:
            details[str(m['id'])] = get_md(str(m['id']))

        # provider fingerprint from every fetched md
        for mid, md in details.items():
            for k, v in md_provider_info(md).items():
                providers_seen.setdefault(k, {}).setdefault(str(v), 0)
                providers_seen[k][str(v)] += 1

        index = fa.team_index(matches)
        if len(index) != team_count:
            fa.log('  WARNING: {} team table has {} teams (expected {})'.format(
                key, len(index), team_count))

        # window block (Understat wire shape, FotMob ids)
        block, skipped = fa.build_block(SEASON_KEY, window, details, index)
        if skipped:
            fa.log('  skipped no-xg window matches: {}'.format(skipped))
        snapshot['{}_{}'.format(key, SEASON_KEY)] = block

        # pre-window verification rows (meta only)
        pre_rows = []
        for m in pre_verify:
            mid = str(m['id'])
            md = details[mid]
            xg = fa.extract_xg_pair(md, 'Expected goals (xG)')
            npxg = fa.extract_xg_pair(md, 'xG non-penalty')
            score = fa.extract_score(md)
            pre_rows.append({
                'match': '{} v {}'.format(m['home']['name'], m['away']['name']),
                'utc': m['status']['utcTime'], 'score': score, 'xg': xg, 'npxg': npxg,
                'provider': md_provider_info(md),
            })
            if xg is None or score is None:
                fa.log('  VERIFY-WARN pre-window {} has xg={} score={}'.format(mid, xg, score))

        league_meta[key] = {
            'fotmob_id': lid, 'api_name': name, 'selected_season': selected,
            'league_dataProvider': (league.get('details') or {}).get('dataProvider'),
            'window_start': WINDOW_START, 'window_end_inclusive': now_s,
            'window_matches': len(window), 'window_with_xg': len(block['dates']),
            'window_skipped_no_xg': skipped,
            'pre_window_verify': pre_rows,
            'unfinished_in_window': len([m for m in matches
                                         if in_window(m) and not m['status'].get('finished')]),
            'cancelled_total_season': len(parts['cancelled']),
            'first_window_utc': window[0]['status']['utcTime'] if window else None,
            'last_window_utc': window[-1]['status']['utcTime'] if window else None,
        }
        fa.log('  {} block: {} dates, {} skipped'.format(
            key, len(block['dates']), len(skipped)))

    ended = datetime.now(timezone.utc)
    out_path = args.out_dir / 'xg_fotmob_big5_new.json'
    meta_path = args.out_dir / 'xg_fotmob_big5_new.json.meta.json'
    atomic_write(out_path, json.dumps(snapshot, indent=1) + '\n')
    meta = {
        'generated_utc': ended.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'duration_s': round((ended - started).total_seconds(), 1),
        'purpose': 'Understat outage data recovery (down since Oct 31); Nov 1+ Big-5 backfill',
        'provider': 'fotmob.com/api/data (unofficial, no key); match-level provider fingerprints below',
        'league_id_mapping_verified': {
            '47': 'Premier League', '87': 'LaLiga', '55': 'Serie A',
            '54': 'Bundesliga', '53': 'Ligue 1'},
        'note_id_conflict': ('dispatch prompt had LaLiga=55/SerieA=87/Bundesliga=53/Ligue1=54; '
                             'API details.name shows 55=Serie A, 87=LaLiga, 53=Ligue 1, 54=Bundesliga '
                             '(matches library fotmob.py docstring). API is authoritative.'),
        'championship_reference_provider': 'league-level dataProvider=opta (id 48, WP-P3 validated)',
        'providers_seen_in_matchdetails': {k: dict(v) for k, v in providers_seen.items()},
        'leagues': league_meta,
        'backfill_stats': {
            'matchdetails_new_fetches': fetches,
            'matchdetails_cache_hits': cache_hits,
            'rate_limit_seconds': args.sleep,
        },
        'wire_format': 'Understat snapshot shape (FotMob team ids; merge script maps to Understat ids)',
    }
    atomic_write(meta_path, json.dumps(meta, indent=1) + '\n')
    fa.log('wrote {} ({})'.format(out_path, out_path.stat().st_size))
    fa.log('wrote {}'.format(meta_path))
    fa.log('fetches={} cache_hits={} duration={:.0f}s'.format(
        fetches, cache_hits, meta['duration_s']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
