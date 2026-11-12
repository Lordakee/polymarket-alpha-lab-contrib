#!/usr/bin/env python3
import json, os
RAW = os.path.expanduser("~/paper-sim/round45/raw")
OUT = os.path.expanduser("~/paper-sim/round45/politics_macro_candidates.json")
audit = json.load(open(os.path.join(RAW, "audit45.json")))
F = {
 "us_post_midterm": [
  {"market":"Dem Senate / Dem House control 2026","price":"both RESOLVED YES 1.00","liq":"n/a","note":"Ledger #47 Dem-Senate YES @0.65 won (+134.62). Dem sweep: House 252-161 (NPR), Senate 52+2-44. No liquid seat-count lag market remains."},
  {"market":"2026 Midterms House Turnout buckets (Clerk of the House source)","price":"115-120m .115/.205; 120-125m .769/.848 sz33; 125-130m .011/.013","liq":"5.3k-16.5k/leg","note":"~124m prelim turnout (UF lab) BUT measure is Clerk votes cast for House candidates, which ran ~4% BELOW ballots in 2022 (107.7m vs ~112m). >=120m not guaranteed; 115-120m live. NO MODEL -> NO ENTRY."},
  {"market":"El-Sayed 0-3 behind Benson (MI)","price":"YES .9645","liq":"$204","note":"near-certainty lag leg, dead book; cannot deploy $100-250. SKIP."},
  {"market":"Which Dems underperform Kamala (9 legs)","price":"Kotek .877 liq$78; Jackson .25 liq$45; rest .006-.025","liq":"dead","note":"SKIP."}],
 "fomc_rates": [
  {"market":"Fed Decision in December (Dec 8-9 2026)","price":"hike25 .76/.77 sz86k; no-change .22/.23 sz150k; cuts .008; hike50+ .007","liq":"364k-788k/leg","note":"Oct 27-28 FOMC held 3.75-4.00%. Reuters poll 100/100 economists expect Dec 25bp HIKE; Warsh signaling. All-NO ask sum = 4.000 exactly = perfectly efficient. NO ENTRY."},
  {"market":"Fed rate cut by Dec 2026 meeting","price":"YES .0125","liq":"53k","note":"NO at ~.99 = ~1c/30d vs hike-cycle risk; no edge. NO ENTRY."},
  {"market":"Core CPI YoY Oct (resolves Nov 11)","price":"2.6% modal .895; sum .9915","liq":"~2k/leg","note":"no bucket gap. NO ENTRY."},
  {"market":"Core CPI MoM Oct (resolves Nov 11)","price":".2% .485 / .3% .32; ask-sum 1.104","liq":"0.7k-3.5k/leg","note":"mid-sum .946 is bid-side artifact; ask-sum 1.104 kills buy-all arb. NO ENTRY."}],
 "funding_shutdown": [
  {"market":"Government shutdown by December 12?","price":".32/.34 sz750","liq":"moderate","note":"CR expires Dec 11 2026 (passed Sep, Senate 90-6). Lame-duck vote-math after Dem sweep. NO MODEL -> NO ENTRY."},
  {"market":"Government shutdown by December 31?","price":".40/.54 (14c spread)","liq":"thin","note":"wide spread = genuine uncertainty. NO ENTRY."}],
 "french_2027_beyond_basket": [
  {"market":"RN candidate 2027","price":"Le Pen RESOLVED YES (Oct 25 launch; closed)","note":"known leg-loss expectation confirmed."},
  {"market":"Lagarde advance (NEW leg created Nov 6; NOT HELD)","price":".08/.10 sz~1000/side","liq":"11.5k","note":"ECB exit Feb 7 2027 + candidacy speculation (Le Monde Nov 5-7, Irish Times Nov 6). If she advances, basket pays 35/unit (upside, not a hole). No declare -> no trade."},
  {"market":"Melenchon advance (HELD NO)","price":".50/.51","liq":"24.6k","note":"polls 15-19% 1st round, consolidated left #2; likely 2nd advancer per market. In-basket risk leg; floor unchanged."},
  {"market":"Lisnard advance (HELD NO)","price":".172/.18 sz1099","liq":"37.3k","note":"hottest money in family (vol 245k ~7x others); polls 3rd. In-basket risk leg; floor unchanged."},
  {"market":"PM Lecornu advance (HELD NO)","price_mid":0.0345,"note":"PM since Sep 2025. Tail leg."},
  {"market":"Mellonium lookup","note":"No Mellonium in French politics/news; new-right surge = Lisnard (.176); new establishment entrant = Lagarde (.09)."}],
 "geopolitics": [
  {"market":"Russia-Ukraine peace talks by Nov 15","price":".949/.976 sz712","liq":"thin","note":"RULE: joint/mediated RU-UA meeting on substantive terms (incl security guarantees) qualifies. Abu Dhabi trilateral Nov 10-11 announced (US mediating, Medinsky leads RU). Earlier 2026 legs resolved NO (Geneva Feb = shuttle, no qualifying joint meeting). CLOSEST MISS: at .976 ask the ~2-3% cancellation/criterion risk eats the edge (schedule wobbled Nov 6-10 -> 10-11). Fails (b). NO ENTRY. Conditional: once delegations confirmed ARRIVED, by-Nov-30 (.982, sz100) turns attractive."},
  {"market":"RU-UA talks by Nov 30 / Dec 31","price":"ask .982 / .982","note":"same event, thinner edge. NO ENTRY."},
  {"market":"Serbia election called by Nov 30","price":"YES .987","note":"1.3c for snap-call risk. PASS."},
  {"market":"NatGuard at election sites Nov30 .023 vs Dec31 .019","note":"monotonicity violation, 0.4c wide = inside spread, unexecutable. NOTED."},
  {"market":"US imports Russian diesel by Nov 30","price":"YES .175","note":"no dated catalyst. PASS."},
  {"market":"Next Israeli govt by Nov 30 / Dec 31","price":".122 / .41","note":"no mandate-deadline clarity. PASS."},
  {"market":"Ukraine peace referendum by Dec 31 2026","price":"YES .028","note":"PASS."}],
}
out = {
 "round":"45A","team":"politics+macro+geopolitics","date":"2026-11-09",
 "window":"now through 2026-11-30","mode":"PAPER ONLY - no orders, no DB writes",
 "discipline":"STRUCTURAL-NO-MODEL requires (a) dated resolution mechanism (b) price vs stated reasoning chain (c) focused news check (d) size $100-250. No quantitative model exists for these domains.",
 "held_position_audit": audit,
 "scan_findings": F,
 "proposals": [],
 "proposals_note":"NONE. Every candidate failed >=1 gate: RU talks Nov-15 (edge consumed at .976 ask); House-turnout >=120m set (Clerk House-votes ~4% below ballots in 2022 breaks guarantee); Fed Dec hike-25 (100/100 consensus priced, all-NO sum 4.000 exact); MI margin + underperform-Kamala (dead liq); shutdown/Fed directions (vote-math, no model).",
 "news_sources":[
  "Reuters/Toluna-Harris Nov 9 2026: Le Pen 34-36% R1, Melenchon 15-19%, runoff 45-47 (reuters.com/world/le-pen-melenchon-ahead-2027-french-presidential-race-poll-shows-2026-11-09)",
  "AP News: US-mediated trilateral RU-UA talks Abu Dhabi Nov 10-11 2026; Medinsky leads RU delegation",
  "NPR 2026 results live: House 252-161 D; Senate D52/I2/R44; Ballotpedia Nov 6: D250, 28 uncalled",
  "UF election lab via 8-charts analysis: ~124m prelim 2026 turnout",
  "CNBC/Investopedia Oct 28 2026: FOMC hold 3.75-4.00%; Reuters poll 100/100 Dec 25bp hike; CME ~75%",
  "CR expires Dec 11 2026 (Senate 90-6, Sep 2026); lame-duck funding coverage",
  "Le Monde Nov 5-7 + Irish Times Nov 6 2026: Lagarde candidacy speculation; ECB exit Feb 7 2027",
  "Gamma/CLOB raw fetches in round45/raw/"],
 "ledger_context":{"bankroll_latest":"cash 12032.78, deployed 1735.65 (2026-11-09 07:44Z)",
  "related_resolved":"#47 Dem Senate YES .65 won +134.62; #38 ceasefire window passed; #42 Lula settled",
  "db_access":"read-only psql selects on paper_sim; no writes"},
}
json.dump(out, open(OUT, "w"), indent=1)
print("WROTE", OUT, os.path.getsize(OUT), "bytes")
