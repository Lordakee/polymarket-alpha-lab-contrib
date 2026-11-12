import json, math, datetime

RAW="/home/ubuntu/paper-sim/round12/raw"
OUT="/home/ubuntu/paper-sim/round12"
NOW=datetime.datetime(2026,10,22,12,0,tzinfo=datetime.timezone.utc)

scan=json.load(open(RAW+"/scan_classified.json"))
books=json.load(open(RAW+"/books_finalists.json"))
finals=json.load(open(RAW+"/finals_fills.json"))

raw_out=dict(
 generated_at=NOW.isoformat(),
 scope="Polymarket BTC/ETH markets through 2026-12-31, round-12 paper scan",
 spot={"ETH":2397.59,"BTC":81717.07},
 realized_vol_daily={"ETH":{"7d":0.0244,"30d":0.0245,"60d":0.0241,"87d":0.0259},
                     "BTC":{"7d":0.0165,"30d":0.0163,"60d":0.0179,"87d":0.0185}},
 model=dict(vol_source="Coinbase 6h candles, sqrt-scaled",
   conventions=["A: zero-log-drift GBM","B: median-flat (mu_log=-sigma^2/2)"],
   touch="drifted first-passage (reflection principle form)",
   note="conservative fair for a buy = convention least favorable to that side; daily markets resolve 16:00 UTC Binance 1m candle; weekly/yearly touch per Binance 1m High/Low"),
 barrier_checks=dict(
   btc65=dict(created="2026-08-25",min_low_since=74888,touched_65000=False),
   btc95=dict(created="2026-06-08",max_high_since=87397,touched_95000=False),
   eth3000=dict(created="2026-06-08",max_high_since=2807,touched_3000=False),
   eth2250=dict(created="2026-08-25",min_low_since=2313,touched_2250=False),
   eth2000=dict(created="2026-08-25",min_low_since=2313,touched_2000=False),
   btc80w=dict(created="2026-10-19",min_low_since=81081,touched_80000=False)),
 classified_markets=scan,
 finalist_books=books,
 finalist_fills=finals["fills"])
json.dump(raw_out,open(RAW+"/crypto_scan.json","w"),indent=1)

cands=dict(
 generated_at=NOW.isoformat(),
 caps=dict(crypto_team_cap_usd=1900,current_exposure_usd=1570,max_new_usd=330,note="cap leaves $330; 'max 1 position <=$400' not binding"),
 existing_positions_mtm=[
  dict(market="ETH dip to $2,250 by Dec 31 2026",side="YES",cost_usd=1250,avg_cost=0.489,
       bid=0.66,ask=0.68,mid=0.67,shares=2555,mtm_bid_usd=1686,pnl_usd=436,pnl_pct=34.9,
       model_fair_A=0.758,model_fair_B=0.781,action="hold"),
  dict(market="ETH dip to $2,000 by Dec 31 2026",side="YES",cost_usd=320,avg_cost=0.265,
       bid=0.30,ask=0.31,mid=0.305,shares=1208,mtm_bid_usd=362,pnl_usd=42,pnl_pct=13.3,
       model_fair_A=0.379,model_fair_B=0.414,action="hold")],
 candidates=[
  dict(rank=1,market="Will Bitcoin dip to $65,000 by December 31, 2026?",side="NO",
       event="What price will Bitcoin hit in 2026?",executable=0.78,fill_330usd="423 sh @ 0.78",
       fair_A=0.906,fair_B=0.895,conservative_fair=0.895,edge_c=11.5,edge_c_87dvol=7.9,
       liquidity_usd=56112,horizon_days=70.5,
       reason="20% crash touch priced at 0.22-0.24 vs model 0.09-0.11; edge survives every realized-vol window; directionally offsets existing ETH crash-long book",
       caveats="dies only under stress vol >=2.5%/d (unrealized in 7/30/60/87d windows); loses in a deep-crash scenario where ETH dips win (portfolio-level tradeoff)"),
  dict(rank=2,market="Will Bitcoin reach $95,000 by December 31, 2026?",side="NO",
       event="What price will Bitcoin hit in 2026?",executable=0.647,fill_330usd="avg 0.647",
       fair_A=0.730,fair_B=0.750,conservative_fair=0.730,edge_c=8.3,edge_c_87dvol=2.1,
       liquidity_usd=46812,horizon_days=70.5,
       reason="+16% rally touch priced 0.36-0.37 vs model 0.25-0.27 at 30d vol",
       caveats="edge nearly vanishes at 87d vol (1.85%/d); top-of-book depth thin (200 @ 0.64)"),
  dict(rank=3,market="Will Bitcoin dip to $80,000 October 19-25?",side="YES",
       event="What price will Bitcoin hit October 19-25?",executable=0.423,fill_330usd="avg 0.4226, 781 sh",
       fair_A=0.463,fair_B=0.468,conservative_fair=0.463,edge_c=4.0,edge_c_87dvol=9.6,
       liquidity_usd=23480,horizon_days=3.2,
       reason="spot 81,717 only 2.1% above barrier with 3.2d left; edge grows with vol",
       caveats="below the 5c bar at headline 30d vol (+4.0c); BTC in intraday downtrend (day range 84,305->81,546) both helps and signals momentum risk; weekly window already 3 days elapsed, no touch (min low 81,081)")],
 excluded=[
  dict(market="Will Ethereum dip to $2,300 October 19-25?",side="YES",executable=0.27,
       fair=0.341,edge_c=7.1,reason="EXCLUDED: third ETH-downside dip position; duplicates existing ETH 2250/2000 dip risk direction per task rules"),
  dict(market="Will Ethereum hit $1,000 or $3,000 first?",side="$1,000 token",executable=0.35,
       fair_blended=0.362,reason="EXCLUDED: resolves 50-50 if neither level hit by Dec-31; blend rule cuts fair($1,000) to 0.36 vs ask 0.35 (edge <=2.7c); raw unblended edge was illusory"),
  dict(market="Same-day dip/above markets (BTC dip 80k/81k on Oct 22 etc.)",side="NO",
       reason="EXCLUDED: 4h horizon; GBM zero-drift ignores intraday momentum (BTC fell 84.3k->81.5k today) and fat tails; model inadequate, not a true edge despite +10-15c nominal"),
  dict(market="Will Bitcoin reach $90,000 by December 31, 2026?",side="NO",executable=0.44,
       fair=0.521,reason="EXCLUDED: edge +8c at 30d vol but only +2c at 87d vol; not robust"),
  dict(market="Will Ethereum reach $3,000 by December 31, 2026?",side="NO",executable=0.681,
       fair=0.723,reason="EXCLUDED: +4.2c at 30d, +1.7c at 87d (fails bar); also same ETH-weakness direction as existing book")],
)
json.dump(cands,open(OUT+"/crypto_candidates.json","w"),indent=1)
print("wrote",RAW+"/crypto_scan.json")
print("wrote",OUT+"/crypto_candidates.json")
import os
print("scan size:",os.path.getsize(RAW+"/crypto_scan.json"),"cands size:",os.path.getsize(OUT+"/crypto_candidates.json"))
