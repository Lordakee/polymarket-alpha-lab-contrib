"""ROUND-42 finalize (paper-only): build round42/raw/scan.json.

Outcome: ZERO men's UCL/UEL fixtures exist in the 2026-11-10..13 window
(in-world calendar: UCL MD4 = Nov 3-4, UEL MD4 = Nov 4-5, MD5 = Nov 24-26;
mid-November is the international window). This script records the full
enumeration evidence, calendar proof, window census, xG provenance and
staleness flags. PAPER ONLY - no orders, no DB writes.
"""
import json
import time
import urllib.request
from datetime import datetime, timezone

HOME = '/home/ubuntu/paper-sim'
OUT = HOME + '/round42/raw/scan.json'
NOW_S = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research)'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5)
    raise last


def main():
    events = json.load(open(HOME + '/round42/raw/events_window_42.json'))
    espn = json.load(open(HOME + '/round42/raw/espn_fixtures_42.json'))
    stale = json.load(open(HOME + '/round42/raw/stale_nov8_9.json'))
    pointer = json.load(open(HOME + '/understat_latest_pointer.json'))

    # dispatch-param sanity check: the exact /events query from the brief
    try:
        direct = get('https://gamma-api.polymarket.com/events?closed=false'
                     '&start_date_min=2026-11-10T00:00Z&start_date_max=2026-11-13T00:00Z&limit=100')
        direct_n = len(direct) if isinstance(direct, list) else -1
    except Exception as e:
        direct_n = repr(e)

    # open MD5 events (calendar proof) - ucl tag, matchday slugs
    md5 = []
    try:
        d = get('https://gamma-api.polymarket.com/events/pagination?limit=100'
                '&active=true&closed=false&order=volume24hr&ascending=false&tag_slug=ucl')
        for e in (d.get('data') if isinstance(d, dict) else d) or []:
            slug = str(e.get('slug') or '')
            if '2026-11-24' in slug or '2026-11-25' in slug:
                md5.append({'title': e.get('title'), 'slug': slug,
                            'endDate': str(e.get('endDate'))[:19]})
    except Exception as e:
        md5 = [{'error': repr(e)}]

    # window census: classify each in-window event by tag
    CENSUS = {
        'uefa-nations-league': ('UEFA Nations League (international window)',
                                "OUT-OF-SCOPE: national teams - no club snapshot coverage; dispatch scope is men's club UCL/UEL"),
        'copa-del-rey': ('Copa del Rey (Spanish domestic cup)',
                         'OUT-OF-SCOPE: domestic cup, not UCL/UEL; cup minnows (Anaitasuna, Pamplona, Tavernes, Tarcon, Navalcarnero, Calvo Sotelo, Mijas-Las Lagunas, Amorebieta) not in snapshot universe -> model-void pairs anyway'),
        'womens-champions-league': ("Women's Champions League (UWCL)",
                                    "OUT-OF-SCOPE: women's competition - PSG-Women vs Bayern-Women Nov 10 20:00Z; women's squads not in men's club snapshot universe"),
        'clf': ('Club Friendlies (clf series)',
                'OUT-OF-SCOPE: friendly, not UCL/UEL; placeholder pricing 0.49/0.51, volume None'),
        'colombia-primera-a': ('Colombia Primera A', 'OUT-OF-SCOPE: not UCL/UEL, no coverage'),
        'brazil-serie-b': ('Brazil Serie B', 'OUT-OF-SCOPE: not UCL/UEL, no coverage'),
    }
    fixtures = []
    seen_fx = {}
    for e in events:
        tag = next((t for t in e['tags'] if t in CENSUS), None)
        comp, verdict = CENSUS.get(tag, ('other', 'OUT-OF-SCOPE'))
        base = (e.get('title') or '').split(' - ')[0].strip()
        key = (e['kick'], base)
        if key not in seen_fx:
            seen_fx[key] = {
                'match': base, 'competition': comp, 'tag': tag,
                'kickoff_utc': e['kick'], 'gamma_event_ids': [],
                'n_markets_total': 0, 'vol24_sum': 0.0,
                'league_pairing': 'n/a (see competition)',
                'bridge_applied_lambdas': None, 'p1x2_model': None,
                'verdict': verdict}
            fixtures.append(seen_fx[key])
        seen_fx[key]['gamma_event_ids'].append(e['id'])
        seen_fx[key]['n_markets_total'] += len(e['markets'])
        try:
            seen_fx[key]['vol24_sum'] += float(e.get('vol24') or 0)
        except Exception:
            pass
    fixtures.sort(key=lambda f: (f['kickoff_utc'], f['match']))

    espn_in_window = {}
    for date, day in espn.items():
        for lg, v in day.items():
            espn_in_window['%s_%s' % (date, lg)] = (
                'error: %s' % v.get('error') if isinstance(v, dict)
                else '%d fixtures' % len(v))

    out = {
        'scan': 'ucl-uel-midweek-window', 'round': 42, 'paper_only': True,
        'generated_utc': NOW_S,
        'window_utc': {'lo': '2026-11-10T00:00:00Z', 'hi': '2026-11-13T00:00:00Z'},
        'dispatch_note': (
            "ROUND-42 EARLY scan requested for men's UCL/UEL midweek Nov 10-13. "
            "ENUMERATION FINDING: zero men's UCL/UEL fixtures exist in the window. "
            "In-world calendar (Gamma + ESPN + UEFA): UCL MD4 = Nov 3-4, UEL MD4 = "
            "Nov 4-5 (both last week), UCL MD5 = Nov 24-25, UEL MD5 = Nov 26; the "
            "Nov 10-12 midweek is the UEFA Nations League international window + "
            "Copa del Rey + women's UWCL + friendlies. No bridge application, no "
            "gates, no entries: clean empty board. PAPER ONLY - no DB writes, no "
            "real orders."),
        'calendar_evidence': {
            'gamma_window_census': {
                'sweeps_run': ['date-volume', 'date-liquidity', 'tag-soccer',
                               'tag-ucl', 'tag-champions-league',
                               'tag-uefa-champions-league', 'tag-europa-league',
                               'tag-uel'],
                'in_window_soccer_events': len(events),
                'events_with_ucl_or_uel_tag': 0,
                'dispatch_query_direct': {
                    'url': '/events?closed=false&start_date_min=2026-11-10T00:00Z&start_date_max=2026-11-13T00:00Z',
                    'result_count': direct_n},
                'open_ucl_matchday_events_all_nov24_25': md5[:18],
            },
            'espn_scoreboard': {
                'in_window': espn_in_window,
                'adjacent_matchdays': {
                    'ucl_20261103': '9 fixtures (Stuttgart-Galatasaray, Bayern-Atletico, Villa-Barcelona, ...)',
                    'ucl_20261104': '9 fixtures (RealMadrid-AEK, Liverpool-Fenerbahce, Betis-Dortmund, ...)',
                    'uel_20261104': '1 fixture (Olympiacos-Rennes)',
                    'uel_20261105': '17 fixtures (Ferencvaros-Milan, Salzburg-Anderlecht, Hoffenheim-Palace, ...)',
                    'ucl_20261124': '9 fixtures (LASK-Bodo, Villa-Galatasaray, Dortmund-Arsenal, ...)',
                    'ucl_20261125': '9 fixtures (Barcelona-Sabah, Villarreal-Slavia, Liverpool-Brugge, ...)',
                    'uel_20261126': '18 fixtures (Bournemouth-Celta, Leverkusen-Dinamo, ...)',
                },
            },
            'external_corroboration': (
                'UEFA.com fixtures + Wikipedia 2026-27 UCL league phase: MD4 = '
                'Nov 3-4, MD5 = Nov 24-25; mid-November = international window '
                '(Nations League). Matches in-world Gamma/ESPN exactly.'),
        },
        'provenance': {
            'understat_pointer': pointer,
            'big5_freshness': {
                'resulted_through': '2026-11-07 (EPL 95, La_liga 114, Serie_A 105, Bundesliga 78, Ligue_1 84 results)',
                'source': 'fotmob-big5 recovery merge (round41/raw/xg_fotmob_big5_merged.json, merged 2026-11-08T02:21Z, pointer re-pointed 02:24Z)',
                'sunday_nov8_gap': '24 domestic fixtures Nov-8 unresulted at scan time -> 1-round stale per club until refresh (list in staleness block)',
            },
            'library_commit': '1a2760bc',
            'selfcheck': 'PASS 10/10 (re-run this session 2026-11-08 ~02:38Z pre-scan)',
            'kappa': {'EPL': 0.126994, 'La_liga': -0.086886, 'Serie_A': -0.0961,
                      'Bundesliga': -0.111525, 'Ligue_1': -0.164953,
                      'nuisance': -0.300105},
            'kappa_path': HOME + '/round31/raw/league_strength_kappa.json',
        },
        'staleness_sunday_nov8': stale,
        'gates': {'variant_spread_max': 0.06, 'worst_edge_min': 0.04,
                  'exec_edge_min': 0.05, 'liq_min': 5000.0,
                  'notes': ('frozen gates unchanged from r40: net>=+5c after '
                            'sports fee 0.05, worst>=+4c, var<=6c, liq>=$5k, '
                            '$250 walk fill ($150 MW), entry .10-.92, haircut, '
                            'news + scoreline concordance, one position per '
                            'fixture, spreads flagged-only; cross-league MW '
                            'ELIGIBLE_DEPRIORITIZED via check_cross_league_mw '
                            '(bridge_present + worst>=+5c) at $150 '
                            'CROSS_LEAGUE_ML_CLASS. NEVER TRIGGERED: no '
                            'eligible fixture reached modeling.')},
        'cross_league_wiring': (
            "loaded and armed (kappa bridge + gates.check_cross_league_mw + "
            "risk_policy.CROSS_LEAGUE_ML_CLASS); zero cross- or same-league "
            "men's UCL/UEL fixtures in window -> wiring recorded, not exercised"),
        'fixtures_in_window_out_of_scope': fixtures,
        'matches': [], 'board_rows': 0, 'board': [],
        'budget': {'max_new_entries_usd': 600, 'used_usd': 0,
                   'soccer_pool_usd': 3000,
                   'ucl_uel_reserve_usd': '>=1100 intact (untouched)'},
        'decision': (
            "ENTER NOTHING - clean empty board. Zero men's UCL/UEL fixtures "
            "exist Nov 10-13 (in-world matchday calendar puts MD5 on Nov 24-26). "
            "Nothing modeled, nothing gated, no candidates. Early-entry/T-24h "
            "machinery not applicable; next genuine UCL/UEL window is MD5."),
    }
    json.dump(out, open(OUT, 'w'), indent=1)
    print('wrote', OUT)
    print('fixtures censused:', len(fixtures), '| matches:', len(out['matches']),
          '| direct dispatch query count:', direct_n, '| md5 events:', len(md5))


if __name__ == '__main__':
    main()
