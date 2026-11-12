"""Round-15 final gate + ranking -> soccer_candidates.json.

Gates (coordinator round-15):
- executable edge >= +5c (CLOB $250 VWAP ask), entry 0.10-0.92
- variant spread <= 8c; gamma liquidity >= $5k; book fills $250
- 50-50 haircut: side model median in [0.45,0.55] -> edge halved before bar
- NEW strictness after Friday 1-1 double loss (ou_over 7W-4L softening):
  * under_risk flag for Over totals / BTTS-Yes when recent form is under-trending
    (combined last-5 O2.5 hits <= 3/10) or model goal expectation too low for the line.
    under_risk candidates need edge >= +8c AND all-variant agreement, else dropped.
  * highest-agreement requirement: worst-variant edge must be > 0 for every qualifier.
- No new adds on held fixtures at all this round (correlation rule; round-14 already
  treated BTTS-Yes on O2.5-held as correlated). Recorded under excluded_held_correlated.
- match_winner suspended (never shortlisted).
"""
import json, time

RAW = '/home/ubuntu/paper-sim/round15/raw'
rows = json.load(open(RAW + '/shortlist_books.json'))

def entry_ok(p): return p is not None and 0.10 <= p <= 0.92

def haircut(q_med):
    return 0.5 if 0.45 <= q_med <= 0.55 else 1.0

def under_risk_check(r, side_label, side_med, kind):
    """Extra-strict low-scoring-risk screen for Over totals and BTTS-Yes."""
    if kind not in ('total', 'btts'): return (False, '')
    is_over = kind == 'total' and str(side_label).lower().startswith('over')
    is_yes = kind == 'btts' and str(side_label).lower() == 'yes'
    if not (is_over or is_yes): return (False, '')
    fh = r.get('form_home') or {}
    fa = r.get('form_away') or {}
    o25 = (fh.get('o25_hits') or 0) + (fa.get('o25_hits') or 0)
    lt = r.get('lambda_total') or 0
    lh = r.get('lambda_home') or 0
    la = r.get('lambda_away') or 0
    reasons = []
    if is_over:
        line = 2.5
        try:
            import re as _re
            mm = _re.search(r'O/U (\d+(?:\.\d+)?)', r.get('q') or '')
            if mm: line = float(mm.group(1))
        except Exception:
            pass
        # model expectation should clear the line by a margin
        need = {1.5: 2.3, 2.5: 2.75, 3.5: 3.4, 4.5: 4.3}.get(line, line + 0.4)
        if lt < need: reasons.append('lambda_total %.2f < %.2f for O%.1f' % (lt, need, line))
        if o25 <= 3: reasons.append('combined last-5 O2.5 hits %d/10' % o25)
    if is_yes:
        if min(lh, la) < 0.75: reasons.append('min lambda %.2f < 0.75' % min(lh, la))
        if o25 <= 3: reasons.append('combined last-5 O2.5 hits %d/10' % o25)
    return (len(reasons) > 0, '; '.join(reasons))

cands = []
excluded_risk = []
for r in rows:
    q0 = r['q0_med']
    a0 = r['exec_ask0']; a1 = r['exec_ask1']
    e0 = r['edge0_exec']; e1 = r['edge1_exec']
    best = None
    for side_kind, side_label, ask, edge in (('side0', r['side0'], a0, e0), ('side1', r['side1'], a1, e1)):
        if edge is None or ask is None: continue
        side_med = q0 if side_kind == 'side0' else 1 - q0
        h = haircut(side_med)
        eh = round(edge * h, 4)
        # worst-variant agreement for this side
        side_worst = (r['q0_min'] if side_kind == 'side0' else 1 - r['q0_max'])
        edge_worst = round(side_worst - ask, 4)
        risk, risk_why = under_risk_check(r, side_label, side_med, r['kind'])
        bar = 0.08 if risk else 0.05
        ok = eh >= bar and entry_ok(ask)
        if ok and edge_worst <= 0:
            ok = False; risk_why += ' | worst-variant edge %.4f <= 0 (agreement fail)' % edge_worst
        cand = {'match': r['match'], 'league': r['league'], 'kickoff': r['kickoff'],
                'question': r['q'], 'side': side_label, 'entry_ask': ask,
                'model_median': round(side_med, 4),
                'edge_exec': round(edge, 4), 'haircut': h, 'edge_exec_haircut': eh,
                'edge_worst_variant': edge_worst,
                'under_risk': risk, 'under_risk_why': risk_why or None,
                'var_spread': round(r['var_spread'], 4), 'liq_gamma': r['liq'],
                'kind': r['kind'], 'mid': r['mid'],
                'lambda_total': r.get('lambda_total'),
                'form_home': r.get('form_home'), 'form_away': r.get('form_away'),
                'held_fixture_other_type': r.get('held_fixture_other_type', False),
                'market_id': r['id']}
        if ok:
            if best is None or eh > best['edge_exec_haircut']: best = cand
        else:
            if eh >= 0.03:  # near-miss record
                excluded_risk.append(dict(cand, fail_reason='gate: %s (bar %.2f)' % (risk_why or 'edge<haircut bar', bar)))
    if best is None: continue
    toks = r['tokens']
    if isinstance(toks, str): toks = json.loads(toks)
    tok_i = 0 if best['side'] == r['side0'] else 1
    b = r['books'].get('tok%d' % tok_i, {})
    askinfo = b.get('ask', {}) or {}
    bidinfo = (r['books'].get('tok%d' % (1 - tok_i), {}).get('bid', {}) or {})
    if not askinfo.get('filled'): continue
    best['exit_bid_ref'] = bidinfo.get('best')
    best['book_depth_near2c'] = askinfo.get('depth_near2c')
    best['book_filled_250'] = askinfo.get('filled')
    best['token_id'] = toks[tok_i] if tok_i < len(toks) else None
    cands.append(best)

held_all = True  # this round: no adds on held fixtures at all
final = []
excl_held = []
for c in cands:
    if c['held_fixture_other_type']:
        excl_held.append(dict(c, fail_reason='held-fixture correlation rule (no new adds on held fixtures)'))
    else:
        final.append(c)

# rank: all-variant agreement margin first, then haircut edge
final.sort(key=lambda c: (-c['edge_worst_variant'], -c['edge_exec_haircut']))

TYPE_NOTE = {'total': 'O/U total', 'btts': 'BTTS', 'spread': 'spread'}
ranked = []
for c in final[:2]:
    c2 = dict(c)
    c2['type_note'] = TYPE_NOTE.get(c['kind'], c['kind'])
    c2['sizing'] = '$250'
    ranked.append(c2)

out = {
 'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
 'window': '2026-10-24..2026-10-27 (weekend+Monday)',
 'bankroll_context': 'weekend book $1,500 remaining; max 2 new x $250',
 'rules': {
   'match_winner': 'SUSPENDED per coordinator',
   'eligible_types': ['O/U totals both sides', 'BTTS both sides', 'handicap/spread both sides'],
   'gates': 'edge>=+5c exec (8c if under_risk), entry .10-.92, var spread<=8c, liq>=$5k, book fills $250, 50-50 haircut, all-variant agreement (worst-variant edge>0)',
   'held_fixtures': 'no new adds on held fixtures (correlation rule)',
 },
 'all_passing': final,
 'ranked': ranked,
 'excluded_held_correlated': excl_held,
 'near_misses': excluded_risk,
 'record': {'ou_over': '7W-4L (63.6%) settled; Friday double loss IPS-FOR 1-1, ALA-MAL 1-1'},
}
json.dump(out, open('/home/ubuntu/paper-sim/round15/soccer_candidates.json', 'w'), indent=1)
print('all_passing=%d ranked=%d excluded_held=%d near_miss=%d' % (len(final), len(ranked), len(excl_held), len(excluded_risk)))
for c in ranked:
    print('RANK %s | %s %s | entry %s edge %s (h=%s worst-variant %s) risk=%s liq=%s var=%s' % (
        c['side'], c['match'], c['question'], c['entry_ask'], c['edge_exec_haircut'], c['haircut'],
        c['edge_worst_variant'], c['under_risk'], c['liq_gamma'], c['var_spread']))
print('saved soccer_candidates.json')
