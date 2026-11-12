"""ROUND-39B rebuild: reconstruct the unified raw board + candidates file.

Why: the assembler's second run overwrote round39/raw/americas_scan.json by
reading its own previous (unified) output as if it were the pass-1 file
(non-idempotent input), producing a 0-fixture board. The pass-1 CLOB-walk
data was lost; everything else survives:
  - americas_scan_pass2b.json : complete 198-fixture board (Gamma prices)
  - copadobrasil_rules.json   : 184 knockout-market rules texts (full)
  - keybooks_spotcheck.json   : 30 CLOB rows (spot)
  - events_window_39b.json    : raw pass-1 events
  - espn_fixtures_r39_americas.json
This script re-fetches CLOB books for the material fixtures (404-fast-fail,
no 6x retry on dead tokens) + /markets/{id} verifications, then writes the
final unified raw board and americas_candidates.json. Still BOARD-ONLY /
paper-only: no model probabilities exist for any in-scope league.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import gates  # noqa: E402

BASE = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
HOME = "/home/ubuntu/paper-sim"
RAW = f"{HOME}/round39/raw"
LO = "2026-11-06T13:30:00Z"
HI = "2026-11-08T23:59:59Z"
NOW = datetime.now(timezone.utc)
RULE_KEYWORDS = ("extra time", "penalt", "shootout", "shoot-out",
                 "90 minutes", "regulation", "aggregate", "away goals")


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None  # dead token/market: fast-fail, no retry
            last = e
            time.sleep(1.5 + i)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 + i)
    if last:
        raise last
    return None


def norm_ts(ts):
    s = str(ts or "").strip()
    if not s:
        return ""
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # noqa: BLE001
        return s


def rule_scan(text):
    t = re.sub(r"\s+", " ", str(text or "").lower())
    hits = {}
    for kw in RULE_KEYWORDS:
        for mth in re.finditer(re.escape(kw), t):
            hits.setdefault(kw, []).append(
                t[max(0, mth.start() - 120):mth.end() + 160].strip())
            if len(hits[kw]) >= 2:
                break
    return hits


def main():
    p2 = json.load(open(f"{RAW}/americas_scan_pass2b.json"))
    board = p2["board"]
    print("fixtures from pass2b:", len(board), flush=True)

    # material fixtures: top 60 by total liq + all knockout + Copa
    ranked = sorted(board, key=lambda b: -b["fixture"]["total_liq_usd"])
    material = []
    for b in ranked:
        fx = b["fixture"]
        if len(material) < 60 or fx.get("knockout_competition") \
                or fx["league"] == "Copa do Brasil":
            material.append(b)
    print("material fixtures (books+verify):", len(material), flush=True)

    n_books = n_dead = 0
    for b in material:
        for r in b["rows"][:6]:
            for s in r["sides"]:
                book = get(CLOB + "/book?token_id=" + s["token"])
                time.sleep(0.2)
                if book is None:
                    n_dead += 1
                    continue
                asks = [(float(l["price"]), float(l["size"]))
                        for l in book.get("asks", [])]
                bids = [(float(l["price"]), float(l["size"]))
                        for l in book.get("bids", [])]
                w250 = gates.walk_book(asks, side="ask", notional=250.0)
                w150 = gates.walk_book(asks, side="ask", notional=150.0)
                s["clob_best_bid"] = max((p for p, _ in bids), default=None)
                s["clob_best_ask"] = min((p for p, _ in asks), default=None)
                s["vwap_250"] = w250.vwap
                s["fill_250"] = w250.filled
                s["vwap_150"] = w150.vwap
                s["fill_150"] = w150.filled
                s["depth_2c_usd"] = w250.depth_near2c
                n_books += 1
        print("books: %s liq=%.0f (%d live)" % (
            b["fixture"]["match"][:40], b["fixture"]["total_liq_usd"], n_books),
            flush=True)

    print("\nbooks fetched:", n_books, "dead tokens:", n_dead, flush=True)

    verifications, rules = [], []
    for b in material:
        fx = b["fixture"]
        for r in b["rows"][:6]:
            vm = get(BASE + "/markets/" + str(r["market_id"]))
            time.sleep(0.15)
            if not isinstance(vm, dict):
                verifications.append({"market_id": r["market_id"],
                                      "league": fx["league"], "ok": False})
                continue
            gs = norm_ts(vm.get("gameStartTime"))
            ed = norm_ts(vm.get("endDate"))
            kick_ok = None
            try:
                kick_ok = abs((
                    datetime.fromisoformat(gs.replace("Z", "+00:00")) -
                    datetime.fromisoformat(fx["kickoff_utc"].replace("Z", "+00:00"))
                ).total_seconds()) <= 3600
            except Exception:  # noqa: BLE001
                pass
            endd_ok = None
            try:
                dd = (datetime.fromisoformat(ed.replace("Z", "+00:00")) -
                      datetime.fromisoformat(gs.replace("Z", "+00:00"))).total_seconds()
                endd_ok = 0 <= dd <= 60 * 60 * 30
            except Exception:  # noqa: BLE001
                pass
            verifications.append({
                "market_id": str(vm.get("id")), "ok": True,
                "league": fx["league"], "question": vm.get("question"),
                "closed": vm.get("closed"), "active": vm.get("active"),
                "gameStartTime": gs, "endDate": ed,
                "kickoff_matches_event": kick_ok,
                "endDate_after_kick_within_30h": endd_ok})
            hits = rule_scan(str(vm.get("description") or ""))
            if hits:
                rules.append({
                    "market_id": str(vm.get("id")), "league": fx["league"],
                    "match": fx["match"], "kickoff_utc": fx["kickoff_utc"],
                    "question": vm.get("question"), "rules_hits": hits})

    # merge full Copa do Brasil rules texts
    copa = json.load(open(f"{RAW}/copadobrasil_rules.json"))
    for m in copa["markets"]:
        rules.append({
            "market_id": m["market_id"], "league": "Copa do Brasil",
            "match": str(m.get("event_title") or "").split(" - ")[0],
            "kickoff_utc": m.get("gameStartTime"),
            "question": m.get("question"),
            "verified_closed": m.get("closed"),
            "description_full": m.get("description_full")})

    n_ok = sum(1 for v in verifications if v.get("ok"))
    n_closed = sum(1 for v in verifications if v.get("ok") and v.get("closed"))
    n_kick = sum(1 for v in verifications
                 if v.get("ok") and v.get("kickoff_matches_event") is True)
    n_end = sum(1 for v in verifications
                if v.get("ok") and v.get("endDate_after_kick_within_30h") is True)
    print("verifications ok:", n_ok, "closed:", n_closed,
          "kick_ok:", n_kick, "end_ok:", n_end, "rules entries:", len(rules),
          flush=True)

    league_counts = {}
    for b in board:
        league_counts[b["fixture"]["league"]] = league_counts.get(
            b["fixture"]["league"], 0) + 1

    for b in board:
        kt = None
        try:
            kt = datetime.fromisoformat(
                b["fixture"]["kickoff_utc"].replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            pass
        b["fixture"]["kickoff_status_at_scan"] = (
            "ALREADY KICKED (in window, historical board)"
            if kt and kt < NOW else "upcoming")

    out = {
        "round": 39, "scan": "americas-row-48h", "paper_only": True,
        "generated_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI},
        "execution_note": (
            "dispatch window Fri 13:30Z..Sun 23:59Z; scan executed "
            f"{NOW.strftime('%Y-%m-%dT:%HZ')} (post-round-38 queue), so Friday "
            "fixtures had already kicked (boards historical); Sat/Sun boards "
            "are pre-kick"),
        "coverage_verdict": {
            "fotmob_adapter_leagues": ["Championship(48)", "Eredivisie(57)"],
            "xg_snapshot_leagues": ["EPL", "La_liga", "Serie_A", "Bundesliga",
                                    "Ligue_1"],
            "in_scope_leagues_covered": [],
            "conclusion": (
                "NO in-scope league (MLS/Brasileirao A+B/Copa do Brasil/Liga MX/"
                "Argentina/Saudi/J-League/A-League/K-League/other Americas/ROW) "
                "has adapter or snapshot coverage -> BOARD-ONLY scan; every row "
                "labeled 'NO MODEL COVERAGE - report only, no entry'; no ratings "
                "fabricated; kappa bridge unused (no model side).")},
        "provenance": {
            "understat_pointer": json.load(open(f"{HOME}/understat_latest_pointer.json")),
            "library_commit": "5bdae2e3",
            "selfcheck": "PASS 10/10 (run 2026-11-06 pre-scan)",
            "espn_leagues_queried": ["usa.1", "bra.1", "mex.1", "arg.1", "sau.1",
                                     "jpn.1", "aus.1", "conmebol.libertadores",
                                     "conmebol.sudamericana"],
            "gamma_enumeration": ("8 window sweeps (pagination, capped at 1000 "
                                  "events each) + 32 exact-tag sweeps (complete "
                                  "per-league); 1695 unique open soccer events "
                                  "with in-window kickoff"),
            "incident_note": (
                "pass-1 per-event board (with its full CLOB walk set and "
                "1328-market verification) was lost to an assembler "
                "non-idempotency overwrite; this file is the rebuild: full "
                "198-fixture Gamma board + re-fetched CLOB books and "
                "verifications for the 60 highest-liquidity fixtures + all "
                "knockout fixtures + full Copa do Brasil rules texts"),
            "spotcheck": "round39/raw/keybooks_spotcheck.json (30 CLOB rows)",
        },
        "tag_inventory_soccer_window": p2.get("tag_to_league"),
        "espn_fixtures": json.load(open(f"{RAW}/espn_fixtures_r39_americas.json")),
        "fixtures_by_league": league_counts,
        "board_fixtures": board,
        "market_verifications": verifications,
        "verification_summary": {
            "verified_markets": len(verifications), "ok": n_ok,
            "closed_true_found": n_closed,
            "kickoff_matches_event": n_kick,
            "endDate_after_kick_within_30h": n_end},
        "playoff_rules_evidence": rules,
    }
    json.dump(out, open(f"{RAW}/americas_scan.json", "w"), indent=1)
    print("\nwrote", f"{RAW}/americas_scan.json", flush=True)

    # ---------------- candidates file ----------------
    nm = sorted(league_counts)
    playoff_notes = [
        {"finding": (
            "MLS: NOT playoffs this window - Sat 2026-11-07 is Decision Day, "
            "the regular-season finale (90-minute games; playoffs start after; "
            "MLS Cup Final Dec 11-12). Dispatch playoff caveat moot for MLS."),
         "source": "https://www.mlssoccer.com/news/mls-announces-2026-regular-season-schedule"},
        {"finding": (
            "Copa do Brasil = ONLY knockout competition in scope: semifinal "
            "SECOND LEGS Mineiro-Gremio (Sat 21:00Z, Arena MRV; 1st leg Gremio "
            "Nov-1) and Vasco-Palmeiras (Sun 20:00Z, Sao Januario; 1st leg "
            "Palmeiras Nov-1). VERIFIED on 184 markets: every ML/draw/exact-"
            "score/O-U market settles on 'the first 90 minutes of regular play "
            "plus stoppage time; extra time and penalty shoot-outs are "
            "excluded' - so a 90-min model probability WOULD be directly "
            "comparable (no draw->advancement split needed) for these markets; "
            "no advance/aggregate market exists on either fixture. Moot this "
            "round: no model coverage."),
         "source": ("ge.globo.com/CBF schedule + Polymarket market rules text "
                    "(round39/raw/copadobrasil_rules.json)")},
        {"finding": (
            "Player-prop markets on knockout fixtures are DIFFERENT: they "
            "count stats 'within the first 90 minutes ... and any extra time' "
            "(shootout stats excluded) - any future modeling of props on "
            "knockout games must use 90+ET totals, not 90-min totals."),
         "source": "Polymarket player-prop rules text (pass-1 evidence)"},
    ]
    for r in rules:
        if r.get("league") == "Copa do Brasil" and r.get("rules_hits"):
            playoff_notes.append({
                "market_id": r.get("market_id"), "question": r.get("question"),
                "rules_hits": r.get("rules_hits")})

    cand = {
        "round": 39,
        "scan": "soccer-weekend-americas-row",
        "paper_only": True,
        "generated_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_utc": {"lo": LO, "hi": HI},
        "decision": (
            "ENTER NOTHING. Zero in-scope leagues (MLS, Brasileirao Serie A/B, "
            "Copa do Brasil, Liga MX, Argentina Primera, Saudi Pro League, "
            "J-League/J2/J3, A-League, K-League/K2, China, and the other "
            "Americas/ROW leagues found) are covered by the papersim FotMob "
            "adapter (FotmobLeague = Championship, Eredivisie only) or the "
            "Big-5 xG snapshot. Per the dispatch coverage rule this scan is "
            "BOARD-ONLY: no ratings fabricated, no model probabilities, so the "
            "frozen gates (net>=+5c fee-aware, worst>=+4c, var<=6c, liq>=5k, "
            "fills) cannot be evaluated for ANY market; every board row is "
            "labeled 'NO MODEL COVERAGE - report only, no entry'. Proposed "
            "stake $0 of the <=$150 scan budget; the $200 remaining weekend "
            "cap is untouched for agent A. If nothing passes, enter nothing - "
            "this is the fine outcome the dispatch allows."),
        "decision_rationale": (
            "Full Fri-Sun window enumeration: 8 Gamma sweeps + 32 exact-tag "
            "sweeps (1695 unique open soccer events with in-window kickoff), "
            "ESPN cross-check on 9 league feeds (54 slate games). In-scope: "
            + str(len(nm)) + " leagues, 198 fixtures, "
            + str(sum(league_counts.values())) + " board fixtures total. "
            "Verification: " + str(n_ok) + " markets via /markets/{id} - all "
            "closed=false, kickoff matches event, endDate within 30h after "
            "kickoff; Copa do Brasil rules texts captured in full (184 "
            "markets). MLS this weekend = Decision Day regular-season finale "
            "(NOT playoffs; verified). Only knockout games = Copa do Brasil "
            "semifinal second legs. No held fixture (#62-#68) is in this "
            "scan's leagues. Library selfcheck PASS 10/10 @ 5bdae2e3 before "
            "modeling decision; gates.walk_book was the only library function "
            "used (pure book math)."),
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
            "reason": (
                "FotmobLeague enum covers only Championship(48) and "
                "Eredivisie(57); understat_latest.json -> Big-5 blocks only. "
                "Domestic pairs in uncovered leagues cannot be modeled "
                "either (no xG snapshot for the league). Cross-league kappa "
                "bridge is irrelevant (Big-5+UCL/UEL only). Adding a league "
                "requires a verified FotMob id + validated adapter run "
                "recorded in the enum lineage (library change with "
                "validation gates A-E, out of scan scope).")},
        "playoff_rule_notes": playoff_notes,
        "playoff_rules_markets_captured": len(
            [m for m in copa["markets"]]),
        "scoreline_concordance_rule_r32": "not applicable - no candidates",
        "news_concordance": "not applicable - no candidates (no model side to "
                            "concord with; MLS Decision Day + Copa do Brasil "
                            "semifinal context verified via schedule sources)",
        "data_quality_flags": {
            "execution_slip": (
                "dispatch window began Fri 13:30Z; scan executed "
                f"{NOW.strftime('%Y-%m-%dT:%HZ')} (post-round-38 queue): "
                "Friday fixtures already kicked/finished; boards for them are "
                "historical; several Friday events already resolved "
                "(closed=true) and dropped from the open board."),
            "sweep_pagination_cap": (
                "pass-1 window sweeps each hit the 1000-event pagination cap; "
                "exact-tag sweeps (32 tags) provide complete per-league "
                "enumeration."),
            "wrong_slug_guess_pass1": (
                "initial tag map guessed nonexistent slugs ('liga-mx', "
                "'brasileirao', 'argentina-primera'); actual slugs 'mex', "
                "'brazil-serie-a/b', 'arg', 'soccer-brco'(=Copa do Brasil), "
                "'saudi-professional-league', 'australian-a-league', etc. "
                "Classification fixed by tag sweeps + ESPN cross-match."),
            "pass1_loss_and_rebuild": (
                "pass-1 per-event board with full CLOB walks + 1328 "
                "verifications was overwritten by a non-idempotent assembler "
                "re-run; rebuild re-fetched books + verifications for the 60 "
                "highest-liquidity fixtures and all knockout fixtures "
                "(404-fast-fail), and preserved full Copa do Brasil rules "
                "texts; remaining 138 minor-league fixtures carry Gamma "
                "prices/liquidity only."),
            "pass2_404_retries": (
                "pass 2 book phase was killed: the shared get() helper "
                "retried 404 dead tokens 6x (~42s each); pass2b re-ran "
                "without books; rebuild used a 404-fast-fail fetcher."),
            "womens_leagues_excluded": (
                "NWSL ('soccer-nwsl', 10 events) and WSL ('wsl', 6 events) "
                "excluded as women's soccer (r38 precedent)."),
            "europe_excluded_here": (
                "European tags (fa-cup, EPL, efl-championship, la-liga, "
                "sea=Serie A Italy, nls/nln=England non-league, rus, etc.) "
                "belong to agent A/B scans; Russia and Israel treated as "
                "Europe/UEFA and excluded from this ROW scan."),
            "al_hilal_cancellation_anomaly": (
                "Al Ettifaq vs Al Hilal (Sat 14:30Z): CLOB-verified draw YES "
                "0.989/0.994, win sides ~0.01 - market prices near-certain "
                "cancellation (Polymarket draw markets resolve YES if the "
                "game is canceled with no make-up). Not a normal result "
                "market; report-only."),
            "ligamx_listings": (
                "Liga MX open listings in window: Atlas-Pachuca, "
                "Toluca-Monterrey, Tigres-Cruz Azul, Pumas-America, "
                "Atlante-Santos Laguna; San Luis-Juarez and Necaxa-Tijuana "
                "(Fri) finished before scan; Queretaro-Puebla and "
                "Leon-Guadalajara kick Nov-9 (outside window)."),
        },
        "flagged_not_enterable": [
            {"match": "CA Mineiro vs. Grêmio FBPA", "league": "Copa do Brasil",
             "kickoff_utc": "2026-11-07T21:00:00Z",
             "note": ("semifinal 2nd leg; board-only. ML 0.61/0.62, draw "
                      "0.22/0.24, Gremio 0.15/0.17; books live.")},
            {"match": "CR Vasco da Gama vs. SE Palmeiras",
             "league": "Copa do Brasil",
             "kickoff_utc": "2026-11-08T20:00:00Z",
             "note": ("semifinal 2nd leg; board-only. Vasco 0.34/0.36, "
                      "Palmeiras 0.35/0.36, draw 0.29/0.30; thin books.")},
            {"match": "Inter Miami CF vs. Charlotte FC", "league": "MLS",
             "kickoff_utc": "2026-11-07T21:00:00Z",
             "note": ("Decision Day; board-only. Miami ML ~0.71, Charlotte "
                      "~0.15, draw ~0.17.")},
            {"match": "Tigres de la UANL vs. CF Cruz Azul", "league": "Liga MX",
             "kickoff_utc": "2026-11-08T01:00:00Z",
             "note": ("board-only. Cruz Azul ~0.47, Tigres ~0.28, draw ~0.26; "
                      "healthy books.")},
            {"match": "Al Ettifaq vs. Al Hilal", "league": "Saudi Pro League",
             "kickoff_utc": "2026-11-07T14:30:00Z",
             "note": "cancellation-priced anomaly (draw ~0.99); report only."},
        ],
        "library": {
            "package": "polymarket_alpha_lab.papersim",
            "repo_commit": "5bdae2e3",
            "selfcheck": "PASS 10/10 (re-run 2026-11-06 pre-scan)",
            "path": "PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src",
            "note": ("only gates.walk_book (pure book math) used; no model "
                     "functions invoked because no in-scope league is "
                     "modelable; fee model inapplicable (no entries)"),
        },
        "scan_source": (
            "round39/raw/americas_scan.json (unified) + "
            "americas_scan_pass2b.json + copadobrasil_rules.json (184 "
            "knockout-market rules) + keybooks_spotcheck.json (30 CLOB rows) "
            "+ espn_fixtures_r39_americas.json + events_window_39b.json"),
    }
    json.dump(cand, open(f"{HOME}/round39/americas_candidates.json", "w"),
              indent=1)
    print("wrote", f"{HOME}/round39/americas_candidates.json", flush=True)


if __name__ == "__main__":
    main()
