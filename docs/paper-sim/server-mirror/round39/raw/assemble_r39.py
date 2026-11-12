"""ROUND-39B assembler: merge pass1 + pass2 boards, write unified raw board
and the americas_candidates.json decision file.

Board-only outcome by construction: zero in-scope league has model coverage
(FotmobLeague = Championship+Eredivisie; xG snapshot = Big-5), so there are
no model probabilities, no gate arithmetic, and NO entries. Every row is
labeled NO MODEL COVERAGE - report only, no entry.

Paper only. No DB writes, no credentials, no orders.
"""
import json
import re
import unicodedata
from datetime import datetime, timezone

HOME = "/home/ubuntu/paper-sim"
RAW = f"{HOME}/round39/raw"
LO = "2026-11-06T13:30:00Z"
HI = "2026-11-08T23:59:59Z"
NOW = datetime.now(timezone.utc)


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def base_of(title):
    return re.split(r"\s+-\s+", title or "", maxsplit=1)[0]


def fkey(kick, title):
    b = strip_accents(base_of(title).lower())
    b = re.sub(r"[^a-z0-9]", "", b)
    return kick + "|" + b


def parse_ts(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def main():
    p1 = json.load(open(f"{RAW}/americas_scan.json"))
    try:
        p2 = json.load(open(f"{RAW}/americas_scan_pass2.json"))
    except FileNotFoundError:
        p2 = None

    fixtures = {}

    def add_fixture(kick, match, league, source):
        key = fkey(kick, match)
        fx = fixtures.setdefault(key, {
            "match": match, "kickoff_utc": kick, "league": league,
            "league_source": source, "rows": [], "event_ids": [],
            "knockout_competition": False})
        if league and league not in (fx["league"],):
            # prefer the more specific tag-derived league from pass 2
            if source == "pass2-tag":
                fx["league"], fx["league_source"] = league, source
        return fx

    # pass 1: per-event boards -> regroup into fixtures
    for b in p1.get("scope_fixtures", []):
        fx = b["fixture"]
        entry = add_fixture(fx["kickoff_utc"], base_of(fx["title"] or ""),
                            fx.get("league"), "pass1-espn/mixmap")
        entry["event_ids"].append(fx["event_id"])
        for r in b.get("rows", []):
            if r["market_id"] not in [x["market_id"] for x in entry["rows"]]:
                entry["rows"].append(r)

    # pass 2: already fixture-shaped
    if p2:
        for b in p2.get("board", []):
            fx = b["fixture"]
            entry = add_fixture(fx["kickoff_utc"], fx["match"],
                                fx["league"], "pass2-tag")
            entry["event_ids"].extend(fx.get("event_ids", []))
            entry["knockout_competition"] = fx.get("knockout_competition",
                                                   entry["knockout_competition"])
            for r in b.get("rows", []):
                if r["market_id"] not in [x["market_id"] for x in entry["rows"]]:
                    entry["rows"].append(r)

    board = []
    for fx in fixtures.values():
        fx["rows"] = sorted(fx["rows"], key=lambda r: -r.get("liq_gamma_usd", 0))
        fx["total_liq_usd"] = round(
            sum(r.get("liq_gamma_usd", 0) for r in fx["rows"]), 2)
        fx["n_markets"] = len(fx["rows"])
        kt = parse_ts(fx["kickoff_utc"])
        fx["kickoff_status_at_scan"] = (
            "ALREADY KICKED (in window, historical board)" if kt and kt < NOW
            else "upcoming")
        board.append(fx)
    board.sort(key=lambda f: (f["kickoff_utc"], f["match"]))

    # league counts + coverage table
    league_counts = {}
    for fx in board:
        league_counts[fx["league"]] = league_counts.get(fx["league"], 0) + 1

    verifications = list(p1.get("market_verifications", []))
    rules = list(p1.get("playoff_rules_evidence", []))
    if p2:
        verifications += p2.get("market_verifications", [])
        rules += p2.get("playoff_rules_evidence", [])

    n_ok = sum(1 for v in verifications if v.get("ok"))
    n_closed = sum(1 for v in verifications if v.get("ok") and v.get("closed"))
    n_kick_ok = sum(1 for v in verifications
                    if v.get("ok") and v.get("kickoff_matches_event") is True)
    n_end_ok = sum(1 for v in verifications
                   if v.get("ok") and v.get("endDate_after_kick_within_30h") is True)

    out = {
        "round": 39, "scan": "americas-row-48h", "paper_only": True,
        "generated_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI},
        "execution_note": (
            "dispatch window Fri 13:30Z..Sun 23:59Z; scan executed "
            f"{NOW.strftime('%Y-%m-%dT%H:%MZ')} (post-round-38 queue), so Friday "
            "fixtures had already kicked and their boards are historical; "
            "Sat/Sun fixtures were pre-kick"),
        "coverage_verdict": p1.get("coverage_verdict"),
        "provenance": p1.get("provenance"),
        "pass2_note": (p2 or {}).get("note"),
        "tag_inventory_soccer_window": p1.get("tag_inventory_soccer_window"),
        "espn_fixtures": p1.get("espn_fixtures"),
        "fixtures_by_league": league_counts,
        "board_fixtures": board,
        "market_verifications": verifications,
        "verification_summary": {
            "verified_markets": len(verifications), "ok": n_ok,
            "closed_true_found": n_closed,
            "kickoff_matches_event": n_kick_ok,
            "endDate_after_kick_within_30h": n_end_ok},
        "playoff_rules_evidence": rules,
    }
    json.dump(out, open(f"{RAW}/americas_scan.json", "w"), indent=1)
    print("unified board:", len(board), "fixtures;",
          sum(f["n_markets"] for f in board), "rows ->", f"{RAW}/americas_scan.json")

    # ---------------- candidates file ----------------
    nm = sorted(set(fx["league"] for fx in board))
    # playoff rules summary: group knockout-league rules evidence by match
    playoff_notes = [{
        "finding": ("MLS: NOT playoffs this window - Sat 2026-11-07 is Decision "
                    "Day, the regular-season finale (all games 90-minute results; "
                    "playoffs begin after Decision Day; MLS Cup Final Dec 11-12). "
                    "Verified via MLSsoccer.com schedule announcement. The "
                    "dispatch's playoff caveat is therefore moot for every MLS "
                    "market in this window."),
        "source": "https://www.mlssoccer.com/news/mls-announces-2026-regular-season-schedule",
    }, {
        "finding": ("Copa do Brasil: the ONLY knockout competition in scope - "
                    "semifinal SECOND LEGS: Atletico-Mineiro vs Gremio (Sat "
                    "2026-11-07 21:00Z, Arena MRV; 1st leg Gremio home Nov-1) and "
                    "Vasco da Gama vs Palmeiras (Sun 2026-11-08 20:00Z, Sao "
                    "Januario; 1st leg Palmeiras home Nov-1). Aggregate-score "
                    "ties: any 90-min model probability would NOT be comparable "
                    "to an advance/win market without the draw->advancement "
                    "split. Moot this round: no model coverage exists, so these "
                    "markets stay report-only; per-market rules text captured in "
                    "playoff_rules_evidence."),
        "source": "ge.globo.com / CBF schedule (semifinal legs confirmed Nov 7-8)",
    }]
    for r in rules:
        if r.get("league") == "Copa do Brasil":
            playoff_notes.append({
                "market_id": r.get("market_id"), "question": r.get("question"),
                "kickoff_utc": r.get("kickoff_utc"),
                "rules_hits": r.get("rules_hits")})
    n_rule_mkts = sum(1 for r in rules if r.get("league") == "Copa do Brasil")

    cand = {
        "round": 39,
        "scan": "soccer-weekend-americas-row",
        "paper_only": True,
        "generated_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI},
        "decision": (
            "ENTER NOTHING. Zero of the in-scope leagues (MLS, Brasileirao "
            "Serie A/B, Copa do Brasil, Liga MX, Argentina Primera, Saudi Pro "
            "League, J-League, A-League, K-League, and the other Americas/ROW "
            "leagues found) are covered by the papersim FotMob adapter "
            "(FotmobLeague = Championship, Eredivisie only) or the Big-5 xG "
            "snapshot. Per the dispatch coverage rule this scan is BOARD-ONLY: "
            "no ratings were fabricated, no model probabilities exist, so the "
            "frozen gates (net>=+5c fee-aware etc.) cannot be evaluated for any "
            "market. Every board row is labeled 'NO MODEL COVERAGE - report "
            "only, no entry'. Proposed stake: $0 of the <=$150 scan budget; the "
            "$200 remaining weekend cap is untouched for agent A."),
        "decision_rationale": (
            "Full Fri-Sun window enumeration (8 Gamma sweeps + 32 per-tag "
            "sweeps; 1262+ open soccer events in window) cross-checked against "
            "ESPN for MLS/Brasileirao/Liga MX/Argentina/Saudi/J-League/A-League/"
            "CONMEBOL. In-scope leagues found: " + ", ".join(nm) + ". The "
            "dispatch's playoff caveat proved moot for MLS: Sat Nov-7 is "
            "Decision Day (regular-season finale; playoffs start after Nov-7, "
            "MLS Cup Final Dec 11-12). The ONLY knockout games in scope are the "
            "two Copa do Brasil semifinal SECOND LEGS (Mineiro-Gremio Sat "
            "21:00Z, Vasco-Palmeiras Sun 20:00Z; aggregate ties) - rules text "
            "captured in playoff_rules_evidence. No held fixture (#62-#68) is "
            "in this scan's leagues."),
        "max_new_positions": 0,
        "positions_used": 0,
        "stake_per_position_usd": None,
        "weekend_budget_note": (
            "$0 used by this scan; remaining weekend cap $200 (agents A+B) "
            "untouched; this sub-scan was allowed up to $150"),
        "bankroll_usd": 13409.0,
        "cash_usd": 11923.0,
        "bankroll_note": ("per round38 candidates file (no ledger read/written "
                          "in this scan; paper only)"),
        "open_positions": 7,
        "open_positions_note": (
            "held fixtures per dispatch: #62 Sevilla-Alaves, #63 ManUtd-Villa, "
            "#64 Mainz-Bayern, #65 Osasuna-Athletic, #66 Valencia-RealMadrid, "
            "#67 LeMans-Monaco, #68 Brest-Lyon - all European, none in this "
            "scan's scope"),
        "new_candidates": [],
        "killed_candidates": [],
        "no_model_coverage": {
            "leagues": nm,
            "fixtures_total": len(board),
            "reason": ("FotmobLeague enum covers only Championship(48) and "
                       "Eredivisie(57); understat_latest.json -> Big-5 blocks "
                       "only. Domestic pairs within these leagues cannot be "
                       "modeled either because the league itself has no xG "
                       "snapshot. Adding a league requires a verified FotMob id "
                       "+ validated adapter run recorded in the enum lineage "
                       "(library change, out of scan scope)."),
        },
        "playoff_rule_notes": playoff_notes,
        "playoff_rules_markets_captured": n_rule_mkts,
        "scoreline_concordance_rule_r32": "not applicable - no candidates",
        "data_quality_flags": {
            "execution_slip": (
                "dispatch window began Fri 13:30Z but scan executed "
                f"{NOW.strftime('%Y-%m-%dT:%MZ')} (post-round-38 queue): Friday "
                "fixtures (Brasileirao Vitoria-Fluminense, 5 Argentina Primera "
                "games, Fri Liga MX games, A-League Sydney-CCM) had already "
                "kicked; their boards are post-kick/historical. Sat/Sun boards "
                "are pre-kick."),
            "sweep_pagination_cap": (
                "pass-1 date/tag sweeps each hit the 1000-event pagination cap; "
                "pass 2 re-enumerated by exact tag slug (32 tags) for complete "
                "per-league coverage. Some cross-check discrepancies possible "
                "for events outside all swept tags."),
            "wrong_slug_guess_pass1": (
                "pass-1 LEAGUE_TAG_MAP guessed slugs ('liga-mx', 'brasileirao', "
                "'argentina-primera') that do not exist; actual slugs are 'mex', "
                "'brazil-serie-a', 'arg', etc. Pass-1 classification survived "
                "via ESPN cross-match; pass 2 fixed classification by tag."),
            "womens_leagues_excluded": (
                "NWSL ('soccer-nwsl', 10 events) and WSL ('wsl', 6 events) "
                "excluded as women's soccer (r38 precedent)."),
            "europe_excluded_here": (
                "European tags (fa-cup, EPL, championship, la-liga, sea=Serie A "
                "Italy, nls/nln=England non-league, etc.) belong to agent A/B "
                "scans; Russia ('rus') and Israel treated as Europe/UEFA and "
                "excluded from this ROW scan."),
            "ligamx_listings": (
                "Gamma Liga MX listings in window: Atlas-Pachuca, "
                "Toluca-Monterrey confirmed with main events; Tigres-Cruz Azul "
                "and Pumas-America appear via pass-2 tag sweep (mex) if listed; "
                "San Luis-Juarez and Necaxa-Tijuana were NOT found as open "
                "events in any sweep (either unlisted or beyond caps at pass-1 "
                "time; pass-2 mex sweep is authoritative)."),
            "kickoff_status_in_rows": (
                "each board fixture carries kickoff_status_at_scan; books for "
                "already-kicked games reflect in-play/post-match state and are "
                "NOT entry evidence"),
            "pass2b_books_skipped": (
                "pass 2 was killed in its book phase (404 tokens retried 6x by "
                "the shared get() helper = ~42s each); pass2b re-ran "
                "classification/board/verification with CLOB books SKIPPED. "
                "CLOB walks for the major leagues come from pass 1; a 30-row "
                "spot-check of key books (Copa do Brasil ML, Tigres/Pumas, "
                "Saudi anomaly) is in round39/raw/keybooks_spotcheck.json"),
            "al_hilal_cancellation_anomaly": (
                "Al Ettifaq vs Al Hilal (Sat 14:30Z): CLOB-verified draw YES "
                "0.989/0.994, Al Hilal win YES 0.005/0.012, Ettifaq win YES "
                "0.008 - market prices near-certain CANCELLED-with-no-make-up "
                "(Polymarket draw markets resolve YES on cancellation). Not a "
                "normal fixture; report-only regardless."),
            "friday_games_absent": (
                "Friday fixtures (Argentina x5, Liga MX San Luis-Juarez + "
                "Necaxa-Tijuana, Brasileirao Vitoria-Fluminense, A-League "
                "Sydney-CCM, Saudi Friday trio) are mostly absent from the "
                "open-event board: finished and resolved (closed=true) by scan "
                "time, or in-play. ESPN cross-check confirmed they existed; "
                "pass-1 board retains whatever remained open."),
        },
        "flagged_not_enterable": [
            {"match": "CA Mineiro vs. Grêmio FBPA", "league": "Copa do Brasil",
             "kickoff_utc": "2026-11-07T21:00:00Z",
             "note": ("semifinal 2nd leg (agg tie); board-only - no model "
                      "coverage. ML 0.61/0.62, draw 0.22/0.24, Grêmio 0.15/0.17; "
                      "books live (depth_2c $1.2k-6.6k). Report only.")},
            {"match": "CR Vasco da Gama vs. SE Palmeiras", "league": "Copa do Brasil",
             "kickoff_utc": "2026-11-08T20:00:00Z",
             "note": ("semifinal 2nd leg (agg tie); board-only. Vasco 0.34/0.36, "
                      "Palmeiras 0.35/0.36, draw 0.29/0.30; thin books "
                      "(depth_2c $0.3-0.8k). Report only.")},
            {"match": "Inter Miami CF vs. Charlotte FC", "league": "MLS",
             "kickoff_utc": "2026-11-07T21:00:00Z",
             "note": ("Decision Day; board-only. Miami ML 0.71 ask, $250 walk "
                      "0.71 filled; Charlotte 0.15, draw 0.17. Report only.")},
            {"match": "Tigres de la UANL vs. CF Cruz Azul", "league": "Liga MX",
             "kickoff_utc": "2026-11-08T01:00:00Z",
             "note": ("board-only. Cruz Azul 0.47, Tigres 0.28, draw 0.26; "
                      "healthy books (depth_2c $2.7-9.4k). Report only.")},
            {"match": "Al Ettifaq Saudi Club vs. Al Hilal Saudi Club",
             "league": "Saudi Pro League",
             "kickoff_utc": "2026-11-07T14:30:00Z",
             "note": ("CANCELLATION-PRICED anomaly: draw YES ~0.99 (draw "
                      "resolves YES if canceled with no make-up); win sides "
                      "~0.01. Do not treat as a soccer result market. Report "
                      "only.")},
        ],
        "library": {
            "package": "polymarket_alpha_lab.papersim",
            "repo_commit": "5bdae2e3",
            "selfcheck": "PASS 10/10 (re-run 2026-11-06 pre-scan)",
            "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
            "note": ("only gates.walk_book (pure book math) used; no model "
                     "functions invoked because no in-scope league is modelable"),
        },
        "scan_source": (
            "round39/raw/americas_scan.json (unified) + americas_scan_pass2b.json"
            " + copadobrasil_rules.json (184 knockout-market rules texts) + "
            "keybooks_spotcheck.json (30 CLOB rows) + espn_fixtures_r39_americas.json"),
    }
    json.dump(cand, open(f"{HOME}/round39/americas_candidates.json", "w"), indent=1)
    print("wrote", f"{HOME}/round39/americas_candidates.json")

    # console fixture table for the report
    print("\nFIXTURE TABLE (league | kickoffZ | match | rows | liq | status):")
    for fx in board:
        print("  %-24s %s %-44s %3d %10s %s" % (
            str(fx["league"])[:24], fx["kickoff_utc"][5:16],
            fx["match"][:44], fx["n_markets"], fx["total_liq_usd"],
            "KICKED" if fx["kickoff_status_at_scan"].startswith("ALREADY") else "pre"))


if __name__ == "__main__":
    main()
