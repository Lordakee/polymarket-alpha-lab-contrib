import json, glob, os, subprocess

RAWD = "/home/ubuntu/paper-sim/round12/raw"

# --- WS champion books (missed earlier) ---
champ_tokens = {
 "WS_champ_Rays_YES": "47619537154464827225570738666275423513741144464229940374555699932743034295206",
 "WS_champ_Brewers_YES": "68495273029336552259622116656826978391613637593537133254546205487243272235948",
}
champ_books = {}
for k, t in champ_tokens.items():
    out = subprocess.run(["curl", "-s", "https://clob.polymarket.com/book?token_id=%s" % t],
                         capture_output=True, text=True, timeout=20).stdout
    try:
        b = json.loads(out)
        bids = sorted([(float(x["price"]), float(x["size"])) for x in b.get("bids", [])], reverse=True)
        asks = sorted([(float(x["price"]), float(x["size"])) for x in b.get("asks", [])])
        champ_books[k] = {"bb": bids[0][0] if bids else None, "ba": asks[0][0] if asks else None,
                          "top_bids": bids[:3], "top_asks": asks[:3]}
    except Exception as e:
        champ_books[k] = {"error": str(e)}
json.dump(champ_books, open(RAWD + "/books/ws_champ_books.json", "w"), indent=1)
print(json.dumps(champ_books, indent=1))

# --- scan summary ---
counts = {"nba": {"events_scanned": 109, "in_7d_window": 56},
          "nfl": {"events_scanned": 400, "in_7d_window": 74},
          "mlb": {"events_scanned": 51, "in_7d_window": 11}}

scan = {
  "team": "us-sports", "round": 12, "scan_time_utc": "2026-10-22T12:00Z",
  "window": "2026-10-22 .. 2026-10-29",
  "method": "gamma events/pagination tag_slug={nba,nfl,mlb} closed=false, 4 pages each, tag-filtered client-side; CLOB books via curl; sportsbook cross-check via web search",
  "raw_files": sorted(os.path.basename(p) for p in glob.glob(RAWD + "/*_p*.json")),
  "counts": counts,
  "games_checked_in_detail": [
    "NBA: CLE@PHI (10/22), DEN@OKC (10/22), POR@SAC (10/23), NYK@BOS (10/23)",
    "NFL wk7: CIN@BAL, SF@ATL, CLE@TEN, KC@SEA, GB@DET, TB@CAR, DAL@PHI, PIT@NO, LAR@LV, IND@MIN, NYG@HOU",
    "MLB WS: Rays-Brewers champion + Game 1",
  ],
  "position_check": {
    "market": "POR Trail Blazers make 2027 playoffs",
    "side": "YES", "cost": 369.65, "entry": 0.612,
    "shares": round(369.65 / 0.612, 1),
    "gamma_price": 0.655, "clob_bid": 0.64, "clob_ask": 0.66, "mid": 0.65,
    "mtm_value": round((369.65 / 0.612) * 0.65, 2),
    "unrealized": round((369.65 / 0.612) * 0.65 - 369.65, 2),
    "liquidity_note": "thin: ~$334 bid / $264 ask within 5c of top; soft mark",
    "thesis": "Ja Morant in starting lineup alongside returning Damian Lillard (NBA.com/ESPN/Blazersedge previews); market agrees, price up 61.2->65.5; thesis intact, no action",
  },
}
json.dump(scan, open("/home/ubuntu/paper-sim/round12/raw/ussports_scan.json", "w"), indent=1)

candidates = {
  "round": 12, "generated_utc": "2026-10-22T12:00Z",
  "bar": ">=10c edge vs reasoned probability (anchored to sportsbook devig), liquidity >= $10k, resolution <= 14d preferred, max 1 new position <= $200",
  "candidates_evaluated": [
    {
      "market": "MLB World Series Champion 2026 (Rays vs Brewers set)",
      "side_considered": "Rays YES @ 0.37 (ask 0.371)",
      "reasoned_prob": "0.37-0.40",
      "edge_c": "0 to +3",
      "liquidity": "$311k (gamma) / deep book",
      "resolution": "by Oct 31",
      "verdict": "REJECT",
      "reason": "Books: MIL -165/-180, Rays +145/+148 -> devig Rays ~37-40%; Polymarket exactly in line despite 1v1 seeds (MIL home field, rested dominant bullpen, Rays' rotation taxed by 5-game ALCS)",
    },
    {
      "market": "WS Game 1: Rays @ Brewers (Oct 23)",
      "side_considered": "Rays 0.405 / Brewers 0.595",
      "reasoned_prob": "Rays ~0.40 (books ML -161/+133)",
      "edge_c": "~0",
      "liquidity": "$729k",
      "resolution": "Oct 23",
      "verdict": "REJECT",
      "reason": "Rasmussen vs Misiorowski; devig book price matches market within 1c",
    },
    {
      "market": "NBA DEN @ OKC (Oct 22, tonight)",
      "side_considered": "Denver 0.26 / OKC 0.745",
      "reasoned_prob": "OKC ~0.75 (Jokic OUT wrist + Murray OUT shoulder)",
      "edge_c": "~0",
      "liquidity": "$222k, 1c spread",
      "resolution": "Oct 22-23",
      "verdict": "REJECT",
      "reason": "Both Denver stars ruled out; 0.745 for home OKC is fair-to-cheap; no value side at these prices",
    },
    {
      "market": "NBA CLE @ PHI (Oct 22, tonight)",
      "side_considered": "PHI 0.585 / CLE 0.415",
      "reasoned_prob": "unclear; hinges on Allen/Mitchell GTD",
      "edge_c": "unknown, < 10c",
      "liquidity": "$176k",
      "resolution": "Oct 22-23",
      "verdict": "REJECT",
      "reason": "Garland out, Allen GTD (patellar), Mitchell iffy vs Embiid-risk Sixers at home; no confident >=10c case either way before injury clarity",
    },
    {
      "market": "NFL wk7 CIN @ BAL (Oct 25)",
      "side_considered": "CIN 0.52 / BAL 0.48",
      "reasoned_prob": "CIN ~0.53-0.55 (books flipped to CIN -1.5 on Lamar ankle; Huntley pricing)",
      "edge_c": "~+2 on CIN",
      "liquidity": "$97k, 1c spread",
      "resolution": "Oct 25",
      "verdict": "REJECT",
      "reason": "Lamar limited Wed with limp; books CIN -1.5 vs market 0.52 -> only ~2-3c; BAL 3-1 in Huntley starts since 2025 caps the case; below 10c bar",
    },
    {
      "market": "NFL wk7 DAL @ PHI (Mon Oct 26)",
      "side_considered": "DAL 0.645",
      "reasoned_prob": "DAL ~0.66-0.68 (Hurts out for season - blood clots; Cloudbet DAL 1.46/PHI 2.70)",
      "edge_c": "~+2",
      "liquidity": "$100k",
      "resolution": "Oct 26",
      "verdict": "REJECT",
      "reason": "Hurts loss already priced; Cowboys have their own injuries ('could be without two key players'); ~2c edge below bar",
    },
    {
      "market": "NFL wk7 KC @ SEA (Oct 25)",
      "side_considered": "KC 0.425",
      "reasoned_prob": "KC ~0.45 (books KC +114/SEA -135)",
      "edge_c": "~+2.5 on KC",
      "liquidity": "$74k",
      "resolution": "Oct 25",
      "verdict": "REJECT",
      "reason": "FPI even favors KC slightly; market 2.5c below book devig; sub-bar",
    },
    {
      "market": "NBA POR @ SAC (Oct 23)",
      "side_considered": "POR 0.715",
      "reasoned_prob": "POR ~0.70-0.72 (books POR -6.5, ML -225/-258)",
      "edge_c": "~0",
      "liquidity": "$74k",
      "resolution": "Oct 23",
      "verdict": "REJECT",
      "reason": "Ja+Dame hype fully priced; books agree within 1-2c (a StatSniper 'SAC -19.5' figure was investigated and found to be AI-model garbage, not a market line)",
    },
    {
      "market": "Giants Week 7 Starting QB (Winston 0.495/McCarthy 0.495)",
      "side_considered": "n/a",
      "reasoned_prob": "n/a",
      "edge_c": "n/a",
      "liquidity": "$2.3 (FAILS >= $10k bar)",
      "resolution": "Oct 25",
      "verdict": "REJECT",
      "reason": "Interesting news market but liquidity ~$2; untradeable at required size",
    },
  ],
  "final_verdict": "PASS - no new positions",
  "rationale": "All 15+ high-volume markets checked sit within 1-3c of sportsbook devig; no >=10c edge found without a model. Forced bets worse than clean pass, consistent with rounds 1-11.",
}
json.dump(candidates, open("/home/ubuntu/paper-sim/round12/ussports_candidates.json", "w"), indent=1)
print("scan + candidates written")
