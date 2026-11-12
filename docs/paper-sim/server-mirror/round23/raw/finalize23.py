"""Round-23 Ligue 1 + rest-of-world finalize: write raw/ligue_rest_scan.json + ligue_rest_candidates.json."""
import json, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round23/raw'
OUT = '/home/ubuntu/paper-sim/round23'

model = json.load(open(RAW + '/ligue_model23.json'))
shortlist = json.load(open(RAW + '/ligue_shortlist23.json'))
books = json.load(open(RAW + '/ligue_books23.json'))
evs = json.load(open(RAW + '/events_window23.json'))
dk = json.load(open(RAW + '/dk_compare23.json'))
espnfx = json.load(open(RAW + '/espn_fixtures23.json'))

NOW = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

# ---- league fixture counts (distinct base fixtures) ----
def base_of(e):
    t = str(e.get('title') or '')
    b = t.split(' - ')[0].strip()
    return b if ' vs. ' in b else None

fixtures = {}
for e in evs:
    tags = e.get('tags') or []
    lg = None
    for tt in ['ligue-1', 'ere', 'primeira-liga', 'brazil-serie-a', 'brazil-serie-b',
               'efl-championship', 'mls', 'scottish-premiership']:
        if tt in tags: lg = tt; break
    if lg is None and e.get('league_hint') == 'liga-mx': lg = 'liga-mx'
    if lg is None: continue
    b = base_of(e)
    if b:
        fixtures.setdefault(lg, {})[b] = True

fixture_counts = {lg: len(v) for lg, v in sorted(fixtures.items())}

# top fixture per league by vol24 for fixtures_detail
fixtures_detail = []
for lg in sorted(fixtures):
    for b in fixtures[lg]:
        vol = sum(e.get('vol24') or 0 for e in evs if base_of(e) == b)
        nmk = sum(len(e.get('markets') or []) for e in evs if base_of(e) == b)
        ko = ''
        for e in evs:
            if base_of(e) == b:
                for m in e['markets']:
                    g = str(m.get('gameStartTime') or '')
                    if g and (not ko or g < ko): ko = g
        fixtures_detail.append({'league': lg, 'title': b, 'vol24': round(vol, 1), 'n_markets': nmk, 'kickoff': ko})
fixtures_detail.sort(key=lambda x: (x['league'], -x['vol24']))

# ---- spread flags (flagged-only) ----
import re
flagged_spreads = []
for base, rec in model['matches'].items():
    for q, m in rec['markets'].items():
        if m['kind'] != 'spread': continue
        mm = re.match(r'^Spread: .+ \((-?\d+(?:\.\d+)?)\)$', q)
        if not mm: continue
        line = float(mm.group(1))
        if abs(line) > 2.5: continue
        if (m.get('liq') or 0) < 5000: continue
        mid = m.get('mid')
        if mid is None: continue
        flagged_spreads.append({
            'match': base, 'league': 'Ligue_1', 'kickoff': rec['kickoff'], 'kind': 'spread',
            'q': q, 'id': m['id'], 'liq': m['liq'], 'side0': q[len('Spread: '):].split(' (')[0],
            'line': line, 'mid0': mid, 'q0_med': m['p0_med'], 'var_spread': m['var_spread'],
            'gap0': round(m['p0_med'] - mid, 4),
            'policy': 'FLAGGED-ONLY (blowout-tail rule; not a candidate)'})

# ---- near misses from books (core-pass rows that failed exec gates) ----
near_misses = []
for b in books:
    side = b['side']
    ask = b['exec_ask0'] if side == 0 else b['exec_ask1']
    exec_edge = b['edge0_exec'] if side == 0 else b['edge1_exec']
    worst_edge = b['worst_var_edge0'] if side == 0 else b['worst_var_edge1']
    filled = (b['books'].get('tok%d' % side, {}).get('ask', {}) or {}).get('filled', False)
    qs = b['qs_variants']
    q_side_med = b['q0_med'] if side == 0 else round(1 - b['q0_med'], 4)
    worst_q = round(min(qs), 4) if side == 0 else round(max(qs), 4)
    outs = b.get('outcomes') if isinstance(b.get('outcomes'), list) else None
    fails = []
    if not filled: fails.append('book did not fill $250')
    if exec_edge is None or exec_edge < 0.05: fails.append('exec edge %s < +5c' % exec_edge)
    if worst_edge is None or worst_edge < 0.04: fails.append('worst-variant edge %s < +4c' % worst_edge)
    if b['var_spread'] > 0.06: fails.append('var spread %.4f > 6c' % b['var_spread'])
    near_misses.append({
        'match': b['match'], 'league': 'Ligue_1', 'kickoff': b['kickoff'], 'question': b['q'],
        'kind': b['kind'], 'side_index': side,
        'liq': b['liq'], 'entry_ask_250': ask, 'model_median_side': q_side_med,
        'worst_variant_side': worst_q, 'var_spread': b['var_spread'],
        'exec_edge': exec_edge, 'worst_variant_edge': worst_edge, 'filled_250': filled,
        'fail': '; '.join(fails) if fails else 'PASSES ALL GATES'})
near_misses.sort(key=lambda x: -(x['exec_edge'] or -1))

# ---- top var-fail near-misses (documented, no books) ----
var_fail_near = [s for s in shortlist if not s['core_pass']]
var_fail_near.sort(key=lambda s: -s['mid_edge'])
documented_var_fail = []
for s in var_fail_near[:8]:
    documented_var_fail.append({
        'match': s['match'], 'question': s['q'], 'kind': s['kind'], 'liq': s['liq'],
        'mid': s['mid'], 'side': 'over/yes' if s['side'] == 0 else 'under/no',
        'mid_edge': s['mid_edge'], 'var_spread': s['var_spread'],
        'fail': 'var spread %.4f > 6c' % s['var_spread']})

# ---- non-big5 liquid list ----
non_big5_liquid = []
for lg in ['ere', 'primeira-liga', 'scottish-premiership', 'liga-mx', 'brazil-serie-a', 'brazil-serie-b', 'efl-championship', 'mls']:
    for b in fixtures.get(lg, {}):
        vol = sum(e.get('vol24') or 0 for e in evs if base_of(e) == b)
        mkliq = []
        for e in evs:
            if base_of(e) == b:
                mkliq += [m.get('liq') for m in e['markets'] if m.get('liq')]
        ko = ''
        for e in evs:
            if base_of(e) == b:
                for m in e['markets']:
                    g = str(m.get('gameStartTime') or '')
                    if g and (not ko or g < ko): ko = g
        non_big5_liquid.append({'league': lg, 'title': b, 'vol24': round(vol, 1),
                                'top_market_liq': round(max(mkliq), 1) if mkliq else None, 'kickoff': ko[:16]})
non_big5_liquid.sort(key=lambda x: -x['vol24'])

# ---- devig check summary ----
gaps = [abs(o['gap_pm_minus_dk']) for o in dk['ou'] if o['gap_pm_minus_dk'] is not None]
devig_summary = {
    'source': 'DraftKings via ESPN scoreboard (totals close odds, 2-way devig)',
    'n_ou_compared': len(gaps), 'max_abs_gap_c': round(max(gaps) * 100, 1) if gaps else None,
    'sourced_flags_ge15c': [],
    'note': 'PM O/U mids agree with DK devig within %.1fc across all %d compared games (all leagues); no ML side exceeds DK vigged implied by 15c either. Zero sourced >=15c gaps.' % (max(gaps) * 100 if gaps else 0, len(gaps))}

# ---- big5 dk context (Ligue 1) ----
ligue_ou = [{'match': o['match'], 'line': o['line'], 'dk_over_devig': o['dk_over_devig'],
             'pm_over_mid': o['pm_over_mid'], 'gap_c': round(o['gap_pm_minus_dk'] * 100, 1)} for o in dk['ou'] if o['league'] == 'ligue-1']
model_vs_dk = []
for base, rec in model['matches'].items():
    for o in ligue_ou:
        if o['match'] == base:
            m = rec['markets'].get('%s: O/U %s' % (base, o['line']))
            if m:
                model_vs_dk.append({'match': base, 'line': o['line'], 'model_over_med': m['p0_med'],
                                    'dk_over_devig': o['dk_over_devig'], 'pm_mid': m['mid'],
                                    'model_minus_dk_c': round((m['p0_med'] - o['dk_over_devig']) * 100, 1)})

# ---- scan file ----
scan = {
 'generated_utc': NOW, 'scan': 'ligue_rest', 'round': 23, 'paper_only': True,
 'window': ['2026-10-30T00:00:00Z', '2026-11-03T03:00:00Z'],
 'window_note': 'Fri Oct 30 - Mon Nov 2 slates incl. Monday-night spillover',
 'xg_file': 'round23/raw/xg_understat_ligue_23.json',
 'xg_base': model['xg_base'],
 'variants': model['variants'],
 'match_winner': 'SUSPENDED', 'spread_policy': 'ALL spreads flagged-only (blowout-tail rule)',
 'gates': model['gates'],
 'gamma_coverage_note': "Eredivisie per-match markets exist on Polymarket under tag_slug 'ere' (the 'eredivisie' tag is dead/unused). Liga MX events carry generic tags and were added via public-search team sweeps. MLS covered by us-sports sibling; listed for completeness only.",
 'matches': model['matches'],
 'kind_counts': {k: sum(1 for r in model['matches'].values() for m in r['markets'].values() if m['kind'] == k)
                 for k in ['total', 'btts', 'teamtotal', 'spread']},
 'flagged_not_recommended': flagged_spreads,
 'near_miss_books': near_misses,
 'var_fail_near_documented': documented_var_fail,
 'fixture_counts_by_league': fixture_counts,
 'fixtures_detail': fixtures_detail,
 'non_big5_liquid': non_big5_liquid[:24],
 'non_big5_devig_check': devig_summary,
 'non_big5_sourced_flags': [],
 'big5_dk_context': {'ligue_1_ou_devig': ligue_ou, 'model_vs_dk': model_vs_dk,
   'note': 'PM mids track DK devig within 1.5c on every Ligue 1 total - all model edges are model-vs-consensus disagreements, not PM mispricings. Model is higher than DK on goals for Troyes-Le Mans (+8.6c), Lorient-Brest (+7.9c), PFC-Monaco (+5.9c), Nice-Rennes (+5.6c); lower on PSG game (-11.8c, var spread 20c+ blocks entry, r18 precedent: DK sided with PM).'},
}
json.dump(scan, open(RAW + '/ligue_rest_scan.json', 'w'), indent=1)

# ---- candidates file ----
passing = [n for n in near_misses if n['fail'] == 'PASSES ALL GATES']
decision = 'TRADE' if passing else 'PASS'
fragility = {
 'Le Havre AC vs. Paris Saint-Germain FC': 'PSG rotation expected at last-place Le Havre (YSScores XI: Digne, Joao Neves, Akliouch, Zabarnyi, L.Hernandez; Mayulu/Godts recent scorers; thestatszone preview) - rotated XI is exactly why PSG-dependent markets carry 20c+ variant spreads; model under-lean vs market mirrors r18 PSG-Lyon where DK agreed with PM (model error risk, not mispricing).',
 'OGC Nice vs. Stade Rennais FC 1901': 'Comps probables not published at scan time (T-2d); Nice attack xG 1.11/g season vs 1.19 last-5 - over-1.5 edge depends on home boost; recheck lineup news (24-48h pre-KO) before any entry.',
 'ES Troyes AC vs. Le Mans FC': 'Both newly promoted (no 2025/26 Ligue 1 prior -> league-average shrink). Troyes player underwent exams after violent head clash Sat Oct 24 (lest-eclair report); possible absence. Model edge over 1.5 (+6.5c mid) is the largest in slate but exec book only +4.5c.',
 'Lille OSC vs. Racing Club de Lens': 'Derby; comps not published at scan time. Lille over-1.5 exec edge only +2.5c - not close to gates.',
}
candidates = {
 'generated_utc': NOW,
 'window': '2026-10-30 .. 2026-11-03 (Fri-Mon)',
 'decision': decision,
 'ranked': [],
 'reason': ('No Ligue 1 market passed the full gate set. Best exec was OGC Nice O/U 1.5 (Over) at '
   '+6.7c on a $250 VWAP ask (liq $7.4k, var 5.5c) but worst-variant edge only +2.6c < +4c; '
   'ES Troyes AC-Le Mans O/U 1.5 Over reached +4.5c exec / +2.5c worst (< +5c/+4c). All other core '
   'entries <= +3.0c exec. PSG-game under-leans are 11-22c mid edges but variant spreads 15-25c '
   '(PSG last-5 xG 2.73/g destabilizes attack rating; r18 precedent: DK sided with PM, model error). '
   'match_winner SUSPENDED; spreads flagged-only. Non-Big-5: PM agrees with DK devig within 1.5c on all '
   '28 O/U comparisons; zero sourced >=15c gaps.'),
 'near_misses': near_misses,
 'var_fail_near_documented': documented_var_fail,
 'flagged_spreads': flagged_spreads,
 'lineup_fragility': fragility,
 'fixture_counts_by_league': fixture_counts,
 'non_big5_liquid_ml': non_big5_liquid[:12],
 'non_big5_sourced_flags': [],
 'big5_dk_context': scan['big5_dk_context'],
}
json.dump(candidates, open(OUT + '/ligue_rest_candidates.json', 'w'), indent=1)

print('decision:', decision, '| passing:', len(passing))
print('fixture counts:', fixture_counts)
print('flagged spreads:', len(flagged_spreads))
for f in flagged_spreads:
    print('  %-58s mid=%.3f model=%.3f gap=%+.3f liq=%.0f' % (f['q'][:58], f['mid0'], f['q0_med'], f['gap0'], f['liq']))
print('near misses:')
for n in near_misses:
    print('  %-58s exec=%+0.4f worst=%+0.4f var=%.4f  %s' % (n['question'][:58], n['exec_edge'], n['worst_variant_edge'], n['var_spread'], n['fail'][:60]))
print('model vs dk:')
for r in model_vs_dk:
    print('  %-46s O/U %s model=%.3f dk=%.3f pm=%.3f diff=%+.1fc' % (r['match'][:46], r['line'], r['model_over_med'], r['dk_over_devig'], r['pm_mid'], r['model_minus_dk_c']))
print('saved ligue_rest_scan.json + ligue_rest_candidates.json')
