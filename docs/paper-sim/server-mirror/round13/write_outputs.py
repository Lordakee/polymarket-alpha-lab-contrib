import json

scan = {
 "round": 13,
 "team": "US-SPORTS (NBA/NFL/MLB)",
 "generated_utc": "2026-10-23T01:20Z",
 "method": "gamma events/pagination tag_slug={nba,nfl,mlb} active=true closed=false order=volume24hr (nfl 4 pages); CLOB books via curl; ESPN site.api scoreboards 20261022-20261025; sportsbook devig + injury news via web search",
 "results_check": {
  "note": "Task brief assumed DEN@OKC and CLE@PHI finished; at scan time (Oct 23 ~01:00 UTC = Thu ~9pm ET) they were in progress / pre-tip. TNF also in progress.",
  "DEN_at_OKC": {"status_at_scan": "pre-tip (tips 9:30 PM ET Oct 22)", "pm_price": "OKC 0.735 / DEN 0.265 (was 0.745 round-12)", "books": "OKC -8.5 (-115), ML -306/-340, DEN +240 -> devig OKC ~0.72", "jokic_murray": "both OUT (Jokic wrist, Murray shoulder), confirmed round-12"},
  "CLE_at_PHI": {"status_at_scan": "in progress 4th quarter CLE 90 PHI 82", "pm_live": "CLE ~0.695", "context": "Garland out, Allen/Mitchell played; CLE covering the 0.415 pre-game side"},
  "TNF_NE_at_CHI": {"status_at_scan": "in progress 2Q CHI 10 NE 7", "pm_live": "CHI ~0.735", "context": "CHI 4-2 vs NE 4-2; Bears RB Monangai OUT (thumb/toe)"},
  "POR_opener": {"result": "POR beat PHX (Wed Oct 21, market resolved POR 1-0)", "por_record": "1-0"},
 },
 "por_position_mtm": {
  "market": "Will the Portland Trail Blazers make the 2027 NBA Playoffs?",
  "entry": "YES $369.65 @ 0.612 (604.66 shares) [held from prior rounds]",
  "now": "bid 0.64 x248 / ask 0.66; mid 0.65; gamma last 0.655; vol24 $283k",
  "unrealized": "+$22.9 at mid (0.65*604.66=$393.0 vs $369.65) = +6.2%",
  "exit_slippage_note": "top-of-book thin (248 sh at 0.64); full 605-share exit walks to ~0.637 avg",
  "health": "Ja Morant and Damian Lillard both healthy/active (Ja came off bench behind Dame+Scoot in one preseason look); no injury flags",
  "next_game": "POR @ SAC Fri Oct 23 7pm ET: Polymarket POR 0.725 vs books POR -6.5 ML -225/+233 devig ~0.698 -> market ~2.5c RICH, no add",
 },
 "ws_markets": {
  "series": {"pm": "Rays 0.365-0.366 / MIL 0.635-0.6375 (champ market + TB@MIL main, deep books ~2-6k sh lvls)", "books": "MIL ~62% (Covers preview); -165/-180 at open", "gap": "<=1.5c, in line"},
  "game1": {"pm": "Rays 0.41/0.43 MIL 0.57/0.59 (thin main-B book, mid MIL ~0.58)", "books": "MIL -158/-162, Rays +134/+140, total 6 -> devig MIL ~0.593", "gap": "~1c, in line", "pitchers": "Rasmussen (16-5, 2.67) vs Misiorowski"},
  "g2_g3_markets": "not yet spawned on Polymarket; appear after G1",
 },
 "nfl_week7_vs_books": {
  "CIN@BAL": {"pm": "CIN 0.47/0.48, BAL 0.52/0.53 (flipped from CIN 0.52 round-12)", "books": "open BAL -3/-3.5 -> -2.5 -> CIN -1.5 midweek (Huntley pricing) -> recovering toward BAL on Lamar practice; ML BAL -150/-160 stale quotes", "lamar": "limited Wed+Fri, limping, GTD/'murky'; missed last 2 games; Zac Taylor preparing as if he plays; BAL 4-2, 3-1 in Huntley starts since 2025", "reasoned_prob": "~0.50 +/- 0.04 blend", "gap": "market BAL 0.525 inside uncertainty band; no >=10c side"},
  "TB@CAR": {"pm": "TB 0.41/0.42, CAR 0.58/0.59", "books": "CAR -3.5, ML TB +154/CAR -185 -> devig CAR 0.622; FPI CAR by 5.1", "gap": "~3c on CAR, sub-bar"},
  "LAR@LV": {"pm": "LAR 0.64/0.65", "books": "LAR -4.5 (open -5.5; Adams out 6-10wk absorbed) -> devig ~0.655-0.66", "gap": "~1c, in line"},
  "DAL@PHI(MNF)": {"pm": "DAL 0.64/0.65", "books": "Cloudbet DAL 1.46/PHI 2.70 -> devig DAL ~0.65", "gap": "~1c, in line; Hurts IR known; A.J. Brown ankle worth watching"},
  "KC@SEA(SNF)": {"pm": "KC 0.42/0.43", "books": "round-12 KC +114/SEA -135 devig KC 0.453; line stable", "gap": "~2.5c on KC, sub-bar"},
  "SF@ATL": {"pm": "SF 0.58/0.59", "books": "line n/a in search; Mike Evans (SF, Achilles) ruled out/missing time - absorbed by books; possible ~3-4c on ATL if books dropped SF to -1.5", "gap": "unconfirmed, likely sub-bar"},
  "PIT@NO(London)": {"pm": "PIT 0.62/0.63", "gap": "no book line found; low liquidity interest, sub-bar expected"},
  "DEN@ARI": {"pm": "DEN 0.66/0.67", "gap": "no book line found; one of two DD spreads wk7 per preview"},
  "GB@DET": {"pm": "GB 0.37/0.38", "gap": "thin volume; books n/a in search"},
 },
 "nba_weekend_vs_books": {
  "POR@SAC_Fri": {"pm": "POR 0.725", "books": "POR -6.5, ML -225/+233 devig 0.698", "gap": "PM ~2.5c rich on POR"},
  "NYK@BOS_Fri": {"pm": "NYK 0.445/BOS 0.555", "books": "BOS -3, NYK +120 -> devig BOS ~0.562", "gap": "~0.5-1c, in line"},
  "other_fri": "CHI@MIL 0.495/0.505, PHI@MIL Sat, OKC home Sun vs LAC - thin/no book gaps found; Sat/Sun markets low volume",
 },
 "tnf_context": "NE@CHI: Monangai (CHI RB) OUT thumb/toe, Sanborn OUT, T.J. Edwards doubtful",
 "sources": [
  "bengals.com/news/bengals-ravens-week-7-2026-injury-report",
  "sports.yahoo.com/articles/ravens-face-crucial-lamar-jackson-100052640.html",
  "espn.com/nfl/story/_/id/50241195/lamar-jackson-practice-unclear-vs-bengals-week-7",
  "azcentral.com Bengals-Ravens wk7 odds (open -3/-3.5 -> -2.5)",
  "cincyjungle.com Huntley/Lamar sudden shift",
  "cbssports.com Rays-Brewers G1 odds",
  "covers.com 2026-world-series-preview (MIL ~62%)",
  "dimers.com + tsn.ca POR@SAC odds",
  "espn.com/nba/odds NYK@BOS (-3, NYK +120)",
  "espn.com/nba/odds DEN@OKC (-8.5, OKC -340 ML)",
  "theedgesheet/aisportpicks LAR@LV -4.5 (open -5.5)",
  "nfl.com week-7 injury report; yahoo/nbc/fantasy Adams-Evans-Hurts",
 ],
}

cands = {
 "round": 13,
 "generated_utc": "2026-10-23T01:20Z",
 "bar": ">=10c edge vs reasoned probability (anchored to sportsbook devig), liquidity >= $10k, resolution <= 14d preferred, max 1 new position <= $200",
 "candidates_evaluated": [
  {"market": "NFL wk7 CIN @ BAL (Oct 25) - round-12 near-miss recheck", "side_considered": "BAL 0.525 / CIN 0.475 after market flipped toward BAL", "reasoned_prob": "0.50 +/- 0.04 (Lamar GTD limping; Huntley 3-1 as starter since 2025; BAL home 4-2; books oscillated CIN -1.5 <-> BAL -2.5 during week)", "edge_c": "0 (both sides inside uncertainty band)", "liquidity": "$1.43M event, 1c spread, 57k-share top levels", "resolution": "Oct 25", "verdict": "REJECT", "reason": "Price moved from CIN 0.52 to BAL 0.525 but Lamar's Friday 'limited + limp + GTD' makes true prob a coin flip; no side offers 10c; recheck Sunday inactive list could create an in-game edge, out of scope now"},
  {"market": "WS Champion 2026 (series) + Game 1 Rays@MIL", "side_considered": "Rays series 0.365-0.366 / MIL G1 0.57-0.59", "reasoned_prob": "series MIL ~0.62 (books); G1 MIL ~0.593 (books -160 devig)", "edge_c": "<=1.5c", "liquidity": "series deep (2-6k sh levels); G1 main book thin (65-321 sh)", "resolution": "by Oct 31-Nov 1", "verdict": "REJECT", "reason": "G1 not yet played (tips Fri 8pm ET); no market reaction to price since matchup set (Rays 0.37 -> 0.365-0.366); books and Polymarket agree within 1-1.5c; Rasmussen (2.67 ERA) vs Misiorowski fairly priced at total 6"},
  {"market": "NFL wk7 TB @ CAR", "side_considered": "CAR 0.58/0.59", "reasoned_prob": "CAR ~0.622 (books CAR -3.5, TB +154/CAR -185 devig; FPI CAR by 5.1)", "edge_c": "~3 on CAR", "liquidity": "$1.84M event, vol24 $103k", "resolution": "Oct 25", "verdict": "REJECT", "reason": "Largest clean book-vs-PM gap on Sunday slate but well under 10c bar; FPI agreeing with books caps the case"},
  {"market": "NFL wk7 LAR @ LV (highest Sunday volume)", "side_considered": "LAR 0.645", "reasoned_prob": "LAR ~0.655-0.66 (books LAR -4.5 after Adams OUT 6-10wk absorbed; line moved -5.5 -> -4.5)", "edge_c": "~1 on LAR", "liquidity": "$1.49M event, vol24 $73k", "resolution": "Oct 25", "verdict": "REJECT", "reason": "Adams injury fully absorbed by both books and PM"},
  {"market": "NFL wk7 DAL @ PHI (MNF)", "side_considered": "DAL 0.645", "reasoned_prob": "DAL ~0.65 (Cloudbet 1.46/2.70 devig)", "edge_c": "~0.5", "liquidity": "$1.27M event", "resolution": "Oct 26", "verdict": "REJECT", "reason": "Unchanged from round-12; Hurts IR long priced"},
  {"market": "NFL wk7 KC @ SEA (SNF)", "side_considered": "KC 0.425", "reasoned_prob": "KC ~0.45 (books KC +114/SEA -135)", "edge_c": "~2.5 on KC", "liquidity": "$1.52M event", "resolution": "Oct 25", "verdict": "REJECT", "reason": "Same 2-3c stale gap as round-12; sub-bar"},
  {"market": "NBA POR @ SAC (Fri Oct 23)", "side_considered": "POR 0.725 / SAC 0.275", "reasoned_prob": "POR ~0.698 (books -6.5, ML -225/+233)", "edge_c": "~ -2.5 (PM RICH on POR)", "liquidity": "$1.04M event", "resolution": "Oct 23-24", "verdict": "REJECT", "reason": "Market rich vs books; SAC at 0.275 vs 0.302 devig is a 2.7c value but sub-bar and anti-position-direction"},
  {"market": "NBA DEN @ OKC (Thu night, tips 9:30pm ET)", "side_considered": "OKC 0.735", "reasoned_prob": "OKC ~0.72 (books -8.5, ML -306/-340 -> devig 0.722)", "edge_c": "~ -1.5 (PM slightly RICH on OKC)", "liquidity": "$9.66M event", "resolution": "tonight", "verdict": "REJECT", "reason": "Round-12 pass validated: price drifted 0.745 -> 0.735 toward books, not away; Jokic+Murray OUT fully priced at -8.5"},
  {"market": "NBA NYK @ BOS (Fri Oct 23)", "side_considered": "BOS 0.555", "reasoned_prob": "BOS ~0.562 (books BOS -3, NYK +120)", "edge_c": "~0.5", "liquidity": "$1.33M event", "resolution": "Oct 23-24", "verdict": "REJECT", "reason": "In line"},
  {"market": "NFL wk7 SF @ ATL (Evans Achilles)", "side_considered": "ATL (PM SF 0.585)", "reasoned_prob": "SF ~0.53-0.55 if books moved to SF -1.5/-2 after Mike Evans ruled out", "edge_c": "possibly ~3-4 on ATL, unconfirmed book line", "liquidity": "$1.70M event, vol24 $6.3k (thin flow)", "resolution": "Oct 25", "verdict": "REJECT", "reason": "Evans news 24h+ old, likely absorbed; could not confirm current book line; worst-case gap ~4c < 10c bar"},
  {"market": "NBA CLE @ PHI (live, 4th qtr CLE +8)", "side_considered": "CLE live 0.695", "reasoned_prob": "n/a live", "edge_c": "n/a", "liquidity": "$1.6M", "resolution": "tonight", "verdict": "REJECT", "reason": "Pre-game market had PHI 0.585; CLE up 8 in 4th; no pre-game edge existed at 0.415 CLE per round-12 pass; live chasing not the mandate"},
 ],
 "final_verdict": "PASS - no new positions (13th consecutive clean-ish pass; round-12 near-miss CIN@BAL resolved into a coin flip rather than an edge)",
 "rationale": "Every liquid weekend market sits within ~3c of sportsbook devig. The only >=3c gaps: CAR ~+3c vs books (FPI concurs, sub-bar), KC ~+2.5c (stale), PM rich on POR/OKC (wrong side). Lamar Jackson's GTD status makes CIN@BAL genuinely unpriceable to a 10c conviction; the Sunday-morning inactive list is the next information event, after which in-game prices will absorb it within minutes. WS G1/series within 1-1.5c of books.",
 "por_position": {"action": "HOLD", "mtm": "+6.2% at mid 0.65 (bid 0.64/ask 0.66)", "thesis": "ON TRACK - POR 1-0, Ja+Dame healthy, market re-rated 0.612 -> 0.65"},
}

json.dump(scan, open("/home/ubuntu/paper-sim/round13/raw/ussports_scan.json", "w"), indent=1)
json.dump(cands, open("/home/ubuntu/paper-sim/round13/ussports_candidates.json", "w"), indent=1)
print("written ussports_scan.json and ussports_candidates.json")
