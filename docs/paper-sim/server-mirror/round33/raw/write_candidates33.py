"""Round-33 candidates writer (paper-only). Applies the news-concordance
layer to the scan's numeric passers (scan file: round33/raw/soccer_scan.json).

News evidence gathered 2026-11-04 ~10:55-11:15Z via live web search:
- Lens-Como: Lens WITHOUT Edouard (adductor) + Sima (out to ~Nov 30) +
  Ganiou (knee) + Nawrocki (ACL)  -> news WORSE than the stale-xG model
  direction for Lens-scoring-dependent bets -> ML home and TT O0.5 killed.
- Leipzig-City: City near full strength (Haaland, Foden, Doku, Cherki
  predicted XI; only Semenyo out); no Leipzig-side supporting news found
  -> news UNKNOWN for the model's Leipzig-tilt -> ML home / away_no killed
  per the r29-r32 lineage rule (unknown cannot support candidacy).
- Leverkusen-Marseille: BTTS Yes is the consensus tip (GoonersGuide BTTS
  Yes 1.65; Kalshi O2.5 65%; Sportskeeda Lev win + Over 2.5) -> CONCORDANT.
- Wrexham-Middlesbrough: Forebet 1-2, Wrexham U2.5 in last 4, Boro 1st vs
  Wrexham 18th; Sports Mole 1-3 is the lone 4-goal view -> mildly
  CONCORDANT with Under 3.5.
"""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round33/raw/soccer_scan.json"
OUT = "/home/ubuntu/paper-sim/round33/soccer_candidates.json"
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
scan = json.load(open(SCAN))
board = {((r["fixture_key"], r["kind"], r["side"], r["line"])): r for r in scan["board"]}


def get(fk, kind, side, line):
    return board[(fk, kind, side, line)]


btts = get("leverkusen-marseille", "btts", "yes", None)
u35 = get("middlesbrough-wrexham", "total", "under", 3.5)
om05 = get("leverkusen-marseille", "team_total", "over", 0.5)

candidates = [
    {
        "rank": 1,
        "match": "Bayer 04 Leverkusen vs. Olympique de Marseille",
        "comp": "UEL MD4", "kickoff_utc": "2026-11-05T20:00:00Z",
        "market": "BTTS Yes (id 6091589)",
        "side_bought": "YES", "entry_ask_vwap250": btts["exec_ask_vwap250"],
        "stake_usd": 250,
        "model": "p_med 0.7133 [0.6945-0.7496], 10 bridged variants "
                 "(f=1.0549, Bundesliga vs Ligue_1), lambdas 2.71/1.45",
        "gates": "exec +13.3c (bar 5c, cushion 8.3c); worst +11.5c (cross-"
                 "league bar 5c, cushion 6.5c); var 5.51c (cap 6c, cushion "
                 "0.49c - TIGHTEST GATE); liq $12.9k (2.6x floor); fill_250 "
                 "yes; entry 0.58 in [.10-.92]; under_risk no (min lambda "
                 "1.45>=0.75)",
        "news_concordance": {
            "verdict": "CONCORDANT",
            "evidence": "BTTS Yes is the consensus tip: GoonersGuide BTTS "
                        "Yes @1.65 (~0.61 implied), Kalshi O2.5 65%, "
                        "Sportskeeda Leverkusen win + Over 2.5; Leverkusen "
                        "W3-0-0 / Marseille 0-0-3 in UEL MD1-3",
            "sources": ["goonersguide.com/football-pick-60227",
                        "kalshi.com/markets/kxueltotal-26nov05levolm",
                        "sportsgambler.com leverkusen-marseille 2026-11-05",
                        "sportskeeda.com match preview"],
        },
        "fragility": [
            "var cushion only 0.49c - a single variant moving 0.5c breaks "
            "the var<=6c gate",
            "Big-5 xG base 4 days stale (through Oct-31; Lev/OM league "
            "games Nov 1-3 not absorbed)",
            "model 0.713 vs external implied ~0.61 (GoonersGuide/Kalshi): "
            "true edge plausibly +3..+10c, not +13c",
            "entry ~33h pre-kick: lineups unset; Marseille rotation risk "
            "after 3 UEL losses directly threatens the OM-scores leg",
            "post-window kickoff (Thu 20:00Z > hi Nov-5 10:00Z); entry "
            "placed inside window per r30/r31 interpretation",
        ],
        "exit": "best bid 0.57, bid-VWAP250 0.5641 (exit cost 1.6c)",
    },
    {
        "rank": 2,
        "match": "Wrexham AFC vs. Middlesbrough FC",
        "comp": "Championship (ENG2) MD16", "kickoff_utc": "2026-11-04T19:45:00Z",
        "market": "Under 3.5 goals (id 6039115)",
        "side_bought": "UNDER", "entry_ask_vwap250": u35["exec_ask_vwap250"],
        "stake_usd": 250,
        "model": "p_med 0.7420 [0.7183-0.7638], 10 domestic variants on the "
                 "FotMob Championship snapshot (fresh through Nov-3), "
                 "lambdas 1.05/1.51",
        "gates": "exec +9.2c (bar 5c, cushion 4.2c); worst +6.8c (domestic "
                 "bar 4c, cushion 2.8c); var 4.55c (cushion 1.45c); liq "
                 "$69.7k (14x floor); fill_250 yes; entry 0.65 in window; "
                 "under side not under-risk screened",
        "news_concordance": {
            "verdict": "CONCORDANT (mild)",
            "evidence": "Forebet 1-2 (3 goals, Under 3.5 wins); Wrexham "
                        "matches under 2.5 in last 4; Wrexham 18th (14 pts) "
                        "hosting leaders Middlesbrough (28 pts); Boro wins "
                        "predicted 1-2/1-3",
            "sources": ["forebet.com/en/football/matches/wrexham-fc-middlesbrough-2507178",
                        "sports.yahoo.com preview-wrexham-vs-middlesbrough",
                        "sportsmole.co.uk preview (lone 1-3 contrary view)"],
        },
        "fragility": [
            "FIRST-EVER Championship candidate: WP-P3 FotMob path is 1 day "
            "old in production; walk-forward gate D passed but live-sample "
            "is zero",
            "Sports Mole predicts 1-3 (exactly 4 goals = loss); predicted "
            "scorelines straddle the 3.5 line",
            "kickoff ~8.75h after scan; XIs unset at entry",
            "O/U 3.5 needs total<=3; an early red card or 2-goal first 20 "
            "minutes flips the position",
        ],
        "exit": "best bid 0.64, bid-VWAP250 0.64 (exit cost 1.0c)",
    },
    {
        "rank": 3,
        "match": "Bayer 04 Leverkusen vs. Olympique de Marseille",
        "comp": "UEL MD4", "kickoff_utc": "2026-11-05T20:00:00Z",
        "market": "Marseille team total Over 0.5 (id 6091604)",
        "side_bought": "OVER", "entry_ask_vwap250": om05["exec_ask_vwap250"],
        "stake_usd": 150,
        "stake_note": "reduced to $150: same fixture as candidate 1 (OM "
                      "scoring is a strict subset of BTTS Yes - fully "
                      "correlated downside); deploy 2 candidates only if "
                      "independence is preferred",
        "model": "p_med 0.7641 [0.7525-0.7739] (tightest board var 2.14c)",
        "gates": "exec +11.4c (cushion 6.4c); worst +10.3c (cross bar 5c, "
                 "cushion 5.3c); var 2.14c (cushion 3.86c); liq $8.2k "
                 "(1.6x floor - thinnest of the three); fill_250 yes; "
                 "entry 0.6499 in window",
        "news_concordance": {
            "verdict": "CONCORDANT (via candidate 1 evidence)",
            "evidence": "BTTS-consensus tip implies OM expected to score; "
                        "OM scored in recent league away games (stale base) "
                        "- see candidate 1 sources",
        },
        "fragility": [
            "correlated with candidate 1: OM 0-0 loses BOTH positions",
            "Marseille rotation (0-0-3 in UEL) is the specific kill risk",
            "thin depth: exit bid 0.60 vs ask 0.65 (5c round-trip cost); "
            "depth_2c $2.6k",
            "same 33h-pre-kick lineup uncertainty",
        ],
        "exit": "best bid 0.60, bid-VWAP250 0.60 (exit cost 5.0c)",
    },
]

killed_at_news = [
    {"match": "Racing Club de Lens vs. Como 1907 (UCL MD4, Nov-4 20:00Z)",
     "market": "Lens match-winner Yes (id 6053608; ml/home)",
     "numbers": "p_med 0.431 [0.4038-0.4602] vs ask 0.27; exec +16.1c, "
                "worst +11.4c (>= 5c cross bar OK), var 5.64c, liq $390k - "
                "the largest raw edge on the board and the FIRST-EVER "
                "numeric pass for bridged cross-league MW",
     "news_verdict": "KILLED - news WORSE than model direction",
     "evidence": "Lens missing 4: Edouard (adductor), Sima (dead leg, out "
                 "~Nov 30), Ganiou (knee surgery), Nawrocki (ACL); the "
                 "stale Oct-31 xG base cannot see this; market's 0.26-0.27 "
                 "is plausibly pricing exactly these absences",
     "sources": ["transfermarkt.us/rc-lens/sperrenundverletzungen",
                 "uefa.com MD4 predicted line-ups",
                 "sports.yahoo.com preview-lens-vs-como"]},
    {"match": "RB Leipzig vs. Manchester City FC (UCL MD4, Nov-4 20:00Z)",
     "market": "Leipzig match-winner Yes (ml/home)",
     "numbers": "p_med 0.300 vs ask 0.18; exec +12.0c, worst +10.9c, var "
                "2.61c, liq $354k",
     "news_verdict": "KILLED - news UNKNOWN (cannot support candidacy)",
     "evidence": "City predicted near full strength (Donnarumma; Nunes, "
                 "Khusanov, Guehi, O'Reilly; Anderson, Fernandez; Foden, "
                 "Cherki, Doku; Haaland; only Semenyo out); no Leipzig-side "
                 "supporting news found; the model tilt (bridge f=0.80 "
                 "clamped) leans on stale data",
     "sources": ["yahoo.com city-2026-27 predicted XI"]},
    {"match": "Racing Club de Lens vs. Como 1907",
     "market": "Lens team total Over 0.5 (id 6054089)",
     "numbers": "p_med 0.839 [0.8053-0.8653] vs ask 0.74; exec +9.9c, worst "
                "+8.0c, var 6.00c (exactly at the cap)",
     "news_verdict": "KILLED - same Edouard/Sima absences (attack-reducing "
                     "direction)", "sources": ["as above"]},
    {"match": "RB Leipzig vs. Manchester City FC",
     "market": "Man City NOT to win (ml/away_no)",
     "numbers": "p_med 0.509 vs ask 0.38; exec +6.4c, worst +10.6c, var "
                "4.05c, liq $334k",
     "news_verdict": "KILLED - same unknown-news rule; full-strength City "
                     "XI leans market-side", "sources": ["as above"]},
]

doc = {
    "scan": "soccer", "round": 33, "paper_only": True,
    "generated_utc": now,
    "sub_scan": ("THREE-FIRSTS SCAN: WP-P2a bridge production debut; "
                 "cross-league MW scan-level unban (WP-P2b PASS; T4 "
                 "accumulating 0/20); first Championship model (WP-P3)"),
    "window_utc": {"lo": "2026-11-04T10:00:00Z", "hi": "2026-11-05T10:00:00Z",
                   "note": "UEL Thu evening kickoffs post-window; enterable "
                           "now per r30/r31 interpretation"},
    "library": {"package": "polymarket_alpha_lab.papersim",
                "repo_commit": "19501719", "selfcheck": "10/10 PASS"},
    "bridge": scan["bridge"],
    "bankroll_usd": 12998.34, "cash_usd": 10563.00,
    "max_new_positions": 3,
    "budget_deployed_usd": 650,
    "verdict": (
        "PASS - 3 candidates (all paper): (1) Leverkusen-Marseille BTTS Yes "
        "$250 +13.3c (news-concordant, consensus tip); (2) Wrexham-"
        "Middlesbrough U3.5 $250 +9.2c (first Championship candidate, fresh "
        "Nov-3 FotMob base); (3) Marseille TT O0.5 $150 +11.4c (correlated "
        "with #1, reduced size). The two cross-league MW first-passes "
        "(Lens ML +16.1c, Leipzig ML +12.0c) were KILLED at news-concordance "
        "- Lens missing 4 incl. 2 forwards (Edouard, Sima), City near full "
        "strength - so the T4 cross-league MW settled sample stays 0/20 and "
        "no MW entry is recorded. Bridge compression vs r30 confirmed: "
        "O/U variant spreads 13.2-24.0c (old 18.2-37.4c), reductions "
        "35-64%; four O/U-family rows now clear var<=6c where zero did in "
        "r30/r31; MW spreads 2.6-5.6c."),
    "candidates": candidates,
    "killed_at_news": killed_at_news,
    "flagged_not_entered": [
        "Leipzig-City spread nocover -1.5 +10.9c exec (flagged-only policy; "
        "spreads never entered)",
        "Cardiff-West Ham: event has only ML+spread markets live (12 rows); "
        "no O/U/BTTS to evaluate; ml away (West Ham) p_med 0.345 vs ask 0.50 "
        "fails var (13.95c) - the 1X2 gate-E limitation visible but not "
        "gating anything today",
        "Getafe-Brightton modeled as CROSS(other); gamma tag is "
        "europa-conference-league (UECL) - comp label cosmetic, bridged "
        "cross-league path correct; vol24 $49, no candidate relevance",
        "All 6 non-Big-5 UCL Wed fixtures + 14 of 17 UEL Thu fixtures + "
        "Rennes-Olympiakos remain MODEL-VOID (clubs absent from snapshot "
        "universe; bridge cannot create multipliers for absent clubs); "
        "full prices-only boards captured (58-70 rows each)",
    ],
    "t4_accumulation": {"settled_cross_league_mw_before": 0,
                        "entered_this_round": 0,
                        "settled_after_this_round": 0,
                        "registry_flip_requires": 20},
    "next_action": (
        "Enter the 3 candidates as paper orders at ask-VWAP; recheck books "
        "at ~19:30Z (Championship XIs) and Thu ~16:30Z (UEL XIs) before "
        "kickoffs; UCL MD4 results feed Thursday's r34 scan; recommend "
        "Understat recovery check before r34 (Big-5 base now 4d stale)."),
}
json.dump(doc, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("candidates:", len(candidates), "| killed at news:", len(killed_at_news))
