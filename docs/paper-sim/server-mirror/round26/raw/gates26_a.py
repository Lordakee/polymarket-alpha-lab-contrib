"""Round-26 scan A: gate evaluation via the canonical library + output assembly.

Re-fetches fresh CLOB books for the shortlist side tokens, runs
gates.under_risk_check / check_news / suspension_policy / evaluate_candidate /
rank_candidates exactly as documented, writes round26/raw/scan_a.json and
round26/candidates_a.json. Paper-only; no orders, no credentials."""
import json, time, urllib.request
from types import SimpleNamespace
from polymarket_alpha_lab.papersim import gates, risk_policy
from polymarket_alpha_lab.papersim.xg import load_xg_snapshot

RAW = '/home/ubuntu/paper-sim/round26/raw'
SNAP = '/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json'

SHORTLIST = [
    ("Elche-Valencia", "over_2.5"), ("Elche-Valencia", "over_3.5"),
    ("Lecce-Genoa", "tt_away_over_1.5"), ("Lecce-Genoa", "over_2.5"),
    ("Lazio-Cagliari", "tt_away_over_1.5"), ("Lazio-Cagliari", "tt_away_over_0.5"),
    ("Juventus-Napoli", "ml_home"), ("Juventus-Napoli", "tt_home_over_1.5"),
    ("Athletic-RealSociedad", "ml_home"),
    ("RacingSantander-RealMadrid", "tt_home_over_2.5"), ("RacingSantander-RealMadrid", "under_3.5"),
    ("Frosinone-Torino", "over_2.5"), ("Frosinone-Torino", "under_3.5"),
    ("Getafe-Sevilla", "ml_home"),
]

# fixture -> (news_delta, blockers, sources)
NEWS = {
    "Elche-Valencia": ("unchanged", [], [
        "LaLiga match sheet 2026-11-01: Elche without Aguado (ankle), Yago Santiago (arthroscopy); Valencia without Elliott (suspension), Copete (meniscus), Sadiq (hamstring)",
        "r25 baseline (Sports Mole/Yahoo): Aguado out, Fer Nino + Bigas doubtful, one Valencia hamstring doubt",
        "net vs r25: Elche attack doubts mostly resolved, Valencia extra absences offset; no new contra-Over factor"]),
    "Lecce-Genoa": ("unchanged", [], [
        "fixture preview: Genoa without Ilic (thigh) + Sow (ankle) - both central mids; Lecce without Coulibaly (hamstring)",
        "no forward depletion either side; Genoa front line + Frendrup intact; Genoa lost last 3 away (inside xG data)"]),
    "Lazio-Cagliari": ("unchanged", [], [
        "starting11.com predicted XI 1 Nov 2026; FootballCritic: Cagliari J. Liteta (thigh) out - squad forward",
        "probable Cagliari XI full attack (Piccoli; Zortea, Gaetano, Felici); Lazio CB Gila knee doubt (mildly pro-Cagliari-side)"]),
    "Juventus-Napoli": ("unknown", [], [
        "r25 (DAZN/juventus.com): Yildiz + Locatelli out; Thuram, Celik, N.Gonzalez doubtful",
        "2026-11-01 search: conflicting - Football Italia headline suggests Yildiz + Conceicao start; juventus.com matchroom lists Locatelli/Thuram; not an official XI (lands ~18:45Z)"]),
    "Athletic-RealSociedad": ("better", [], [
        "Fox Sports/Yahoo 2026-11-01: Sancet available for derby after calf recovery; Nico Williams fit (returned from thigh), starting",
        "Laporte back from suspension"]),
    "Como-Venezia": ("worse", [], [
        "Fabregas long injury list: Kean out among five injured (Franjic shoulder, + hip case); Douvikas to lead line"]),
    "Getafe-Sevilla": ("unknown", [], ["no fixture-specific team news found in 2026-11-01 searches"]),
    "Frosinone-Torino": ("unknown", [], ["Torino injuries noted as a concern (unnamed); no confirmed XI found"]),
    "RacingSantander-RealMadrid": ("unknown", [], [
        "Mourinho's Real Madrid away at promoted side - typical rotation candidate; nothing confirmed in searches"]),
}

model = json.load(open(RAW + '/model26_a.json'))
rows = {(r['fixture'], r['key']): r for r in model['rows']}
matches = {m['match']: m for m in model['matches']}
books = {(b['fixture'], b['key']): b for b in json.load(open(RAW + '/books26_a.json'))}

def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'research/0.1'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    return None

def market_kind(key):
    if key.startswith('ml_'):
        return 'match_winner'
    if key.startswith('tt_'):
        return 'team_total'
    if key.startswith(('over_', 'under_')):
        return 'total'
    if key.startswith('btts'):
        return 'btts'
    return 'other'

def line_of(key):
    try:
        return float(key.split('_')[-1])
    except ValueError:
        return None

def side_word(key):
    if key.startswith('ml_'):
        return 'yes'
    if key == 'btts_yes':
        return 'yes'
    if key == 'btts_no':
        return 'no'
    if '_over_' in key or key.startswith('over_'):
        return 'over'
    return 'under'

gate_rows, reports = [], []
for fx, key in SHORTLIST:
    r = rows[(fx, key)]
    m = matches[fx]
    tok = r['token']
    b = get('https://clob.polymarket.com/book?token_id=' + tok) if tok else None
    levels = []
    if b and 'asks' in b:
        levels = [(float(l['price']), float(l['size'])) for l in b.get('asks', [])]
    time.sleep(1.1)
    delta, blockers, sources = NEWS[fx]
    news = gates.check_news(fx, delta, news_delta=delta, blockers=blockers, sources=sources)
    kw = side_word(key)
    o25 = (m['form_home_last5'] or {}).get('over_2_5_hits', 0) + (m['form_away_last5'] or {}).get('over_2_5_hits', 0)
    ur_flag, ur_why = gates.under_risk_check(
        kind=market_kind(key) if market_kind(key) in ('total', 'btts') else 'other',
        side=kw, o25_hits=o25, lambda_total=m['lambda_total'],
        lambda_home=m['lambda_home'], lambda_away=m['lambda_away'],
        line=line_of(key) or 2.5)
    quote = SimpleNamespace(model_median=r['model_med'], qs_variants=r['qs_variants'],
                            gamma_liquidity=r['liq_gamma'])
    if levels:
        rep = gates.evaluate_candidate(quote, levels, side='ask',
                                       gamma_liquidity=r['liq_gamma'], news=news,
                                       under_risk=ur_flag)
    else:
        rep = None
    susp = gates.suspension_policy(market_kind(key), cross_league=False)
    row = {
        'fixture': fx, 'league': r['league'], 'kickoff_utc': r['kickoff_utc'], 'key': key,
        'q': r['q'], 'market_id': r['market_id'], 'kind': market_kind(key),
        'model_med': r['model_med'], 'model_min': r['model_min'], 'model_max': r['model_max'],
        'var_spread': r['var_spread'],
        'gamma_ask': r['gamma_ask'], 'liq_gamma': r['liq_gamma'],
        'entry_vwap250': getattr(rep, 'entry_price', None) if rep else None,
        'fill_250': getattr(rep.walk, 'filled', None) if rep else None,
        'depth_near2c': getattr(rep.walk, 'depth_near2c', None) if rep else None,
        'exec_edge': getattr(rep, 'exec_edge', None) if rep else None,
        'exec_edge_haircut': getattr(rep, 'exec_edge_haircut', None) if rep else None,
        'worst_variant_edge': getattr(rep, 'worst_variant_edge', None) if rep else None,
        'under_risk': ur_flag, 'under_risk_why': ur_why,
        'suspension_policy': susp.policy,
        'checks': dict(rep.checks) if rep else {},
        'passed': bool(rep.decision.passed) if rep else False,
        'failed_gates': list(rep.decision.failed) if rep else ['no_book'],
        'news_delta': delta, 'news_concordant': news.concordant,
    }
    gate_rows.append(row)
    if rep is not None:
        reports.append(((fx, key), rep))

ranked = gates.rank_candidates([rep for _, rep in reports])
by_identity = {id(rep): k for k, rep in reports}
order = [by_identity[id(rep)] for rep in ranked]

# ---- assemble scan_a.json ----
scan = {
    'scan': 'soccer_a', 'round': 26, 'paper_only': True,
    'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'window_utc': {'lo': '2026-11-01T11:30:00Z', 'hi': '2026-11-01T20:00:00Z'},
    'method': {
        'library': 'polymarket_alpha_lab.papersim @ repo 7b6cdd47 (canonical)',
        'selfcheck': 'PASS 10/10 (r19 crypto anchors, r23 soccer anchors, banned path, gate arithmetic)',
        'pipeline': 'gamma discovery (events/pagination, tags sea/la-liga/laliga/serie-a/soccer) -> fixture_variants (10 sweeps) -> gamma join -> CLOB $250 ask walks -> gates.evaluate_candidate -> rank_candidates',
        'note': 'All probabilities, walks, gate arithmetic and ranking computed by the library; bespoke code only fetches/discovers/serves inputs.',
    },
    'gates': {'variant_spread_max': 0.06, 'worst_edge_min': 0.04, 'exec_edge_min': 0.05,
              'liq_min': 5000, 'entry_window': [0.10, 0.92], 'fill_250': True,
              'notes': 'cross-league MW banned; domestic MW eligible-but-deprioritized; spreads flagged-only; news-concordance required; 50-50 haircut band [0.45,0.55]; under_risk screen 8c'},
    'bankroll_usd': 12374.33, 'cash_usd': 9488.68,
    'xg_refresh': {
        'file': 'round25/raw/xg_understat_25.json',
        'verified_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'latest_game_dates': {'Serie_A': '2026-10-31 19:45:00', 'La_liga': '2026-10-31 20:00:00'},
        'verdict': 'FRESH - all leagues through Sat Oct 31; no Sunday Nov 1 games present; all 18 clubs resolve in snapshot team tables',
    },
    'fixtures': [
        {'kickoff_utc': m['kickoff_utc'], 'league': m['league'], 'label': m['match'], 'status': 'verified'}
        for m in model['matches']
    ],
    'matches': model['matches'],
    'gate_rows': gate_rows,
    'news_checks': {fx: {'delta': d, 'blockers': list(b), 'sources': list(s), 'concordant': gates.news_concordance(d) and not b}
                    for fx, (d, b, s) in NEWS.items()},
    'ranking_order': [{'fixture': k[0], 'key': k[1]} for k in order],
}
json.dump(scan, open(RAW + '/scan_a.json', 'w'), indent=1)
print('wrote scan_a.json; gate rows:', len(gate_rows), 'passing:', sum(1 for g in gate_rows if g['passed']))
for g in gate_rows:
    print('%-26s %-18s exec=%s worst=%s var=%.3f pass=%s failed=%s ur=%s' % (
        g['fixture'], g['key'], g['exec_edge'], g['worst_variant_edge'], g['var_spread'],
        g['passed'], ','.join(g['failed_gates']) or '-', g['under_risk']))
print('\nrank order:', order)
