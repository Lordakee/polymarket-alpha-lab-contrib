"""ROUND-43C board summary builder (paper-only).

Reads round43/raw/americas_scan.json (completed 43C scan, 13 in-window
events -> 3 board fixtures) plus the supplemental gap-check and ESPN data,
and writes round43/americas_board.json (fixtures/prices/liq/anomalies).
Corrects the pass-1 espn_only false positive (exact-set name matching) by
re-matching with substring logic; documents the ESPN-Gamma discrepancy on
the Cali derby. No model probabilities anywhere - board only.
"""
import json
import re
import unicodedata

HOME = "/home/ubuntu/paper-sim"
RAW = json.load(open(f"{HOME}/round43/raw/americas_scan.json"))
ESPN = json.load(open(f"{HOME}/round43/raw/espn_fixtures_43c.json"))
GAP = json.load(open(f"{HOME}/round43/raw/supplemental_gap_check.json"))
OUT = f"{HOME}/round43/americas_board.json"
LO, HI = "2026-11-09T01:15:00Z", "2026-11-09T05:30:00Z"


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm_name(s):
    s = strip_accents(str(s or "").lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in {
        "fc", "cf", "ac", "sc", "afc", "1", "the", "de", "club", "calcio",
        "rc", "ud", "us", "as", "sv", "cd", "ca", "scd", "sd"}]
    return " ".join(toks).strip()


fixtures = []
for f in RAW["board_fixtures"]:
    mkt_liq_sum = sum(r["liq_gamma_usd"] for r in f["rows"])
    brief = {"moneyline_draw_totals": []}
    for r in f["rows"]:
        if r["kind"] in ("ml_win", "ml_draw"):
            for s in r["sides"][:2]:
                brief["moneyline_draw_totals"].append({
                    "kind": r["kind"], "outcome": s.get("outcome"),
                    "gamma_price": s.get("gamma_price"),
                    "clob_bid": s.get("clob_best_bid"),
                    "clob_ask": s.get("clob_best_ask"),
                    "vwap_250_ask": s.get("vwap_250"),
                    "fill_250": s.get("fill_250"),
                    "depth_within_2c_usd": s.get("depth_2c_usd")})
        if r["kind"] == "team_total" and str(r.get("line")) in ("2.5", "2.50"):
            for s in r["sides"][:2]:
                if str(s.get("outcome")).lower() == "over":
                    brief["ou_2_5"] = {
                        "line": r.get("line"),
                        "gamma_price": s.get("gamma_price"),
                        "clob_bid": s.get("clob_best_bid"),
                        "clob_ask": s.get("clob_best_ask")}
    spreads = []
    for r in f["rows"]:
        sp = [s["clob_best_ask"] - s["clob_best_bid"]
              for s in r["sides"]
              if s.get("clob_best_bid") is not None
              and s.get("clob_best_ask") is not None]
        if sp:
            spreads.append({"kind": r["kind"],
                            "min_spread_c": round(min(sp) * 100, 1),
                            "max_spread_c": round(max(sp) * 100, 1)})
    ml_spread = next((s for s in spreads if s["kind"] in ("ml_win", "ml_draw")), None)
    dead_books = sum(1 for r in f["rows"] for s in r["sides"]
                     if s.get("clob") == "no book (dead token or fetch failed)")
    fixtures.append({
        "match": f["match"], "league": f["league"],
        "kickoff_utc": f["kickoff_utc"],
        "kickoff_status_at_scan": f["kickoff_status_at_scan"],
        "gamma_event_ids": f["event_ids"],
        "n_market_rows": len(f["rows"]),
        "market_kinds": f["market_kinds"],
        "vol24_usd_all_events": round(f["vol24"], 2),
        "market_level_liquidity_sum_usd": round(mkt_liq_sum, 2),
        "top_market_liquidity_usd": round(max(
            (r["liq_gamma_usd"] for r in f["rows"]), default=0), 2),
        "key_prices": brief,
        "spread_quality_ml": ml_spread,
        "anomaly_flags": f["anomaly_flags"],
        "espn_cross_check": f.get("espn"),
        "coverage": "NO MODEL COVERAGE - report only, no entry"})

# ---- corrected ESPN-only reconciliation (substring matching) ----
gamma_pairs = []
for f in RAW["board_fixtures"]:
    parts = re.split(r"\s+vs\.?\s+|\s+at\s+", f["match"], maxsplit=1)
    if len(parts) == 2:
        gamma_pairs.append((norm_name(parts[0]), norm_name(parts[1]),
                            f["match"], f["league"]))

espn_in_window = []
for date, day in ESPN.items():
    for lg, evs in day.items():
        for ev in (evs if isinstance(evs, list) else []):
            dt = ev.get("date") or ""
            if not (dt and LO <= dt <= HI):
                continue
            th = norm_name((ev["teams"].get("home") or {}).get("name"))
            ta = norm_name((ev["teams"].get("away") or {}).get("name"))
            matched = None
            for gh, ga, gmatch, glg in gamma_pairs:
                if (th and ta) and ((th in gh or gh in th or th in ga or ga in th)
                                    and (ta in gh or gh in ta or ta in ga or ga in ta)):
                    matched = gmatch
                    break
            espn_in_window.append({
                "league": lg, "kickoff_utc": dt, "name": ev.get("name"),
                "status": ev.get("status"), "note": ev.get("note"),
                "on_gamma_open_board": bool(matched),
                "gamma_match": matched})

summary = {
    "round": 43, "scan": "americas-overnight-tail", "paper_only": True,
    "generated_utc": RAW["generated_utc"],
    "board_built_utc": "2026-11-08T14:09Z (from completed scan raw; "
                       "prices timestamped at scan 13:48-13:51Z)",
    "window_utc": {"lo": LO, "hi": HI},
    "coverage_statement": (
        "FotMobLeague enum = {CHAMPIONSHIP, EREDIVISIE} only (verified at "
        "repo 1a2760bc); xG snapshot covers Big-5 only (EPL/La_liga/Serie_A/"
        "Bundesliga/Ligue_1 via round41 merged file; Championship and "
        "Eredivisie covered by their own adapters but have no fixtures in "
        "this window). Colombia Primera A, Peru Liga 1, Liga MX and every "
        "other league in this window have NO model coverage. BOARD-ONLY: "
        "prices/liquidity reported, no ratings fabricated, no entry. "
        "Stake $0 of the $0 board-only budget."),
    "decision": (
        "ENTER NOTHING. Zero in-scope fixtures are modelable (no club in any "
        "window fixture appears in the Big-5/Championship/Eredivisie club "
        "universe - modelable-club STOP check returned 0 alerts). Report-only "
        "board below; $0 staked, no orders, no DB writes."),
    "modelable_club_alerts": RAW["modelable_club_alerts"],
    "enumeration": {
        "method": ("Gamma /events/pagination per-tag sweeps (28 sweeps: "
                   "soccer + 24 Americas tags + MLS-Cup/LigaMX aliases, cap "
                   "1000) with local kickoff filtering; 4 date-window sweeps "
                   "returned 0 because Gamma start_date_min/max filter on the "
                   "event LISTING-creation startDate, not kickoff (verified: "
                   "event 1260476 startDate=2026-10-26, gameStartTime="
                   "2026-11-09T01:15Z). Supplemental gap-check sweeps "
                   "(endDate-asc / liquidity-desc / created-asc, 600 each) "
                   "found 0 additional in-window events."),
        "gap_check_new_events": len(GAP),
        "unique_in_window_soccer_events": 13,
        "board_fixtures": 3,
        "tag_census_in_window": RAW["tag_census_in_window"],
        "sweep_log": RAW["provenance"]["gamma_sweep_log"],
        "ids_param_note": ("Gamma /markets?ids= list param is BROKEN; all "
                           "market verifications used /markets/{id}")},
    "leagues_expected_but_absent": {
        "argentina_primera": ("ESPN shows only one Sunday game (Lanus at "
                              "Central Cordoba 2026-11-08T22:30Z) - before "
                              "window start 01:15Z; tag-arg sweep in_window=0"),
        "brasileirao": ("No Serie A games on ESPN Nov 8-10 this matchweek; "
                        "Serie B latest Sunday kickoff 22:15Z (before window); "
                        "tag sweeps in_window=0"),
        "chile_ecuador_uruguay_paraguay_bolivia_venezuela_costa_rica_guatemala":
            ("All Sunday kickoffs end 23:30Z or earlier (latest: Bolivia "
             "23:30Z, Chile 23:00Z, Costa Rica 00:30Z, Guatemala 00:00Z, "
             "Queretaro-Puebla Liga MX 00:00Z) - all before 01:15Z window "
             "start; tag sweeps in_window=0; Monday games (Ecuador 18:00Z+, "
             "Paraguay 20:00Z+, Bolivia 00:30Z Nov-10, Colombia Junior-"
             "Cucuta 00:00Z Nov-10) all after window end 05:30Z"),
        "mls": ("Decision Day was Sat/Sun Nov 7-8 daytime (r39 verified); "
                "no MLS games listed by ESPN Nov 8-10; tag-mls sweep "
                "in_window=0 (55 open MLS events, none kicking in window)"),
        "liga_mx": ("2 Sunday-night games: Queretaro-Puebla 00:00Z (before "
                    "window) and Leon-Guadalajara 02:10Z (in window, on "
                    "board)")},
    "euro_slippage_check": {
        "euro_tagged_events_in_window": RAW["euro_slippage_events"],
        "espn_monday_europe": ("No Championship or Ligue 1 Monday fixtures "
                               "listed by ESPN for Nov 9-10; Ligue 1 slate is "
                               "all Sunday (14:00-19:45Z Nov 8, 43B scope). "
                               "Nothing European kicks inside 01:15Z-05:30Z "
                               "Nov 9."),
        "conclusion": "CLEAN - no European slippage into the window"},
    "fixtures": fixtures,
    "anomalies": RAW["anomalies"],
    "anomaly_screen": (
        "Checked and CLEAN on all 3 fixtures: no cancellation-priced draws "
        "(draw YES prices 0.115-0.295, win sides normal; r39 Al-Ettifaq "
        "pattern absent); no placeholder 0.49/0.51 no-volume dead books "
        "(the one 0.49/0.51-looking market - Alianza BTTS - has live "
        "two-sided CLOB books with $237-$636 within 2c); no women's-league "
        "or friendly lookalikes; no wide-spread (>10c) ML books (ML spreads "
        "1c everywhere)."),
    "espn_only_reconciliation": {
        "espn_in_window_games": espn_in_window,
        "notes": [
            ("Deportivo Cali at America de Cali (Colombia, 01:45Z, ESPN "
             "status 'Full Time' for a not-yet-kicked slot) is NOT on the "
             "open Gamma board; Gamma has CLOSED events 'America de Cali vs "
             "AD Cali' with gameStartTime 2026-11-08T01:15:00Z (a day "
             "earlier). ESPN-Gamma date/status discrepancy - not enterable, "
             "not modeled, report-only."),
            ("Pass-1 espn_only list flagged 'Deportivo Moquegua at "
             "Universitario' as ESPN-only - FALSE POSITIVE of exact-set name "
             "matching; it is the same game as Gamma fixture 'Club "
             "Universitario de Deportes vs. CD Moquegua' (01:30Z) and is on "
             "the board. Corrected here by substring matching.")]},
    "data_quality_notes": [
        ("Gamma event-level liquidityNum is 0/null for all three fixtures; "
         "market-level liquidity is real and reported instead (sums "
         "$16.8k-$77.6k per fixture)."),
        ("Polymarket question strings use Nov-8 ET-date labels ('Will X win "
         "on 2026-11-08?') while gameStartTime is 2026-11-09T0x:xxZ - "
         "verified kickoff-match on 9/9 markets via /markets/{id}, all "
         "closed=false, endDate within 30h after kickoff."),
        ("Deep-tail market 'Spread: CD Moquegua (-3.5)' has a near-dead book "
         "(~$7-8 within 2c, $250 walk does not fully fill) - flagging as "
         "ultra-thin; not an entry candidate regardless (no model).")],
    "verification": {
        "markets_checked_via_markets_id": len(RAW["market_verifications"]),
        "bad": RAW["verification_bad_count"],
        "detail": RAW["market_verifications"]},
    "provenance": {
        "repo_commit": "1a2760bc",
        "library": "polymarket_alpha_lab.papersim gates.walk_book only "
                   "(book math; no model functions invoked)",
        "selfcheck": "not needed per dispatch (no modeling)",
        "raw_scan": "round43/raw/americas_scan.json (generated "
                    "2026-11-08T13:48:20Z, completed 13:51Z)",
        "43c_intermediates": ["round43/raw/events_window_43c.json",
                              "round43/raw/espn_fixtures_43c.json",
                              "round43/raw/scan43c.log",
                              "round43/raw/supplemental_gap_check.json"],
        "collision_note": ("round43/raw/COLLISION_NOTE_43c.md - pass-1 "
                           "intermediates briefly overwrote the parallel "
                           "43B agent's events_window_43.json / "
                           "espn_fixtures_43.json; 43B files were restored "
                           "by re-running their own enum43.py (verified: 191 "
                           "European events back on disk 14:00Z); all 43C "
                           "artifacts now use the 43c suffix")},
}
json.dump(summary, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("fixtures:", len(fixtures))
for f in fixtures:
    print("  %-46s %-18s %s mktliq=$%.0f vol=$%.0f" % (
        f["match"][:44], f["league"], f["kickoff_utc"],
        f["market_level_liquidity_sum_usd"], f["vol24_usd_all_events"]))
