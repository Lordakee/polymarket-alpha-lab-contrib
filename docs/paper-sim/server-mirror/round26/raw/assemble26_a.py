"""Round-26 scan A: assemble candidates_a.json (max 2 candidates, flags, recheck table)."""
import json, time
from polymarket_alpha_lab.papersim import risk_policy

RAW = '/home/ubuntu/paper-sim/round26/raw'
scan = json.load(open(RAW + '/scan_a.json'))
books = {(b['fixture'], b['key']): b for b in json.load(open(RAW + '/books26_a.json'))}
gr = {(g['fixture'], g['key']): g for g in scan['gate_rows']}

tier = risk_policy.sizing_tier(market_class='standard', fragile_pass=False, lineup_confirmation=0.0)
stake0 = risk_policy.tier_notional(tier, lineup_confirmation=0.0)
stake1 = risk_policy.tier_notional(tier, lineup_confirmation=1.0)

gen = gr[('Lecce-Genoa', 'tt_away_over_1.5')]
gen_book = books[('Lecce-Genoa', 'tt_away_over_1.5')]
exit_bid = gen_book['books']['side']['bid_walk']['best']

candidates = [{
    'rank': 1,
    'match': 'US Lecce vs. Genoa CFC',
    'league': 'Serie_A',
    'kind': 'team_total (Genoa O/U 1.5 Over)',
    'kickoff_utc': '2026-11-01T17:00:00Z',
    'market_q': gen['q'],
    'market_id': gen['market_id'],
    'side': 'Over 1.5 (Genoa team total)',
    'model_med': gen['model_med'], 'model_worst': gen['model_min'], 'model_best': gen['model_max'],
    'var_spread': gen['var_spread'],
    'exec_ask_vwap_250': gen['entry_vwap250'],
    'filled_250': gen['fill_250'],
    'exit_bid': exit_bid,
    'depth_2c': gen['depth_near2c'],
    'edge_exec': gen['exec_edge'],
    'worst_var_edge': gen['worst_variant_edge'],
    'liq_gamma': gen['liq_gamma'],
    'gates': gen['checks'],
    'under_risk': False,
    'suspension_policy': gen['suspension_policy'],
    'sizing': {'tier': tier.tier, 'stake_now_usd': stake0, 'stake_on_confirmed_xi_usd': stake1,
               'reason': tier.reason},
    'stake_usd': stake0,
    'paper_only': True,
    'fragility': ('(1) XIs UNCONFIRMED at scan (10:00Z; KO 17:00Z, XIs ~16:00Z): news delta rests on predicted-XI previews '
                  '(Genoa without Ilic+Sow - central mids, no forward depletion; Lecce without Coulibaly). A Genoa rotation '
                  'or defensive setup would invalidate the Over-1.5 direction. (2) Depth: depth_2c $3.7k is thin-ish; liq '
                  'gate passed on Gamma liquidity ($18.3k) and the $250 walk filled at one level (0.35). (3) Margin: worst-variant '
                  'edge +5.9c breaks if ask VWAP rises above 0.369 (entry ceiling). (4) Match total O2.5 on the same fixture '
                  'FAILS var (17.7c) - the TT row is stable (3.7c) precisely because per-side goal distributions are '
                  'DC-invariant, but the same rating uncertainty is shared. (5) Genoa lost last 3 away (in-data).'),
    'entry_note': ('PAPER entry <= 0.36 ceiling, $150 now (EARLY_ENTRY tier); scale to $250 only after confirmed XIs '
                   '(~16:00Z) show Genoa full front line and a fresh gate run re-passes. Re-verify book at entry.'),
}]

flagged = [
    {'fixture': 'Elche-Valencia', 'key': 'over_2.5',
     'why': 'BOUNDARY MISS by 0.01c: worst-variant edge +3.99c vs +4c bar (model_min 0.5386 vs ask VWAP 0.4987, verified stable 10:01Z; an earlier 09:52Z walk at 0.498 gave +4.1c - book tick lability). exec +5.49c, var 2.1c, liq $124k, news unchanged, no under_risk. r25 missed by 0.1c; still the best watch item: re-run gates at XI confirmation (~16:30Z); enter only on a fresh full pass.',
     'gates': gr[('Elche-Valencia', 'over_2.5')]['failed_gates']},
    {'fixture': 'Elche-Valencia', 'key': 'over_3.5',
     'why': 'under_risk FLAGGED (lambda_total 2.90 < 3.4 for O3.5 -> 8c bar) + worst 3.56c fail.',
     'gates': gr[('Elche-Valencia', 'over_3.5')]['failed_gates']},
    {'fixture': 'Athletic-RealSociedad', 'key': 'ml_home',
     'why': 'r25 news-kill RESOLVED (Sancet available after calf, Nico Williams fit and starting, Laporte back) - news now concordant/better, worst +5.9c and var 6.0c both pass. Blocked ONLY by the 50-50 cancellation haircut: median 0.540 sits in [0.45,0.55] so exec halves to +3.49c < 5c. Deprioritized ML class anyway. Recheck pre-KO only if median/ask migrate out of the haircut band.',
     'gates': gr[('Athletic-RealSociedad', 'ml_home')]['failed_gates']},
    {'fixture': 'Juventus-Napoli', 'key': 'ml_home',
     'why': 'News-conflicted: r25 had Yildiz+Locatelli OUT; today conflicting reports (Football Italia headline suggests Yildiz+Conceicao start; not official). Plus 50-50 haircut halves exec to +3.59c. Recheck at 18:45Z XIs.',
     'gates': gr[('Juventus-Napoli', 'ml_home')]['failed_gates']},
    {'fixture': 'Lazio-Cagliari', 'key': 'tt_away_over_0.5 / tt_away_over_1.5',
     'why': 'Cagliari TT overs fail worst-variant by 0.3-0.7c (+3.29c / +3.66c). News unchanged (Liteta squad-forward out only).',
     'gates': ['worst_edge']},
    {'fixture': 'RacingSantander-RealMadrid', 'key': 'all high-edge rows',
     'why': 'Var artifact is STRUCTURAL, not XI-compressible: Racing is promoted with no 2025 top-flight history in the xG snapshot, so sweep variants disagree on prior fallback (var 5.5-31c across rows; the +29c TT-under and +19c ML rows all carry var>=19c). Confirmed XIs change news, not model variance. Plus news unknown (Mourinho rotation risk). Skip for the round.',
     'gates': ['variant_spread', 'news_concordant']},
    {'fixture': 'Frosinone-Torino', 'key': 'match totals',
     'why': 'Same promoted-side structural var (Frosinone: var 12.8-26.6c on totals). Book ALSO moved against r25 Over lean: O2.5 ask 0.62 (r25) -> 0.7066 now, exec -7.6c; U3.5 +6.8c but var 26.6c. r25 verdict (var block) unchanged and now reinforced by price.',
     'gates': ['variant_spread']},
    {'fixture': 'Lecce-Genoa', 'key': 'over_2.5 (match total)',
     'why': 'Book moved our way (O2.5 ask 0.40, exec +13.7c, worst +6.3c) but variant spread 17.7c FAILS var<=6c - the shared promoted/short-history uncertainty again. The stable expression of this lean is the Genoa TT O1.5 candidate.',
     'gates': ['variant_spread']},
    {'fixture': 'Getafe-Sevilla', 'key': 'ml_home',
     'why': 'Exec +12.9c headline but var 16.2c and worst -0.06c - variants straddle the market. Var fail; news unknown.',
     'gates': ['variant_spread', 'worst_edge', 'news_concordant']},
    {'fixture': 'Como-Venezia', 'key': '(11:30Z KO, news-clean rule)',
     'why': 'No row passed var pre-CLOB (best: ml_away +7.8c at var 10.5c). Como news is WORSE (Kean out among 5 injured) - nothing news-clean available regardless. Honest no-candidate.',
     'gates': ['variant_spread']},
]

near_miss_recheck = [
    {'r25_item': 'Juventus ML +9.2c (news-killed: Yildiz/Locatelli out + Thuram/Celik/N.Gonzalez doubtful)',
     'today': 'gamma ask 0.44 (was 0.42); exec +7.2c, worst +5.2c, var 5.5c - numerics pass, BUT 50-50 haircut halves exec to +3.6c (median 0.512 in band) and news is now CONFLICTED (reports Yildiz may start) -> unknown, non-concordant',
     'verdict': 'STILL NO-ENTRY; haircut + news. Recheck at 18:45Z XIs.'},
    {'r25_item': 'Athletic ML +9.0c (news-killed: Sancet calf + Nico Williams)',
     'today': 'ask 0.47, exec +7.0c, worst +5.9c, var 6.0c; news IMPROVED to better (Sancet available, Nico Williams fit/starting, Laporte back) - r25 news explanation is resolved',
     'verdict': 'NO-ENTRY on the 50-50 haircut (+3.5c < 5c). The r25 kill reason is gone; watch the band.'},
    {'r25_item': 'Elche-Valencia O2.5/O3.5 (worst missed by 0.1c; Aguado out)',
     'today': 'O2.5: exec +5.49c, var 2.1c, liq $124k, news unchanged (Aguado still ankle-out; Valencia Elliott susp/Sadiq/Copete out offset Elche attack doubts clearing) - worst +3.99c, misses by 0.01c (stable at 10:01Z). O3.5: under_risk-flagged (lt 2.90<3.4) + worst 3.56c',
     'verdict': 'O2.5 = #1 WATCH: re-run gates at XIs (~16:30Z); enter only on fresh full pass. O3.5 no.'},
    {'r25_item': 'Frosinone/Lecce totals (+4.7-13.7c, var 17-23c)',
     'today': 'Frosinone O2.5 book moved to 0.7066 (exec -7.6c) and U3.5 +6.8c var 26.6c - still var-fail both; Lecce O2.5 exec +13.7c var 17.7c - still var-fail',
     'verdict': 'UNCHANGED: var gate holds. Lecce lean expressed via gate-stable Genoa TT O1.5 instead.'},
    {'r25_item': 'Racing-Real Madrid (var artifact 15-28c - recheck if confirmed XIs compress)',
     'today': 'Var artifact confirmed STRUCTURAL: Racing promoted, no 2025 top-flight xG history -> prior-fallback disagreement across variants (var up to 31c). Confirmed XIs cannot compress MODEL variance; only news/under_risk would move',
     'verdict': 'SKIP permanently this round; revisit only with a promoted-side prior fix (out of scope).'},
]

out = {
    'scan': 'soccer_a', 'round': 26, 'paper_only': True,
    'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'sub_scan': 'A (Serie A + La Liga, Sunday Nov 1)',
    'bankroll_usd': 12374.33, 'cash_usd': 9488.68,
    'max_new_positions': 2, 'candidates_submitted': len(candidates),
    'library_adoption': {
        'worked': [
            'PYTHONPATH=src import of papersim xg/soccer_model/gates/risk_policy - zero bespoke modeling code',
            'cli selfcheck PASS 10/10 before use',
            'fixture_variants/candidate-side quotes give true 10-variant ranges (gate-safe); the Racing/Frosinone var artifacts and the Elche 0.01c worst-edge miss are exactly what the gate-safe path is for',
            'gates.walk_book/evaluate_candidate/check_news/under_risk_check/suspension_policy/rank_candidates all usable as documented; under_risk_check o25+lambda semantics matched the r15 lineage',
            'risk_policy.sizing_tier gave the EARLY_ENTRY $150->$250 discipline for unconfirmed XIs',
        ],
        'friction': [
            'usage.md says "import papersim.xg" but the real module root is polymarket_alpha_lab.papersim (doc wording)',
            'RecentForm field names (over_2_5_hits, goals_per_game) are not in usage.md - first guess (o25_hits) returned None silently',
            'evaluate_candidate is ask-only and walks its own $250 - books must be passed as raw levels, so saved walk summaries are not enough; fetch levels in the gate pass itself',
            'candidate_from_variants only builds match O/U candidates; ML/BTTS/TT sides need hand-built quote objects exposing model_median + qs_variants (documented pattern, but a builder for those kinds would remove the last bespoke glue)',
        ],
    },
    'candidates': candidates,
    'flagged': flagged,
    'near_miss_recheck': near_miss_recheck,
}
json.dump(out, open(RAW + '/candidates_a.json', 'w'), indent=1)
print('wrote candidates_a.json: candidates=%d flagged=%d recheck=%d' % (
    len(candidates), len(flagged), len(near_miss_recheck)))
print('stake tier:', tier.tier, stake0, '->', stake1, '| exit bid:', exit_bid)
