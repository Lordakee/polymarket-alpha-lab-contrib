import json, shutil, datetime

now = "2026-10-22T12:00:00Z"

# Consolidated raw scan: copy the parsed 45-day summary into politics_scan.json with metadata
shutil.copy("/home/ubuntu/paper-sim/round12/raw/summary_45d.json",
            "/home/ubuntu/paper-sim/round12/raw/politics_scan.json")

scan_meta = {
    "team": "politics/macro/world",
    "round": 12,
    "as_of": now,
    "method": "gamma events pagination, tag_slug in {politics,economics,fed,geopolitics,elections,world,spy}, order=volume24hr, limit=100 each; unique events 297; filtered to endDate <= 2026-12-06 (45d window) -> 158; CLOB books pulled for top candidates",
    "raw_files": ["events_politics.json","events_economics.json","events_fed.json","events_geopolitics.json","events_elections.json","events_world.json","events_spy.json","summary_45d.json","books.json","senate_races.json","spy740.json"],
    "scanned_events_in_window": 158,
    "macro_context": {
        "SPY_close_20261021": 773.09,
        "VIX_close_20261021": 16.68,
        "october_low_zone": "SPY already touched <=760 in October (LOW 760 monthly resolved YES=1.0); current spot ~770-773",
        "iran_war_2026": "US/Israel-Iran war began 2026-02-28; rolling ceasefires since Apr/Pakistan broker; current talks stalled over 7-day extension; Iran stalling to influence US midterms; Hormuz traffic not yet normal; oil >= $85 by Nov 2 priced at ~91%",
        "fed": "FOMC 2026-10-28. Polymarket: no-change 89/90, hike25 10/11, cuts 0. CME FedWatch ~84-86% hold per secondary trackers (Growbeansprout/CentralBank.watch).",
        "midterms": "Nov 3. Generic ballot ~D+6-7. RCP Senate map 46/46 with 8 tossups, D+3 projected; DDHQ favors D sweep; ElectIt (Harvard) D both chambers 83%. Polls: D leads TX(Talarico vs Paxton, +0 to +5), OH, MI, IA(Turek vs Hinson, Marist +3, 7/12 polls D)."
    }
}
json.dump(scan_meta, open("/home/ubuntu/paper-sim/round12/raw/scan_meta.json", "w"), indent=1)

candidates = {
    "team": "politics/macro/world",
    "round": 12,
    "as_of": now,
    "bar": ">=8c edge vs reasoned probability; liquidity >= $25k; resolution <= 45d; max 1 new position <= $250",
    "open_position_mark": {
        "market": "S&P 500 (SPY) hit (LOW) $740 in October (Pyth 1m regular session)",
        "side": "NO",
        "entry": 0.846,
        "size_usd": 249.57,
        "current": {"yes_mid": 0.135, "no_mid": 0.865, "book_yes": "13/14"},
        "unrealized_usd": 5.6,
        "pct": 2.2,
        "distance_to_740": "~30-33 pts (~4.0-4.3%) from spot ~770-773",
        "vix": "16.68 (Oct 21 close)",
        "days_left": "8 trading days (Oct 22-31)",
        "risk": "13.5c YES fairly prices a ~1.4-sigma weekly move incl. event tails (Iran ceasefire breakdown 26% by Oct 31 -> oil gap-down risk; FOMC Oct 28 10% hike tail; earnings). GBM check: P(touch)~14-15% == market. Hold, do not add (book thin, monthly liq ~$1k fails $25k bar; edge ~0 at 86.5c NO)."
    },
    "candidates": [
        {
            "market": "Which party will win the Senate in 2026? (D control)",
            "side_considered": "YES D @ 0.68 (book 67/68)",
            "reasoned_probability": 0.72,
            "edge_c": 4,
            "liquidity": 1791211,
            "resolution": "2026-11-04",
            "reason": "Race-level decomposition (D flips TX .68, OH .72, ME .66, AK .74; holds MI/MN; IA D .44 bonus) gives P(D control) ~70-75% vs market 68; internally consistent with balance-of-power bundle (D Sen 69, D House 92). Edge below 8c bar.",
            "verdict": "PASS"
        },
        {
            "market": "Fed Decision October 2026 - hike 25bps",
            "side_considered": "YES @ 0.11 (book 10/11)",
            "reasoned_probability": 0.145,
            "edge_c": 4,
            "liquidity": 1192773,
            "resolution": "2026-10-28/29",
            "reason": "Secondary FedWatch trackers imply ~14-16% hike vs market 10/11, but sourcing is secondhand and Polymarket is normally at least as sharp as futures on FOMC; no-change 89/90 is deep and liquid. Edge below bar, direction uncertain.",
            "verdict": "PASS"
        },
        {
            "market": "Iowa Senate Election Winner 2026 (Democrats)",
            "side_considered": "YES D @ 0.44",
            "reasoned_probability": 0.47,
            "edge_c": 3,
            "liquidity": 383000,
            "resolution": "2026-11-04",
            "reason": "Marist Turek +3, 7/12 recent polls D; but Kalshi agrees with Polymarket (Hinson 59) because Iowa D polls carry a post-2024-Selzer structural discount and no D statewide win in recent cycles. Edge below bar.",
            "verdict": "PASS"
        },
        {
            "market": "Texas Senate Election Winner 2026 (Democrats - Talarico)",
            "side_considered": "fade? NO D @ 0.32 / buy? YES D @ 0.68",
            "reasoned_probability": 0.62,
            "edge_c": 6,
            "liquidity": 925009,
            "resolution": "2026-11-04",
            "reason": "No poll shows Paxton leading (Fox 49-49, CBS +5 D, Cook +5 D) yet market is 68 D; Texas 2024 polling missed ~4-5 pts R (Cruz +8.6 vs polled +4), so 68 embeds a defensible bias correction. Two-sided uncertainty; fading a 68 in the year's highest-volume race on poll-bias priors alone does not clear 8c confidence.",
            "verdict": "PASS"
        },
        {
            "market": "US x Iran ceasefire continues through October 31",
            "side_considered": "YES @ 0.74 (book 72/74)",
            "reasoned_probability": 0.78,
            "edge_c": 4,
            "liquidity": 163289,
            "resolution": "2026-10-31",
            "reason": "Iran is deliberately stalling talks to influence the Nov 3 midterms and US is reducing troop footprint - both argue for muddle-through past Oct 31. But genuine breakdown risk (bombing-campaign fears, Hormuz sequencing dispute) plus resolution ambiguity on 'continues' during a stalled-extension window triggers the 50-50 haircut discipline; edge after haircut below bar.",
            "verdict": "PASS"
        },
        {
            "market": "Brazil Presidential Election (Flavio Bolsonaro to win)",
            "side_considered": "NO FB @ 0.78 (i.e., Lula YES 22)",
            "reasoned_probability": 0.76,
            "edge_c": 2,
            "liquidity": 1264584,
            "resolution": "2026-10-25/26",
            "reason": "Runoff polls are a statistical tie (FB 46.5-46.8 vs Lula 45.9), but Brazilian pollsters have a persistent pro-Lula bias (2022 runoff: polled Lula +4, actual +1.8); market's 78 correctly embeds ~3-4pt bias correction. No edge.",
            "verdict": "PASS"
        }
    ],
    "verdict": "PASS - no new position. Midterm complex is internally consistent (BoP bundle = sum of parts; race prices = control prices; Kalshi agrees where checkable). Fed market slightly MORE confident on hold than futures. Best near-miss: Senate D control YES @ 0.68 vs ~0.72 reasoned (4c edge, below 8c bar)."
}

json.dump(candidates, open("/home/ubuntu/paper-sim/round12/politics_candidates.json", "w"), indent=1)
print("written: politics_candidates.json + raw/politics_scan.json + raw/scan_meta.json")
