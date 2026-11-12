import json, time

ts=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

scan={
 'ts':ts,
 'window':'2026-11-03T02:00Z -> 2026-11-04T02:00Z',
 'server':'ubuntu@SERVER_HOST_REDACTED',
 'subscan':'politics/econ/world round29',
 'held_positions':{
  'senate_d_yes':{'market':'Will the Democratic Party control the Senate after the 2026 Midterm elections?','market_id':562793,'slug':'will-the-democratic-party-control-the-senate-after-the-2026-midterm-elections','held':'YES 384.6sh @ 0.65 (50)','gamma_mid':0.755,'clob':{'bid':0.75,'ask':0.76,'bid_depth_top':438153},'vol24':1307639,'liq':1326074,'end':'2026-11-04T04:59Z'},
  'ceasefire_oct31_yes':{'market':'US x Iran ceasefire continues through October 31?','market_id':4641065,'held':'YES 322.6sh @ 0.775 (50)','gamma_mid':0.317,'clob_final':{'bid':0.30,'ask':0.325},'end':'2026-10-31T23:59Z (deadline passed; open for adjudication)'}
 },
 'senate_evidence':{
  'final_nyt_siena':{'published':'2026-11-01/02 (final, election eve)','mi_d_hold':'+11 (53-42 El-Sayed over Rogers)','tx':'+7 Talarico 50-43 over Paxton','me':'+6 Jackson 51-45 over Collins','oh':'+5 Brown 49-44','ks':'+5 Hamilton 49-44 over Marshall','ak':'+2 Peltola 48-46 over Sullivan','ia':'tied (~D+1)','trump_approval_7states':'38%','cost_of_living':'D+9 across all 7 states','framing':'Dems leading in ALL 7 battlegrounds; need net +4 with 6 R-held flip targets; Levy (Siena): Senate majority for either party still possible, many races within MOE'},
  'models':{'nate_silver':'D Senate 80% (Newser Nov 2)','harry_enten_cnn':'projects Democratic gains in final forecast','cook':'MI shifted toward El-Sayed despite Stevens endorsing Rogers'},
  'early_vote':{'headline':'record 48M early ballots (Oct 31)','party':'D lead larger than 2024 (Oct 30)','ohio':'crushed 2026 early voting record','nc':'turnout bump vs 2022','enthusiasm':'Gallup: D more enthusiastic than R'},
  'risks':['pollsters caution late deciders breaking R','2016/2024-style correlated polling error; polls herded','Alaska: Peltola campaign FBI probe + Decoy Dan Sullivan clone-candidate scandal (judge rejected Trump removal suit; Sullivan says will accept results)','Michigan: Haley Stevens (D) endorsed Rogers; Jewish leaders write-in; Dana Bash doubts own network poll','Mike Johnson claims polls wrong (R cope)','ballot litigation: SCOTUS denied Trump admin on CA ballot segregation']
 },
 'ceasefire_crash_diagnosis':{
  'timeline_utc':[
   {'t':'2026-10-31 20:29','e':'resolution deadline Oct 31 23:59 IRST passes; YES 0.988'},
   {'t':'2026-11-02 21:00','e':'YES still 0.9825; market saw Oct29-30 Iranian claims (Qeshm naval base, Bandar-e Jask) and dismissed them (dip to 0.9035 on Oct30, recovered)'},
   {'t':'2026-11-03 00:39','e':'WSJ EXCLUSIVE: US secretly struck Qeshm Island MONDAY Nov 2 (US fighter jet destroyed IRGC SAM launcher; self-defense after IRGC AA fire); part of series of limited secret strikes in recent weeks kept quiet to avoid signaling resumption of war; targets: Irans ability to threaten commercial shipping'},
   {'t':'2026-11-03 00:43-02:35','e':'Oct-31 leg crashes 0.99 -> 0.38-0.62 whipsaw -> 0.30 bid; Nov-30 leg to 0.005-0.016; Nov-3 leg 0.075-0.081; Nov-2 leg 0.37-0.51'},
   {'t':'2026-11-03 02:08','e':'AP: US official confirms defensive strikes on some Iranian targets in Strait of Hormuz; Iranians using SAMs against US assets targeted; limited, not full return to hostilities'}
  ],
  'resolution_rules_key':{'NO_if':'US-initiated air or SSM strike directly impacting Iranian TERRESTRIAL territory by Oct 31 23:59 IRST','excluded':'intercepted munitions, SAM strikes, small arms, ground incursions, cyber, naval gunfire, artillery, minor SSM/FPV/ATGM, threats/announcements','maritime':'Irans maritime territory and airspace NOT included','adjudication':'on conflicting reports market stays open up to 3 full IRST calendar days from first credibly reported evidence; totality of US/Iran official info + credible reporting consensus; no single statement governs'},
  'case_YES':['only CONFIRMED US strike (WSJ/AP sourced) is Nov 2, AFTER deadline','Iran never confirmed any pre-deadline land strike; Fars reported Oct 29-30 explosions AT SEA near Qeshm/Sirik; Iran still has not confirmed cause of even Mondays 5 explosions','Oct 17-19 Konarak naval base claim: US officially denied; through-Oct-24 and through-Oct-28 legs RESOLVED YES with those claims outstanding - UMA standard requires confirmation, not claims','public record of the multi-week campaign = maritime interdictions (Oct 10 US fighter strike on cargo ship in Gulf of Oman; ship disabling) which are excluded from qualifying actions','Trita Parsi: Iranian sources blamed Israel for Qeshm; one US source told him US not responsible (attribution conflict) - attribution must be US'],
  'case_NO':['WSJ anonymous officials: strikes for SEVERAL WEEKS = campaign window overlaps the pre-Oct-31 deadline','Oct 29-30 Iranian claims: US targeted Qeshm NAVAL BASE (land) + 4 missiles struck Bandar-e Jask naval facility (land), unverified at the time; WSJ revelation retroactively raises their credibility','family track record: May 24 and August legs both sat >95% the night before US strikes broke them (My Investing News Nov 2); specialist sellers may have OSINT/satellite detail','market itself collapsed 0.99->0.30 on the revelation and kept falling; Nov-2 leg 0.37-0.51 vs Nov-3 leg 0.08 implies market puts near-half the break mass INSIDE the pre-Nov-1 window'],
  'uma_status':'no dispute/proposal yet (umaResolutionStatuses=[], closed=False, acceptingOrders=True); expect proposal + possible dispute within 3-day window (~Nov 5-6 IRST); family dispute history: May-24 leg 3x disputed, Apr-22 extension leg 3x disputed, Israel-Iran ceasefire 3x, Iran-Israel/US conflict-ends 2x (all per Hindcast disputes wall)',
  'hindcast':'disputes wall shows this family heavily disputed historically; radar flags D-Senate-control 56/High and Hormuz-agreement markets 98/High; no Oct-31-leg-specific radar entry visible in free preview'
 },
 'fresh_scan_board':[
  {'q':'Will the Democrats win the Michigan Senate race in 2026?','yes':0.785,'bid':0.78,'ask':0.795,'v24':897809,'end':'2026-11-04'},
  {'q':'Will the Fed increase interest rates by 25 bps after the December 2026 meeting?','yes':0.725,'v24':229125,'end':'2026-12-09'},
  {'q':'Will Republicans lose the Alaska, Iowa, Kansas, Maine, Michigan, Ohio, and Texas Senate races?','yes':0.365,'v24':2785688,'end':'2026-11-03'},
  {'q':'US announces end of Iranian blockade by December 31, 2026?','yes':0.395,'v24':243342,'end':'2026-12-31'},
  {'q':'Will Mary Peltola win the Alaska Senate race in 2026?','yes':0.725,'v24':94016,'end':'2026-11-04'},
  {'q':'Will Benjamin Netanyahu be the next Prime Minister of Israel?','yes':0.325,'v24':491042,'end':'open (formation)'},
  {'q':'Will the Democrats win the Kansas Senate race in 2026?','yes':0.615,'v24':83478,'end':'2026-11-04'},
  {'q':'Will the Democrats win the Maine Senate race in 2026?','yes':0.735,'v24':167618,'end':'2026-11-04'},
  {'q':'Will the Democrats win the Iowa Senate race in 2026?','yes':0.515,'v24':65011,'end':'2026-11-04'},
  {'q':'Will the U.S. invade Iran before 2027?','yes':0.165,'v24':548214,'end':'2026-12-31'},
  {'q':'Republican Party hold 47 or fewer Senate seats','yes':0.565,'v24':315782},
  {'q':'Will the Democrats win the Texas governor race in 2026?','yes':0.395,'v24':208875,'end':'2026-11-04'},
  {'q':'Will the Democrats win the Florida governor race in 2026?','yes':0.355,'v24':144824,'end':'2026-11-04'}
 ]
}
json.dump(scan,open('/home/ubuntu/paper-sim/round29/raw/politics_scan.json','w'),indent=1)
print('wrote politics_scan.json')
