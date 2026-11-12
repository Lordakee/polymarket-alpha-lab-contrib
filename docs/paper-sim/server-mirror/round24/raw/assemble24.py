"""Round-24 EPL candidates assembler: verify verdicts + delta candidate + rechecks.
Writes /home/ubuntu/paper-sim/round24/epl_candidates.json (the ONLY file outside raw/)."""
import json, time

RAW = '/home/ubuntu/paper-sim/round24/raw'
OUT = '/home/ubuntu/paper-sim/round24'
scan = json.load(open(RAW + '/epl_scan.json'))
model = json.load(open(RAW + '/epl_model24.json'))
NOW = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

n_spread = sum(1 for m, v in model['matches'].items() for q, mm in v['markets'].items() if mm['kind'] == 'spread')

cand = {
 'generated_utc': NOW,
 'round': '24-EPL-verify+delta',
 'window': '2026-10-30 .. 2026-11-02 (all 10 EPL fixtures, Sat 12:30Z -> Mon 20:00Z)',
 'paper_only': True, 'report_only': True,
 'bankroll_context': ('paper sim; coordinator-maintained ledger (r23 context: bankroll 10780.73, '
   'cash 7045.33); this round adds at most 1 x $250 paper entry on top of held #48/#49'),
 'rules': {
   'match_winner': 'domestic ELIGIBLE under tightened gates but DEPRIORITIZED - none gated this round',
   'cross_league_match_winner': 'BANNED (structural defect, review/FIXES.md) - not used',
   'spreads': 'flagged-only (count this window: %d, report-only)' % n_spread,
   'eligible_kinds': ['O/U totals both sides', 'BTTS both sides', 'team totals both directions'],
   'gates': 'var<=6c; worst-variant exec >= +4c; median exec >= +5c (CLOB $250-VWAP ask); '
            'liq >= $5k; entry .10-.92; book fills $250; max 1 new candidate this round'},
 'model_provenance': ('round-23 10-variant xG-Poisson probabilities UNCHANGED (xG base through '
   '2026-10-25; no EPL fixtures Oct 26-29 -> no refresh). Rebuilt in round24/raw/model24.py; '
   'lambda validation 10/10 exact vs round-23 fixtures; per-market qs_variants identical for all '
   'archived r23 markets checked (BOU-LEE O2.5 0.6096/[0.5714,0.6323], BRE-FOR O2.5 0.6342, '
   'HUL-IPS O2.5 0.6130, CHE-MUN O3.5 0.4514).'),

 'verification': {
  '#48': {
    'position': 'Brentford-Forest O2.5 Over $250 @ 0.560 (mkt 5856164, Sat 15:00Z)',
    'verdict': 'HOLD',
    'exit_condition_checked': 'EXIT-candidate iff (Schade OUT) AND (Damsgaard OUT) AND (Forest Delap OUT)',
    'presser_evidence': [
      'Brentford (Keith Andrews, Fri presser via BBC): Schade BACK IN CONTENTION after shoulder issue - "a really good boost", could be involved',
      'Damsgaard (ankle, Denmark duty) and Collins (calf) SET TO BE INVOLVED again after recovery (BBC, Andrews presser)',
      'Forest (Oliver Glasner, presser ~19h pre-match): Delap FIT and available (building match sharpness, no injury); the doubt is Dan Ndoye (muscle fatigue); Igor Jesus remains OUT, Gibbs-White doubt (carried from r23)',
      'sources: bbc.com (Andrews presser; Glasner presser ck1l39602p38o), sports.yahoo.com (Schade availability), sportsmole.co.uk (Ndoye doubt)'],
    'exit_condition_met': False,
    'current_book': scan['held_verification_books']['5856164'],
    'note': 'ask unchanged 0.560, exit bid 0.54 (-2.0c vs entry, within spread); model edge intact '
            '(exec +7.4c, worst +6.3c); fragility improved vs r23 (both Brentford doubtful AMs returned); depth $16,076 near 2c'},
  '#49': {
    'position': 'Hull-Ipswich O2.5 Over $250 @ 0.5274 (mkt 5856548, Sat 15:00Z)',
    'verdict': 'HOLD',
    'exit_condition_checked': 'EXIT iff Ipswich main scorer OUT',
    'presser_evidence': [
      'Ipswich: NO main-scorer-out news; only Lukic (groin, carried from r23) unavailable; Jack Clarke fit and pushing to start (BBC preview); attack otherwise intact per r23 baseline (only mids Lukic+Taylor out)',
      'Hull (Sergej Jakirovic, BBC presser ~22h pre-match): "no fresh injury concerns"; Nobel Mendy RETURNING to contention (defense reinforcement vs r23 doubt)',
      'Hull absentee list unchanged where it matters: Ansah (back), Akintola, Matazo (ACL), Targett, Gyabi, Hughes, Dowell; Cho/Vaz not flagged out in Friday reports - Hull still field recognisable forwards',
      'sources: bbc.com (Jakirovic presser cw054dqvnvzgo), sportsmole.co.uk preview 607868, bbc.co.uk (Clarke start debate)'],
    'exit_condition_met': False,
    'current_book': scan['held_verification_books']['5856548'],
    'note': 'ask 0.520 (vs 0.5274 entry), exit bid 0.51 (-1.7c); model edge WIDER now (exec +9.3c vs +8.6c at entry); split fragility unchanged-or-better (Mendy back bolsters leaky Hull DEF, which feeds the Ipswich side of the total); depth $13,873 near 2c'}},

 'chemun_o35_recheck': {
   'r23_decision': 'SKIPPED - HIGH fragility (Palmer susp, Pedro/Bynoe-Gittens/Emegha out, James out; Sesko out, Rashford 75% doubt)',
   'news_delta': 'WORSE, not better: Rashford now officially SIDELINED (hip; missed Como + Bournemouth games; listed out in official ManUtd.com match preview alongside Mainoo, Sesko, Ugarte). Chelsea absences unchanged.',
   'market_reprice': 'ask 0.39 (r23) -> 0.370 now: market now priced BELOW the model worst-case variant (0.4306) by 6.1c, i.e. even the most pessimistic of the 10 model variants calls the Over cheap. Gates pass on paper (exec +8.1c, worst +6.1c, var 3.6c).',
   'decision': 'STILL NO ENTRY - news-model concurrence fails: the unchanged model carries full-strength attack ratings for BOTH sides while both attacks are now more depleted than at r23 (Utd first-choice ST + Rashford out). The market discount is news-driven and credible. Revisit only if lineups show attack-minded replacements and the price stays dislocated.',
   'row': scan['chemun_o35_recheck']},

 'delta_scan': {
   'summary': '16 market-sides pass all gates on fresh books vs the unchanged r23 model. After news overlay: CHE-MUN family (5 passers incl MU O1.5 team total +13.3c exec) blocked by news-model conflict (both attacks depleted; Rashford out); TOT-CP Palace O0.5/O1.5 team totals (+8.8c/+11.7c) blocked by Palace injury crisis (Sarr out, several doubts) - model overstates Palace; BRE-FOR O3.5/O4.5 and HUL-IPS O4.5/Hull O0.5 are same-fixture adds on held positions (goal-correlation concentration, deprioritized); COV-SUN Coventry O0.5 passes gates but real depth near 2c only $232 (too thin for the $5k-real-depth intent). COV-SUN O2.5 fails worst again (+3.5c < +4c; ask moved only 0.4891->0.4887).',
   'new_candidates': [{
     'match': 'AFC Bournemouth vs. Leeds United FC', 'kickoff': '2026-10-31 15:00:00+00',
     'kind': 'teamtotal', 'team': 'AFC Bournemouth', 'line': 1.5,
     'question': 'AFC Bournemouth vs. Leeds United FC: AFC Bournemouth O/U 1.5',
     'market_id': '5856446',
     'side': 'Over/Yes(side0)', 'entry_ask_vwap250': 0.4798, 'sizing': '$250 paper',
     'model_median': 0.5634, 'model_range': [0.5516, 0.6077], 'var_spread': 0.0561,
     'edge_exec': 0.0836, 'edge_worst_variant': 0.0718,
     'liq_gamma': 9804, 'book_depth_near2c': 2552, 'book_filled_250': True,
     'lambda_home': 1.89, 'lambda_away': 1.26,
     'news_concurrence': 'PASS - no Bournemouth attack depletion reported (Fri searches found no new '
        'Bournemouth injuries; only stale Apr-2026 items); Bournemouth form best on slate (xG 3.30/gm, '
        '8 gf in 5, won 3-0 at Man Utd last weekend); Leeds away defense solid but that is exactly the '
        'model-vs-market disagreement being priced, not an injury artifact',
     'rationale': 'highest worst-variant edge among news-clean, different-fixture, real-depth passers; '
        'diversifies into a third independent fixture (held: BRE-FOR, HUL-IPS)'}],
   'not_taken': [
     {'q': 'Chelsea FC vs. Manchester United FC: Manchester United FC O/U 1.5 (Over)', 'exec': 0.1334, 'worst': 0.112, 'why': 'news-model conflict: Rashford/Sesko/Mainoo out; model full-strength MU overstates'},
     {'q': 'Tottenham Hotspur FC vs. Crystal Palace FC: Crystal Palace FC O/U 1.5 (Over)', 'exec': 0.1169, 'worst': 0.0996, 'why': 'Palace injury crisis + Sarr out; model overstates Palace attack'},
     {'q': 'Tottenham Hotspur FC vs. Crystal Palace FC: Crystal Palace FC O/U 0.5 (Over)', 'exec': 0.0878, 'worst': 0.075, 'why': 'same Palace crisis'},
     {'q': 'Brentford FC vs. Nottingham Forest FC: O/U 3.5 (Over)', 'exec': 0.0827, 'worst': 0.0712, 'why': 'same fixture as held #48 (goal-correlation concentration); r23 runner-up, stays runner-up'},
     {'q': 'AFC Bournemouth vs. Leeds United FC: AFC Bournemouth O/U 2.5 (Over)', 'exec': 0.0745, 'worst': 0.0635, 'why': 'passes gates but real depth near 2c only $655 - too thin vs the O1.5 line on same team'},
     {'q': 'Coventry City FC vs. Sunderland AFC: Coventry City FC O/U 0.5 (Over)', 'exec': 0.089, 'worst': 0.0421, 'why': 'real depth near 2c $232; var 5.6c near limit; worst cushion thinnest of set'},
     {'q': 'Coventry City FC vs. Sunderland AFC: O/U 2.5 (Over)', 'exec': 0.0585, 'worst': 0.0351, 'why': 'fails worst<+4c AGAIN (market barely moved 0.4891->0.4887); news (Isidor back, Thomas doubt) leans Over but gates are the gates'}],
   'near_misses_this_round': [r for r in scan['gate_rows_all'] if not r['gate_pass'] and r['edge_exec'] >= 0.05 and r['edge_worst'] >= 0.03 and len(r['fails']) <= 2]},

 'boulee_o25_recheck': {
   'question': 'AFC Bournemouth vs. Leeds United FC: O/U 2.5 (Over)',
   'r23_status': 'near-miss: exec +8.96c, worst +5.14c, var 6.09c - failed var by 0.09c',
   'current_book': scan['boulee_o25_recheck'],
   'verdict': 'STILL FLAGGED-ONLY, NOT ENTERED - model unchanged -> var unchanged at 6.09c (>6c). '
              'Ask identical at 0.520; exec +8.96c, worst +5.14c. Note: the fixture is now represented '
              'in the book via the Bournemouth O1.5 team-total candidate instead (var 5.61c, passes).',
   'var_gate_only_fails': [r for r in scan['gate_rows_all'] if not r['gate_pass'] and r['fails'] == ['var>6c'] and r['edge_exec'] >= 0.06]},

 'sources_fragility': {
   'pressers_fetched_utc': NOW,
   'brentford': 'Andrews Fri presser (BBC): Schade/Damsgaard/Colls back in contention',
   'forest': 'Glasner presser (BBC ck1l39602p38o, Sports Mole): Ndoye doubt, Delap fit, Igor Jesus out',
   'hull': 'Jakirovic presser (BBC cw054dqvnvzgo): no fresh concerns, Mendy back; Sports Mole absentee list',
   'ipswich': 'BBC preview: Lukic out only, Clarke fit; no main-scorer-out news',
   'man_utd': 'ManUtd.com official preview: Rashford/Mainoo/Sesko/Ugarte sidelined',
   'crystal_palace': 'Fox Sports/Premier Injuries: Sarr out (groin), injury crisis reported',
   'coventry_sunderland': 'Yahoo/Lampard: Thomas (calf) doubt; BBC/Le Bris: Isidor should be back',
   'bournemouth': 'no fresh injury news found (searches returned only Apr-2026 items)'}}

json.dump(cand, open(OUT + '/epl_candidates.json', 'w'), indent=1)
print('saved', OUT + '/epl_candidates.json')
print('new candidates:', len(cand['delta_scan']['new_candidates']))
print('verify:', cand['verification']['#48']['verdict'], cand['verification']['#49']['verdict'])
