"""Round-39A candidates writer: euro-ext sub-scan (paper-only)."""
import json
from datetime import datetime, timezone

SCAN = "/home/ubuntu/paper-sim/round39/raw/euro_ext_scan.json"
OUT = "/home/ubuntu/paper-sim/round39/euro_ext_candidates.json"

d = json.load(open(SCAN))
board = d["board"]
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# near-misses: eligible kinds, best net edge, with fail reasons
elig = [r for r in board if r["kind"] != "spread"]
elig.sort(key=lambda r: -(r["exec_edge_haircut"] if r["exec_edge_haircut"] is not None else -9))
blocked = []
for r in elig[:10]:
    fails = [k for k, v in r["checks"].items() if not v]
    blocked.append({
        "match": r["match"], "league": r["league"], "kickoff_utc": r["kickoff_utc"],
        "market_id": r["id"], "market_question": r["q"], "kind": r["kind"],
        "side": r["side"], "line": r["line"],
        "net_edge_c": round(100 * (r["exec_edge_haircut"] or 0), 2),
        "gross_edge_c": round(100 * (r["exec_edge_gross"] or 0), 2),
        "worst_variant_edge_c": round(100 * (r["worst_variant_edge"]
                                             if r["worst_variant_edge"] is not None else -9), 2),
        "var_spread_c": round(100 * (r["var_spread"] or 0), 2),
        "p_med": r["p_med"], "p_min": r["p_min"], "p_max": r["p_max"],
        "entry_ask_vwap": r["exec_ask_vwap250"], "liq_gamma": r["liq_gamma"],
        "fill_250": r["fill_250"], "failed_checks": fails,
        "block_reason": ("variant spread %.2fc exceeds frozen 6c bar (10-variant model "
                         "disagreement on promoted-side fallback: ADO Den Haag / Cambuur / "
                         "Telstar have no 2025 prior; current-only variant diverges from "
                         "blends by 8-28c)" % (100 * (r["var_spread"] or 0))
                         if "variant_spread<=6c" in fails else
                         "; ".join(fails))})

no_model = {}
for bo in d["board_only"]:
    if bo["post_kickoff"]:
        continue
    no_model.setdefault(bo["league"], 0)
    no_model[bo["league"]] += 1

out = {
    "round": 39,
    "sub_scan": "A euro-ext (Europe beyond Big-5 + Championship)",
    "scan": "soccer-europe-beyond-big5",
    "paper_only": True,
    "generated_utc": now,
    "window_utc": d["window_utc"],
    "decision": ("NO ENTRY (0 positions; $0 of the $150 sub-scan share). Every modeled "
                 "Eredivisie row with a positive net edge fails the FROZEN variant-spread "
                 "gate (<=6c): spreads run 6.5c-28c because the current-only variant "
                 "diverges from blend variants on promoted sides (ADO Den Haag, Cambuur, "
                 "Telstar - no 2025 prior). No gate was loosened. Board-only leagues have "
                 "no model coverage and are report-only by rule."),
    "decision_rationale": (
        "Coverage: FotMob adapter enum = {Championship, Eredivisie}; Eredivisie is the "
        "only in-scope league with ratings. First-ever Eredivisie adapter run executed "
        "via the library path (id 57, 34 rounds, 18 teams; 100 matches 2026/27 through "
        "Nov-6 + 306 matches 2025/26; fail-closed checks passed; inline sanity: 2025 "
        "goal fit ~1.3%, Pearson r xGF-GF 0.859 / xGA-GA 0.776 vs the 0.7 gate-C bar). "
        "8 weekend Eredivisie fixtures modeled, 560 board rows, 8/8 ESPN-verified. "
        "0/560 rows pass all numeric gates: every positive-edge row dies on variant "
        "spread <=6c (near-misses: Twente ml home +14.8c net but 12.4c spread; "
        "Cambuur-PSV totals unders +8-10c net but 6.8-15c spreads). News concordance "
        "CORROBORATES the kills: every published source on Cambuur-PSV predicts a PSV "
        "win with over 2.5 (Forebet 1-4; Wincomparator Cambuur ~11%) while our median "
        "underrates PSV (promoted-side prior fallback) - r32 scoreline-concordance "
        "would have killed the Cambuur unders independently; Twente-Ajax public odds "
        "~coin flip (+123 Twente) vs our 59% - the +14.8c ml edge is model-only. "
        "159 fixtures across 29 other European leagues = NO MODEL COVERAGE "
        "(board-only, report-only). Friday Nov-6 fixtures all post-kickoff (Full "
        "Time) - excluded. No held-fixture overlap (7 held are Big-5/French). "
        "Budget $150 untouched; coordinator pool intact."),
    "max_new_positions": 0,
    "positions_used": 0,
    "stake_per_position_usd": 0,
    "mw_stake_usd": 0,
    "total_stake_usd": 0,
    "bankroll_usd": None,
    "cash_usd": None,
    "bankroll_note": ("not provided in this dispatch; round-38 brief said $13,409 / "
                      "$11,923 / 5 open, before #66-#68 entries"),
    "weekend_cap_all_agents_usd": 200,
    "this_subscan_share_usd": 150,
    "open_positions_note": ("held per dispatch: #62 Sevilla-Alaves, #63 ManUtd-Villa, "
                            "#64 Mainz-Bayern, #65 Osasuna-Athletic, #66 Valencia-Real, "
                            "#67 LeMans-Monaco, #68 Brest-Lyon - none in this scan's scope"),
    "new_candidates": [],
    "blocked_passers": blocked,
    "no_model_coverage": [
        {"league": lg, "fixtures_sat_sun": n,
         "note": "NO MODEL COVERAGE - report only, no entry"}
        for lg, n in sorted(no_model.items(), key=lambda kv: -kv[1])],
    "key_game_notes": [
        "Eredivisie adapter FIRST RUN (WP-P3): gates D/E (backtest, market calibration) "
        "never run for Eredivisie; totals-family treated as primary, match_winner "
        "deprioritized with explicit caveat",
        "Promoted 2026/27 sides (no 2025 prior): ADO Den Haag, Cambuur, Willem II - "
        "prior-season fallback = gate-E distortion class; the variant-spread gate "
        "caught every affected row",
        "ESPN coverage gaps found: sui.1 lists 0 Swiss games this weekend vs 6 on "
        "Polymarket; nor.1 missing Kristiansund-Vaalerngen vs Polymarket; both "
        "board-only so no entry impact",
        "Eredivisie fixture Willem II-PEC Zwolle kicked Fri 19:00Z (finished) - "
        "post-kickoff, excluded",
        "Match-winner liquidity strongest at Eyupspor-Kocaelispor ($80k) and "
        "Sporting-Moreirense ($42k) - both board-only leagues"],
    "scan_artifacts": {
        "raw_board": "/home/ubuntu/paper-sim/round39/raw/euro_ext_scan.json",
        "events_window": "/home/ubuntu/paper-sim/round39/raw/events_window_39.json",
        "espn_probe": "/home/ubuntu/paper-sim/round39/raw/espn_leagues_probe.json",
        "eredivisie_snapshot": "/home/ubuntu/paper-sim/round39/raw/xg_fotmob_eredivisie.json",
        "eredivisie_snapshot_meta": "/home/ubuntu/paper-sim/round39/raw/xg_fotmob_eredivisie.json.meta.json",
        "fetch_script": "/home/ubuntu/paper-sim/round39/raw/fetch_eredivisie.py",
        "scan_script": "/home/ubuntu/paper-sim/round39/raw/scan39_euro_ext.py",
        "scan_log": "/home/ubuntu/paper-sim/round39/raw/scan39.log",
        "selfcheck": "PASS 10/10 (2026-11-07 ~06:5xZ, repo commit 5bdae2e3)"},
}
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("decision:", out["decision"][:120])
print("blocked near-misses:", len(blocked), "| no-model leagues:", len(no_model))
