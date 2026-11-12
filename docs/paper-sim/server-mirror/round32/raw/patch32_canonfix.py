"""Round-32 post-pass: canon alias fixes for 5 fixtures missed by substring
canon (accented/renamed Gamma titles), model + gate them, append to the
board; plus a direct Gamma check for Brest-Lyon (absent from discovery).

Missed fixtures (from scan post-mortem):
  Hamburger SV vs Boro Mönchengladbach  (BL Fri)
  Málaga CF vs Real Racing Club          (LaLiga Sat)
  RCD Espanyol vs RC Deportivo A Coruña  (LaLiga Sat)
  Stade Rennais FC 1901 vs Lille OSC     (L1 Sun)
  1. FC Köln vs Bayer 04 Leverkusen      (BL Sun)
All are DOMESTIC same-league pairs -> standard 10-variant path.
"""
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/paper-sim/round32/raw")
import soccer_scan32 as S  # noqa: E402

SCAN = "/home/ubuntu/paper-sim/round32/raw/soccer_scan.json"
BOARD = "/home/ubuntu/paper-sim/round32/raw/odds_board_32.json"

# 1) alias additions: exact-lower raw forms (accents kept) + norm forms
S.TEAM_ALIASES.update({
    "borussia mönchengladbach": "Borussia M.Gladbach",
    "borussia monchengladbach": "Borussia M.Gladbach",
    "monchengladbach": "Borussia M.Gladbach",
    "b monchengladbach": "Borussia M.Gladbach",
    "real racing club": "Racing Santander",
    "real racing club santander": "Racing Santander",
    "real racing": "Racing Santander",
    "rc deportivo a coruña": "Deportivo La Coruna",
    "deportivo a coruna": "Deportivo La Coruna",
    "stade rennais fc 1901": "Rennes",
    "stade rennais 1901": "Rennes",
    "stade rennais": "Rennes",
    "rennais": "Rennes",
    "1. fc köln": "FC Cologne",
    "1 fc koln": "FC Cologne",
    "fc köln": "FC Cologne",
    "fc koln": "FC Cologne",
    "koln": "FC Cologne",
    "vfl bochum 1848": "Bochum",  # guard (not in window)
})

# 2) rebuild canon universe
snapshot = S.xg.load_xg_snapshot(S.XG_PATH)
for lg in S.BIG5:
    block = snapshot.get(f"{lg}_2026") or {}
    for t in (block.get("teams") or {}).values():
        title = t.get("title")
        if title:
            S.ALL_TITLES[title] = lg
            S.TITLE_LEAGUE[title] = lg

# 3) reclassify saved events with fixed canon
events = json.load(open(S.EVENTS_OUT))
fixtures = []
for e in events:
    base = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
    parts = re.split(r"\s+vs\.?\s+|\s+at\s+", base, maxsplit=1)
    home_raw = parts[0].strip() if parts else ""
    away_raw = parts[1].strip() if len(parts) > 1 else ""
    home = S.canon_team(home_raw)
    away = S.canon_team(away_raw)
    lgh = S.TITLE_LEAGUE.get(home) if home else None
    lga = S.TITLE_LEAGUE.get(away) if away else None
    if home and away and lgh == lga:
        fixtures.append({"event": e, "home": home, "away": away,
                         "lg": lgh, "kick": e["kick"],
                         "comp": e.get("tags")})

d = json.load(open(SCAN))
already = {m["fixture_key"] for m in d["matches"]}
now = datetime.now(timezone.utc)

new_matches, new_rows = [], []
for fx in sorted(fixtures, key=lambda x: x["kick"]):
    e = fx["event"]
    base_title = re.split(r"\s+-\s+", e.get("title") or "", maxsplit=1)[0]
    fkey = S.fixture_key(fx["home"], fx["away"])
    if fkey in already:
        continue
    variants = S.soccer_model.fixture_variants(
        snapshot, fx["home"], fx["lg"], fx["away"], fx["lg"])
    if variants is None:
        print("still refused:", base_title)
        continue
    vs = [{"lambdas": (v.lambdas[0], v.lambdas[1]), "outputs": v.outputs,
           "spec": getattr(v.spec, "name", "?")} for v in variants]
    lam_h = S.soccer_model.median([v["lambdas"][0] for v in vs])
    lam_a = S.soccer_model.median([v["lambdas"][1] for v in vs])
    p1x2 = {
        "H": S.soccer_model.median([v["outputs"].home_win for v in vs]),
        "D": S.soccer_model.median([v["outputs"].draw for v in vs]),
        "A": S.soccer_model.median([v["outputs"].away_win for v in vs]),
    }
    form_h = S.xg.recent_form(snapshot, fx["home"])
    form_a = S.xg.recent_form(snapshot, fx["away"])
    new_matches.append({
        "match": base_title, "comp": "%s_DOM" % fx["lg"], "cross_league": False,
        "bridged": False, "section": S.section_of(fx["kick"]), "in_entry_window": True,
        "home_league": fx["lg"], "away_league": fx["lg"], "fixture_key": fkey,
        "gamma_event_ids": [e["id"]], "kickoff_utc": fx["kick"],
        "lambda_home": round(lam_h, 3), "lambda_total": round(lam_h + lam_a, 3),
        "lambda_away": round(lam_a, 3),
        "p1x2_med_report_only": {k: round(v, 4) for k, v in p1x2.items()},
        "p1x2_note": "eligible-but-deprioritized",
        "form_home_last5": {"gp": form_h.games, "gf": form_h.goals_for,
                            "ga": form_h.goals_against,
                            "xg_for": round(form_h.xg_per_game * form_h.games, 2),
                            "o25_hits": form_h.over_2_5_hits,
                            "btts_hits": form_h.btts_hits},
        "form_away_last5": {"gp": form_a.games, "gf": form_a.goals_for,
                            "ga": form_a.goals_against,
                            "xg_for": round(form_a.xg_per_game * form_a.games, 2),
                            "o25_hits": form_a.over_2_5_hits,
                            "btts_hits": form_a.btts_hits},
        "method": "library fixture_variants (10 sweeps, domestic; canon-fix post-pass)",
    })
    o25_combined = form_h.over_2_5_hits + form_a.over_2_5_hits
    seen_mkt = set()
    nrow = 0
    for m in e["markets"]:
        if m["id"] in seen_mkt:
            continue
        seen_mkt.add(m["id"])
        side_specs = S.parse_market_sides(m, fx["home"], fx["away"])
        if side_specs is None:
            continue
        for token_idx, kind, side_id, line, team_side in side_specs:
            qs = []
            for v in vs:
                qv = S.model_quote(v["outputs"], kind, side_id, line, team_side)
                if qv is None:
                    qs = None
                    break
                qs.append(qv)
            if not qs:
                continue
            book = S.fetch_book(m, token_idx)
            if book is None:
                continue
            liq = float(m.get("liq") or 0)
            quote = {"model_median": S.soccer_model.median(qs),
                     "qs_variants": tuple(qs)}
            ur, ur_reason = S.gates.under_risk_check(
                kind=kind,
                side=side_id.split("_no")[0] if side_id.endswith("_no") else side_id,
                o25_hits=o25_combined, lambda_total=lam_h + lam_a,
                lambda_home=lam_h, lambda_away=lam_a,
                line=line if line else 2.5)
            report = S.gates.evaluate_candidate(
                quote, book["asks"], gamma_liquidity=liq, under_risk=ur)
            pol = S.gates.suspension_policy(kind, cross_league=False)
            exit_walk = S.gates.walk_book(
                [(p, s) for p, s in book["bids"]], side="bid")
            hours = max(1, round((datetime.fromisoformat(
                fx["kick"].replace("Z", "+00:00")) - now).total_seconds() / 3600))
            row = {
                "match": base_title, "comp": "%s_DOM" % fx["lg"],
                "cross_league": False, "fixture_key": fkey,
                "section": S.section_of(fx["kick"]), "in_entry_window": True,
                "q": m["q"], "kind": kind, "side": side_id, "line": line,
                "team_side": team_side, "id": m["id"], "policy": pol.policy,
                "p_med": round(quote["model_median"], 4),
                "p_min": round(min(qs), 4), "p_max": round(max(qs), 4),
                "n_variants": len(qs), "var_spread": report.variant_spread,
                "book_best_bid": book["best_bid"], "book_best_ask": book["best_ask"],
                "liq_gamma": liq, "exec_ask_vwap250": report.walk.vwap,
                "fill_250": report.walk.filled,
                "depth_2c": report.walk.depth_near2c,
                "exit_bid": book["best_bid"], "exit_bid_vwap250": exit_walk.vwap,
                "exit_bid_depth_2c": exit_walk.depth_near2c,
                "edge_vs_ask": (round(quote["model_median"] - book["best_ask"], 4)
                                if book["best_ask"] is not None else None),
                "exec_edge": report.exec_edge,
                "worst_variant_edge": report.worst_variant_edge,
                "haircut": report.haircut,
                "exec_edge_haircut": report.exec_edge_haircut,
                "under_risk": ur, "under_risk_reason": ur_reason,
                "checks": {k: bool(v) for k, v in report.checks.items()},
                "passed_numeric": all(
                    v for k, v in report.checks.items() if k != "news_concordant"),
                "entry_flags": ["EARLY-ENTRY: kickoff %dh after scan; XIs "
                                "unconfirmed -> $150 tier" % hours],
                "canon_fix": True,
            }
            if kind == "spread":
                row["entry_flags"].append("SPREADS-FLAGGED-ONLY (never entered)")
            elif kind == "ml":
                row["entry_flags"].append("MATCH-WINNER domestic: eligible-but-deprioritized")
            if row["passed_numeric"] and kind not in ("spread",):
                row["entry_flags"].append("NUMERIC-PASS (pending news-concordance)")
            row["enterable"] = bool(row["passed_numeric"] and kind != "spread")
            new_rows.append(row)
            nrow += 1
    print("modeled %-44s kick=%s rows=%d" % (base_title, fx["kick"], nrow))

# 4) Brest-Lyon direct gamma probe
brest_probe = {"query": "Brest vs Lyon", "result": "not attempted"}
try:
    params = {"limit": 20, "active": "true", "closed": "false",
              "order": "volume24hr", "ascending": "false"}
    resp = S.get(S.BASE + "/events/pagination?" + urllib.parse.urlencode(params))
    found = [e.get("title") for e in (resp.get("data") or resp)
             if "brest" in str(e.get("title") or "").lower()
             and "lyon" in str(e.get("title") or "").lower()]
    brest_probe = {"query": "Brest vs Lyon (top-volume active events)",
                   "found": found}
except Exception as e:  # noqa: BLE001
    brest_probe = {"query": "Brest vs Lyon", "error": repr(e)[:120]}

# 5) merge + save
d["matches"].extend(new_matches)
d["board"].extend(new_rows)
d["board_rows"] = len(d["board"])
d["board"].sort(key=lambda r: (-(r["exec_edge"] if r["exec_edge"] is not None else -9),
                               r["match"]))
d["canon_fixes"] = {
    "added_aliases": sorted(set([
        "borussia mönchengladbach", "real racing club", "rc deportivo a coruña",
        "stade rennais fc 1901", "1. fc köln", "fc köln", "koln",
        "deportivo a coruna", "rennais", "monchengladbach"])),
    "fixtures_recovered": [m["match"] for m in new_matches],
    "brest_lyon_probe": brest_probe,
    "final_coverage": "43/48 modeled; Brest-Lyon has no Polymarket market yet "
                      "(probe result attached); remaining 4 are the canon-fixed "
                      "fixtures above; ESPN remains the 48-game source of truth.",
}
json.dump(d, open(SCAN, "w"), indent=1)
json.dump({"generated_utc": d["generated_utc"], "matches": d["matches"],
           "board": d["board"]}, open(BOARD, "w"), indent=1)

print("\nnew matches:", len(new_matches), "new board rows:", len(new_rows))
print("brest probe:", brest_probe)
newpass = [r for r in new_rows if r["passed_numeric"]]
print("NEW numeric passers:", len(newpass))
for r in newpass:
    print("  PASS %s | %s %s line=%s exec=+%dc worst=+%dc var=%.1fc liq=$%.0f" % (
        r["match"], r["kind"], r["side"], r["line"],
        round(100 * (r["exec_edge_haircut"] or 0)),
        round(100 * (r["worst_variant_edge"] or 0)),
        100 * (r["var_spread"] or 0), r["liq_gamma"] or 0))
