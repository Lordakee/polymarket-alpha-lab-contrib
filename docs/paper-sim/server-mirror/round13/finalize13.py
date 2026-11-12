import json, datetime

OUT = '/home/ubuntu/paper-sim/round13'
RAW = f'{OUT}/raw'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

rec = json.load(open(f'{OUT}/crypto_recommendations.json'))
scan = json.load(open(f'{RAW}/crypto_scan.json'))
ms = scan['classified_markets']

# ---- top-5 nominal edges (report-only) ----
cands = []
for m in ms:
    if m['yes_ask'] is not None:
        cands.append((m['edge_yes'], 'YES', m))
    if m['yes_bid'] is not None:
        cands.append((m['edge_no'], 'NO', m))
cands.sort(key=lambda z: -z[0])
top5 = []
HELD = {'Will Bitcoin dip to $65,000 by December 31, 2026?': 'HELD (BTC-65k NO)',
        'Will Ethereum dip to $2,250 by December 31, 2026?': 'HELD (ETH-2250 YES)',
        'Will Ethereum dip to $2,000 by December 31, 2026?': 'HELD (ETH-2000 YES)'}
for e, side, m in cands[:8]:
    px = m['yes_ask'] if side == 'YES' else round(1 - m['yes_bid'], 3)
    fair_side = m['fair_yes'] if side == 'YES' else round(1 - m['fair_yes'], 4)
    top5.append(dict(market=m['q'], side=side, edge=round(e, 4), buy_price=px,
                     model_fair=fair_side, ev_usd_fraction=round(e / px, 3) if px else None,
                     T_days=m['T'], liquidity=m['liq'], status=HELD.get(m['q'], 'unheld')))
rec['top_edges_report_only'] = top5[:5]
rec['top_edges_extended'] = top5[5:8]

rec['cap_and_swap_assessment'] = {
    'cap_status': 'AT CAP: $1,870 / $1,900 committed across 3 positions; $30 free',
    'largest_unheld_edge': 'BTC dip $60k Dec-31 NO: +0.111/share (~12.9% EV fraction on ~0.86 px)',
    'swap_math': {
        'ETH-2000 hold edge (give up if sold)': '+0.109/sh vs bid 0.31 (fair 0.419); position EV premium ~$132',
        'ETH-2250 hold edge (give up if sold)': '+0.096..0.119/sh vs bid 0.67; position EV premium ~$245-303',
        'BTC-65k NO hold edge (give up if sold)': '+0.130/sh vs bid 0.76 (fair NO 0.890); position EV premium ~$50',
        'conclusion': 'No unheld edge exceeds the edge surrendered by exiting any held position after '
                      'spread+slippage friction (1-4c round trip). No swap recommended.'},
    'cap_raise_flag': 'NOT justified: best nominal edges cluster at +9c..+13c/share, same magnitude as '
                      'existing entries. A $190 (10%) cap raise deployed into BTC-60k/65k NO would add '
                      'only ~$25-32 EV; below the threshold for an owner proposal.',
}

rec['weekend_risk']['events_calendar'] = {
    'fri_oct_23': 'UMich consumer sentiment final (minor for crypto); S&P flash PMIs if scheduled (minor)',
    'sat_oct_24_sun_oct_25': 'No US macro prints (structural); no ETF creations/redemptions - crypto ETFs '
                             'do not trade weekends; last flow data of the week already out',
    'mon_oct_26': 'ETF flows resume; pre-FOMC positioning begins',
    'tue_wed_oct_27_28': 'FOMC meeting; rate decision Wed Oct 28 2:00 PM ET + presser 2:30 PM ET (AFTER the weekend - not a weekend event but Monday-Tuesday positioning risk)',
    'later_week': 'Q3 GDP advance (~Oct 29) and Sep PCE (~Oct 30); Deribit monthly options expiry Fri Oct 30',
    'etf_flow_regime': 'ETH spot ETFs: 5 consecutive outflow days through Oct 20 (-$388.8M streak, latest '
                       '-$26.1M, 14d z~1.0); October cumulative -$1.08B = worst month since Nov 2025; '
                       'ETH -9.7% MTD. Persisting into Monday would pressure spot, but weekend has no flow prints.',
}

rec['recommendation'] = {
    'eth2250_action': 'HOLD (full position, no scale-out this round)',
    'rationale': [
        'Conservative fair (zero-drift, 30d vol 2.46%) = 0.766; median-flat = 0.789; vs YES bid 0.67 / ask 0.68.',
        'Hold EV premium vs selling at bid: +0.096..0.119/share = +$245..$303 on 2,555 sh (~15-18% of bid value).',
        'Breakevens far from current regime: daily vol would need to COLLAPSE from 2.46% to 1.72% (-30%) for the '
        '70d fair to fall to the 0.67 bid, or ETH would need a +42%/yr log-drift uptrend at current vol.',
        'Vol-regime risk cuts the RIGHT way for this position: an ETF-outflow-driven vol spike RAISES fair '
        '(30d vol +25% -> fair 0.812/0.836 under A/B). The risk to holding is a sustained rally, not a selloff.',
        'Scale-out 25% (639 sh @ ~0.667 walk avg = $426) would bank +$113 profit on that slice but surrender '
        '~$61-76 of that slice EV; only worthwhile if cap room is needed for a better edge, which does not exist now.',
    ],
    'eth2000_action': 'HOLD (fair 0.419 vs bid 0.31; +0.109/sh edge; same dip-factor logic, higher torque if ETH breaks)',
    'btc65k_action': 'HOLD (fair NO 0.890 vs bid 0.76; +0.130/sh; barrier 25% away, weekend touch prob ~0.0%)',
    'monitoring_triggers': [
        'If ETH spot < 2,310 (recent low zone): ETH-2250 YES becomes near-certain; consider nothing, just hold.',
        'If ETH rallies > 2,650 (+11%): recompute - fair drops toward ~0.60-0.65; scale-out/exit review warranted.',
        'If 30d ETH vol prints < 1.9% daily for several days: fair approaches bid; revisit hold thesis.',
        'Round-14 (post-weekend, post-FOMC-week open) full re-scan.',
    ],
}

rec['asof_final'] = NOW.isoformat()
rec['data_sources'] = ['Coinbase Exchange 6h candles (ETH-USD, BTC-USD; 368 bars from 2026-07-23)',
                       'Polymarket gamma-api events/pagination (crypto/ethereum/bitcoin tags)',
                       'Polymarket gamma-api /markets/{3866000,3865999,3865962}',
                       'Polymarket clob.polymarket.com/book (6 books, YES+NO per position)',
                       'Web (local stack, policy-compliant): FOMC calendar confirmation, ETH ETF flow reports']
json.dump(rec, open(f'{OUT}/crypto_recommendations.json', 'w'), indent=1)
print('finalized', f'{OUT}/crypto_recommendations.json')
for t in top5[:8]:
    print('%-52s %-3s edge=%+.3f px~%.3f fair=%.3f %s' % (t['market'][:52], t['side'], t['edge'], t['buy_price'], t['model_fair'], t['status']))
