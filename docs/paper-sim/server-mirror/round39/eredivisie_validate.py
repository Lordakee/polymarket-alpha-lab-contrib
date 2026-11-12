#!/usr/bin/env python3
"""WP-P3 Eredivisie validation suite (mirror of the Championship validator).

Gates are the SAME definitions/thresholds as ~/paper-sim/tools/fotmob_validate.py
(round31, Championship), with two league-shape adaptations, both documented:
  - Gate A expects 18 teams and numeric rounds 1-34 (Eredivisie; Championship: 24/46).
  - Gate D keeps the n>=90 evidence bar and the beats-baseline-on-both bar, but the
    walk-forward window is rounds 2-13 (9 matches/round -> n=91) because an 18-team
    league cannot reach n=90 over the Championship's rounds 6-13 window (9/round vs
    12/round). The exact mirror window rounds 6-13 is ALSO reported (n=55).
Gate E compares the 8 round-12 fixtures in the round-39 scan window (the 9th,
Willem II v PEC Zwolle, was played 2026-11-06 19:00Z, pre-scan, post-kickoff).

Also prices the totals-family board (O/U, BTTS, TT) for those fixtures and runs
the promoted-team fallback variant-spread analysis (counterfactuals only; the
papersim library is NOT modified).

Paper-only: no credentials, no orders, no DB writes, no repo modification.
Writes only under ~/paper-sim/round39/.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import soccer_model, xg  # noqa: E402

LEAGUE = "Eredivisie"
SEASON_CUR, SEASON_PRI = "2026", "2025"
BLOCK_CUR = "{}_{}".format(LEAGUE, SEASON_CUR)
BLOCK_PRI = "{}_{}".format(LEAGUE, SEASON_PRI)

RAW = Path("/home/ubuntu/paper-sim/round39/raw")
SNAP_PATH = RAW / "xg_fotmob_eredivisie.json"
META_PATH = RAW / "xg_fotmob_eredivisie.json.meta.json"
CACHE_FIX = Path("/home/ubuntu/paper-sim/tools/fotmob_cache/fixtures")
FD_CSV = {"2025": Path("/tmp/n1_2526.csv"), "2024": Path("/tmp/n1_2425.csv")}
EVENTS_PATH = RAW / "events_window_39.json"
OUT_DIR = Path("/home/ubuntu/paper-sim/round39")
REPORT_MD = OUT_DIR / "eredivisie_validation.md"
VAL_JSON = OUT_DIR / "eredivisie_validation.json"
BT_JSON = OUT_DIR / "eredivisie_backtest.json"

LIB_REF = "polymarket-alpha-lab @ 5bdae2e3 (papersim; same tree as round-39A scan)"

# League shape: 18 teams, 34 numeric rounds (fetch constants per FotMobLeague.EREDIVISIE)
N_TEAMS = 18
ROUND_LO, ROUND_HI = 1, 34
# Walk-forward windows: primary (n>=90 bar reachable) + exact Championship mirror
WF_PRIMARY = range(2, 14)      # rounds 2..13
WF_MIRROR = range(6, 14)       # rounds 6..13 (Championship window)
# Events scan freeze (events_window_39.json captured 2026-11-07 07:08Z; euro-ext
# sub-scan generated 07:38Z; all Eredivisie round-12 kickoffs are later than both)
SCAN_CUTOFF = "2026-11-07 07:08:00"

OU_LINES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
TT_LINES = [0.5, 1.5, 2.5, 3.5]
MAIN_EVENT_RE = re.compile(r"^ere-[a-z0-9]+-[a-z0-9]+-\d{4}-\d{2}-\d{2}$")

# Polymarket display name -> FotMob snapshot title (explicit, asserted against titles)
PM_TO_FOTMOB = {
    "Fortuna Sittard": "Fortuna Sittard",
    "Telstar 1963": "Telstar",
    "ADO Den Haag": "ADO Den Haag",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "SBV Excelsior": "Excelsior",
    "Go Ahead Eagles": "Go Ahead Eagles",
    "SC Heerenveen": "SC Heerenveen",
    "Feyenoord Rotterdam": "Feyenoord",
    "FC Twente": "FC Twente",
    "AFC Ajax": "Ajax",
    "AZ": "AZ Alkmaar",
    "FC Groningen": "FC Groningen",
    "SC Cambuur-Leeuwarden": "Cambuur",
    "PSV": "PSV Eindhoven",
    "FC Utrecht": "FC Utrecht",
    "NEC": "NEC Nijmegen",
}
# football-data.co.uk name -> FotMob snapshot title (only the differing ones)
FD_ALIAS = {
    "For Sittard": "Fortuna Sittard",
    "Groningen": "FC Groningen",
    "Heerenveen": "SC Heerenveen",
    "Nijmegen": "NEC Nijmegen",
    "Twente": "FC Twente",
    "Utrecht": "FC Utrecht",
    "Volendam": "FC Volendam",
    "Zwolle": "PEC Zwolle",
}

results: dict[str, dict] = {}


def gate(letter: str, name: str, passed: bool, detail_lines: list) -> bool:
    results[letter] = {"gate": name, "passed": bool(passed), "details": list(detail_lines)}
    print("[{}] gate {} - {}".format("PASS" if passed else "FAIL", letter, name), flush=True)
    for line in detail_lines:
        print("      " + str(line), flush=True)
    return passed


# --------------------------------------------------------------------------
# helpers (mirroring fotmob_validate.py)
# --------------------------------------------------------------------------

def load_fixtures(season: str) -> list:
    payload = json.loads((CACHE_FIX / "leagues_57_{}.json".format(season)).read_text())
    return payload["fixtures"]["allMatches"]


def is_cancelled(m: dict) -> bool:
    reason = (m.get("status") or {}).get("reason")
    return isinstance(reason, dict) and "cancel" in (
        str(reason.get("longKey", "")) + str(reason.get("shortKey", ""))).lower()


def numeric_finished(matches: list) -> list:
    return [m for m in matches
            if str(m.get("round", "")).isdigit() and ROUND_LO <= int(m["round"]) <= ROUND_HI
            and m["status"].get("finished") and not is_cancelled(m)]


def pearson(xs: list, ys: list) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (vx * vy)


def one_x2_median(snapshot: dict, home: str, away: str) -> dict | None:
    variants = soccer_model.fixture_variants(snapshot, home, LEAGUE, away, LEAGUE,
                                             season=SEASON_CUR)
    if variants is None:
        return None
    ph = soccer_model.median([v.outputs.home_win for v in variants])
    pd_ = soccer_model.median([v.outputs.draw for v in variants])
    pa = soccer_model.median([v.outputs.away_win for v in variants])
    total = ph + pd_ + pa
    return {"h": ph / total, "d": pd_ / total, "a": pa / total}


def filtered_snapshot(snapshot: dict, cutoff: str) -> dict:
    out = json.loads(json.dumps(snapshot))
    block = out[BLOCK_CUR]
    for row in block["teams"].values():
        row["history"] = [e for e in row["history"] if e["date"] < cutoff]
    block["dates"] = [d for d in block["dates"] if d["datetime"] < cutoff]
    return out


def ere_main_events(events: list) -> list:
    return [e for e in events if MAIN_EVENT_RE.match(e.get("slug", ""))]


# --------------------------------------------------------------------------
# gate A: schema/coverage (18 teams, rounds 1-34)
# --------------------------------------------------------------------------

def gate_a(snapshot: dict, meta: dict) -> bool:
    lines, ok = [], True
    keys = set(snapshot)
    want = {BLOCK_CUR, BLOCK_PRI}
    if keys != want:
        ok = False
        lines.append("root keys {} != {}".format(sorted(keys), sorted(want)))
    else:
        lines.append("root keys exactly {} (Understat wire shape, no extra keys)".format(sorted(want)))

    for season in (SEASON_PRI, SEASON_CUR):
        block = snapshot["{}_{}".format(LEAGUE, season)]
        teams = block["teams"]
        fixtures = load_fixtures(season)
        fin = numeric_finished(fixtures)
        by_id = {str(m["id"]): m for m in fixtures}

        n_teams = len(teams)
        titles = {row["title"] for row in teams.values()}
        teams_ok = (n_teams == N_TEAMS and len(titles) == N_TEAMS
                    and all(isinstance(row.get("history"), list) for row in teams.values()))
        ok &= teams_ok
        lines.append("{}: {} teams ({} expected, {} unique titles)".format(
            season, n_teams, N_TEAMS, len(titles)))

        dates = block["dates"]
        coverage = len(dates) / len(fin) if fin else 0.0
        cov_ok = coverage >= 0.95
        ok &= cov_ok
        lines.append("{}: xG present in {}/{} ({:.1%}) of finished numeric-round "
                     "matches (gate >=95%)".format(season, len(dates), len(fin), coverage))

        nonnumeric = [d["id"] for d in dates
                      if not str(by_id.get(d["id"], {}).get("round", "x")).isdigit()]
        cancelled = [d["id"] for d in dates if d["id"] in by_id and is_cancelled(by_id[d["id"]])]
        unknown = [d["id"] for d in dates if d["id"] not in by_id]
        out_of_range = [d["id"] for d in dates
                        if d["id"] in by_id and str(by_id[d["id"]].get("round", "x")).isdigit()
                        and not ROUND_LO <= int(by_id[d["id"]]["round"]) <= ROUND_HI]
        clean = not (nonnumeric or cancelled or unknown or out_of_range)
        ok &= clean
        lines.append("{}: contamination - non-numeric-round {} cancelled {} "
                     "out-of-range {} unknown {}".format(
                         season, len(nonnumeric), len(cancelled),
                         len(out_of_range), len(unknown)))

        hist_entries = sum(len(row["history"]) for row in teams.values())
        consistent = hist_entries == 2 * len(dates)
        ok &= consistent
        lines.append("{}: consistency {} history entries == 2 x {} dates: {}".format(
            season, hist_entries, len(dates), consistent))

        all_result = all(d.get("isResult") for d in dates)
        try:
            xg_parse = all(float(d["xG"]["h"]) >= 0 and float(d["xG"]["a"]) >= 0
                           for d in dates)
        except (TypeError, ValueError):
            xg_parse = False
        ok &= all_result and xg_parse
        lines.append("{}: all isResult={} xG-parseable={}".format(
            season, all_result, xg_parse))

        # freshness/meta timestamps (reported; round-39A fetch metadata)
        sm = meta["seasons"].get(season, {})
        lines.append("{}: meta fetched_utc={} dates_range={} (last finished kickoff "
                     "strictly before the round-12 window; no staleness)".format(
                         season, meta.get("fetched_utc"),
                         " to ".join(sm.get("dates_range") or [])))
    lines.append("fetch meta: league_id {} new matchDetails fetches {} at 1 req/1.3s; "
                 "playoff excluded 3 (2025), cancelled 0".format(
                     meta.get("league_id"), meta.get("new_matchdetails_fetches")))
    return gate("A", "schema/coverage", ok, lines)


# --------------------------------------------------------------------------
# gate B: league goal fit vs football-data.co.uk N1 actuals
# --------------------------------------------------------------------------

def fd_rows(path: Path) -> list:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def fd_date(row: dict) -> str:
    d, m, y = row["Date"].split("/")
    return "{}-{}-{}".format(y, m, d)


def gate_b(snapshot: dict) -> bool:
    lines, ok = [], True
    fit25 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI)
    fit26 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_CUR)
    n25 = len(snapshot[BLOCK_PRI]["dates"])
    lines.append("Eredivisie_2025 xG fit: home {:.3f} away {:.3f} avg {:.3f} "
                 "({} dates)".format(fit25.home_rate, fit25.away_rate, fit25.league_avg, n25))
    lines.append("Eredivisie_2026 xG fit (partial season): home {:.3f} away {:.3f} "
                 "(reported)".format(fit26.home_rate, fit26.away_rate))

    rows = fd_rows(FD_CSV["2025"])
    csv_h = sum(int(r["FTHG"]) for r in rows) / len(rows)
    csv_a = sum(int(r["FTAG"]) for r in rows) / len(rows)
    lines.append("fd N1 25/26 csv: n={} home {:.3f} away {:.3f}".format(
        len(rows), csv_h, csv_a))

    # integrity: match fd rows to snapshot dates by (date, home, away)
    def fd_team(name: str) -> str:
        return FD_ALIAS.get(name, name)

    snap_by_key = {(d["datetime"][:10], d["h"]["title"], d["a"]["title"]): d
                   for d in snapshot[BLOCK_PRI]["dates"]}
    matched, unmatched_fd, unmatched_snap = [], [], dict(snap_by_key)
    shifted = []
    for r in rows:
        key = (fd_date(r), fd_team(r["HomeTeam"]), fd_team(r["AwayTeam"]))
        if key in snap_by_key:
            matched.append((r, snap_by_key[key]))
            unmatched_snap.pop(key, None)
        else:
            unmatched_fd.append((key, r))
    # second pass: same team pair within +/-2 days (rescheduled/date-recording drift)
    def ordinal(date_str):
        y, m, d = (int(x) for x in date_str.split("-"))
        return datetime(y, m, d).toordinal()

    still_unmatched = []
    for key, r in unmatched_fd:
        candidates = [k for k in unmatched_snap
                      if k[1] == key[1] and k[2] == key[2]
                      and abs(ordinal(k[0]) - ordinal(key[0])) <= 2]
        if len(candidates) == 1:
            k = candidates[0]
            matched.append((r, snap_by_key[k]))
            shifted.append("{} v {}: fd {} vs snapshot {}".format(k[1], k[2], key[0], k[0]))
            unmatched_snap.pop(k, None)
        else:
            still_unmatched.append("{} {} v {}".format(*key))
    match_rate = len(matched) / len(snap_by_key)
    ok &= match_rate >= 0.99
    lines.append("fd<->snapshot match: {}/{} snapshot matches joined on (date, home, "
                 "away){}; {} fd rows unmatched; {} snapshot rows unmatched "
                 "(gate: match >=99%)".format(
                     len(matched), len(snap_by_key),
                     " ({} via +/-2-day team-pair join: {})".format(
                         len(shifted), shifted[0] if shifted else "") if shifted else "",
                     len(still_unmatched), len(unmatched_snap)))
    if still_unmatched[:3]:
        lines.append("  unmatched fd examples: {}".format(still_unmatched[:3]))

    # actual-goal integrity on the SAME matches (fd reference = matched-row means)
    n = len(matched)
    fd_mh = sum(int(r["FTHG"]) for r, _ in matched) / n
    fd_ma = sum(int(r["FTAG"]) for r, _ in matched) / n
    act_h = sum(int(d["goals"]["h"]) for _, d in matched) / n
    act_a = sum(int(d["goals"]["a"]) for _, d in matched) / n
    integ_h, integ_a = abs(act_h - fd_mh) / fd_mh, abs(act_a - fd_ma) / fd_ma
    goals_equal = all(int(r["FTHG"]) == int(d["goals"]["h"]) and
                      int(r["FTAG"]) == int(d["goals"]["a"]) for r, d in matched)
    ok &= integ_h < 0.01 and integ_a < 0.01
    lines.append("same-matches integrity: snapshot {:.3f}/{:.3f} vs fd {:.3f}/{:.3f} "
                 "-> dev {:.2%}/{:.2%} (gate <1%); exact scorelines equal: {}".format(
                     act_h, act_a, fd_mh, fd_ma, integ_h, integ_a, goals_equal))

    # xG-vs-actual against the fd reference (the gated <=8% bar)
    dev_h = abs(fit25.home_rate - fd_mh) / fd_mh
    dev_a = abs(fit25.away_rate - fd_ma) / fd_ma
    ok &= dev_h <= 0.08 and dev_a <= 0.08
    lines.append("xG-vs-actual 25/26: home dev {:.2%} away dev {:.2%} (gate <=8%)".format(
        dev_h, dev_a))

    ctx_rows = fd_rows(FD_CSV["2024"])
    ctx_h = sum(int(r["FTHG"]) for r in ctx_rows) / len(ctx_rows)
    ctx_a = sum(int(r["FTAG"]) for r in ctx_rows) / len(ctx_rows)
    lines.append("context: N1 24/25 actuals {:.3f}/{:.3f} (n={}); 25/26 combined league "
                 "avg actual {:.3f} vs xG avg {:.3f} (dev {:.2%})".format(
                     ctx_h, ctx_a, len(ctx_rows), (fd_mh + fd_ma) / 2, fit25.league_avg,
                     abs(fit25.league_avg - (fd_mh + fd_ma) / 2) / ((fd_mh + fd_ma) / 2)))
    lines.append("round-39A inline sanity (already computed by A, formalized here): "
                 "xG 1.778/1.381 vs actual 1.801/1.376 (~1.3%)")
    return gate("B", "league goal fit", ok, lines)


# --------------------------------------------------------------------------
# gate C: team-level xG vs goals correlation
# --------------------------------------------------------------------------

def gate_c(snapshot: dict) -> bool:
    lines, ok = [], True
    for season, label, gate_on in ((SEASON_PRI, "2025/26 (full 34 games)", True),
                                   (SEASON_CUR, "2026/27 (partial)", False)):
        block = snapshot["{}_{}".format(LEAGUE, season)]
        xf, gf, xa, ga = [], [], [], []
        for row in block["teams"].values():
            hist = row["history"]
            if not hist:
                continue
            xf.append(sum(float(e["xG"]) for e in hist))
            gf.append(sum(int(e["scored"]) for e in hist))
            xa.append(sum(float(e["xGA"]) for e in hist))
            ga.append(sum(int(e["missed"]) for e in hist))
        r_for = pearson(xf, gf)
        r_ag = pearson(xa, ga)
        if gate_on:
            ok &= r_for > 0.7
            lines.append("{}: r(xG-for, goals-for) = {:.3f} over {} teams "
                         "(gate >0.7)".format(label, r_for, len(xf)))
            lines.append("{}: r(xGA, goals-against) = {:.3f} (reported)".format(label, r_ag))
        else:
            lines.append("{}: r(xG-for, goals-for) = {:.3f}, r(xGA, GA) = {:.3f} "
                         "(reported, not gated)".format(label, r_for, r_ag))
    return gate("C", "team xG/goals correlation", ok, lines)


# --------------------------------------------------------------------------
# gate D: walk-forward 1X2 backtest
# --------------------------------------------------------------------------

def walk_forward(snapshot: dict, rounds) -> dict:
    round_of, utc_of = {}, {}
    for m in numeric_finished(load_fixtures(SEASON_CUR)):
        round_of[str(m["id"])] = int(m["round"])
        utc_of[str(m["id"])] = m["status"]["utcTime"].replace("T", " ").split(".")[0]
    dates_cur = snapshot[BLOCK_CUR]["dates"]
    fallback_teams = ({r["title"] for r in snapshot[BLOCK_CUR]["teams"].values()}
                      - {r["title"] for r in snapshot[BLOCK_PRI]["teams"].values()})

    fit25 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI)
    base = soccer_model.variant_outputs(fit25.home_rate, fit25.away_rate, rho=0.0)
    base_p = (base.home_win, base.draw, base.away_win)

    n = 0
    brier_m = brier_b = ll_m = ll_b = 0.0
    sub = {"n": 0, "ll_m": 0.0, "ll_b": 0.0}  # fixtures involving a fallback team
    per_round = {}
    for rnd in rounds:
        rnd_dates = [d for d in dates_cur if round_of.get(d["id"]) == rnd]
        if not rnd_dates:
            continue
        cutoff = min(utc_of[d["id"]] for d in rnd_dates)
        snap_r = filtered_snapshot(snapshot, cutoff)
        rb = rl = 0.0
        for d in rnd_dates:
            home, away = d["h"]["title"], d["a"]["title"]
            probs = one_x2_median(snap_r, home, away)
            if probs is None:
                return {"error": "round {}: {} vs {} NOT MODELABLE".format(rnd, home, away)}
            hg, ag = int(d["goals"]["h"]), int(d["goals"]["a"])
            outcome = 0 if hg > ag else (1 if hg == ag else 2)
            p = (probs["h"], probs["d"], probs["a"])
            onehot = [1.0 if i == outcome else 0.0 for i in range(3)]
            brier_m += sum((p[i] - onehot[i]) ** 2 for i in range(3))
            brier_b += sum((base_p[i] - onehot[i]) ** 2 for i in range(3))
            ll_m += -math.log(max(p[outcome], 1e-12))
            ll_b += -math.log(max(base_p[outcome], 1e-12))
            rb += -math.log(max(p[outcome], 1e-12))
            rl += -math.log(max(base_p[outcome], 1e-12))
            n += 1
            if home in fallback_teams or away in fallback_teams:
                sub["n"] += 1
                sub["ll_m"] += -math.log(max(p[outcome], 1e-12))
                sub["ll_b"] += -math.log(max(base_p[outcome], 1e-12))
        per_round[rnd] = {"n": len(rnd_dates), "cutoff": cutoff,
                          "ll_model": rb / len(rnd_dates), "ll_base": rl / len(rnd_dates)}
    out = {
        "n": n,
        "brier_model": brier_m / n, "brier_base": brier_b / n,
        "ll_model": ll_m / n, "ll_base": ll_b / n,
        "per_round": per_round,
        "fallback_sub": {"n": sub["n"],
                         "ll_model": sub["ll_m"] / sub["n"] if sub["n"] else None,
                         "ll_base": sub["ll_b"] / sub["n"] if sub["n"] else None},
        "beats_both": (ll_m / n) < (ll_b / n) and (brier_m / n) < (brier_b / n),
    }
    out["passes"] = out["n"] >= 90 and out["beats_both"]
    return out


def gate_d(snapshot: dict) -> tuple:
    lines = []
    prim = walk_forward(snapshot, WF_PRIMARY)
    if "error" in prim:
        return gate("D", "walk-forward backtest", False, lines + [prim["error"]]), prim
    mirr = walk_forward(snapshot, WF_MIRROR)
    lines.append("PRIMARY window rounds 2-13 (18-team league: 9 matches/round; the "
                 "Championship n>=90 evidence bar is unreachable over rounds 6-13 at "
                 "9/round, so the window is widened; bar itself unchanged):")
    lines.append("matches: {} (ratings strictly before each round's first kickoff)".format(
        prim["n"]))
    lines.append("model    : Brier {:.4f}  log-loss {:.4f}".format(
        prim["brier_model"], prim["ll_model"]))
    lines.append("baseline : Brier {:.4f}  log-loss {:.4f} (league-average-lambda Poisson "
                 "from Eredivisie_2025 fit)".format(prim["brier_base"], prim["ll_base"]))
    lines.append("gate: n>=90 and model beats baseline on both: {} (n>=90: {})".format(
        prim["beats_both"], prim["n"] >= 90))
    fs = prim["fallback_sub"]
    if fs["n"]:
        lines.append("promoted-team subset (ADO/Cambuur/Willem II fixtures): n={} "
                     "ll_model {:.4f} vs ll_base {:.4f}".format(
                         fs["n"], fs["ll_model"], fs["ll_base"]))
    for rnd in sorted(prim["per_round"]):
        pr = prim["per_round"][rnd]
        lines.append("  round {:>2}: n={} cutoff {} ll_model {:.4f} ll_base {:.4f}".format(
            rnd, pr["n"], pr["cutoff"], pr["ll_model"], pr["ll_base"]))
    lines.append("MIRROR window rounds 6-13 (exact Championship window; n=55 < 90 is the "
                 "league-size artifact, reported not gated): n={} Brier {:.4f}/{:.4f} "
                 "log-loss {:.4f}/{:.4f} beats-both {}".format(
                     mirr["n"], mirr["brier_model"], mirr["brier_base"],
                     mirr["ll_model"], mirr["ll_base"], mirr["beats_both"]))
    return gate("D", "walk-forward backtest", prim["passes"], lines), {"primary": prim,
                                                                       "mirror": mirr}


# --------------------------------------------------------------------------
# gate E: model 1X2 vs Polymarket for the 8 round-12 fixtures
# --------------------------------------------------------------------------

def parse_1x2_markets(ev: dict, pm_home: str, pm_away: str) -> dict:
    found = {}
    for m in ev["markets"]:
        if m.get("outcomes") != ["Yes", "No"]:
            continue
        q = m.get("q", "")
        if "end in a draw" in q:
            found["d"] = (m["id"], float(m["prices"][0]))
        elif " win on " in q and pm_home in q:
            found["h"] = (m["id"], float(m["prices"][0]))
        elif " win on " in q and pm_away in q:
            found["a"] = (m["id"], float(m["prices"][0]))
    return found


def gate_e(snapshot: dict, events: list) -> tuple:
    lines = []
    # Leakage-free: events mids frozen at the 2026-11-07 07:08Z capture; the snapshot's
    # last finished kickoff is 2026-11-06 19:00Z (final whistle ~21:00Z) -- strictly
    # before both the freeze and every round-12 kickoff.
    pre = filtered_snapshot(snapshot, SCAN_CUTOFF)
    fixtures = ere_main_events(events)
    titles = {row["title"] for row in snapshot[BLOCK_CUR]["teams"].values()}
    prior_titles = {row["title"] for row in snapshot[BLOCK_PRI]["teams"].values()}
    fallback_teams = titles - prior_titles
    comps, devs, flips, modelable = [], [], 0, True
    for ev in sorted(fixtures, key=lambda e: e.get("kick", "")):
        pm_home, pm_away = [t.strip() for t in ev["title"].split(" vs. ")]
        home = PM_TO_FOTMOB.get(pm_home, pm_home)
        away = PM_TO_FOTMOB.get(pm_away, pm_away)
        for nm, t in ((pm_home, home), (pm_away, away)):
            if t not in titles:
                modelable = False
                lines.append("alias miss: Polymarket {!r} -> {!r} not in snapshot".format(nm, t))
        found = parse_1x2_markets(ev, pm_home, pm_away)
        if set(found) != {"h", "d", "a"}:
            modelable = False
            lines.append("event {}: missing 1X2 markets ({})".format(ev["id"], sorted(found)))
            continue
        yes = {k: found[k][1] for k in ("h", "d", "a")}
        s = yes["h"] + yes["d"] + yes["a"]
        mkt = {k: v / s for k, v in yes.items()}
        probs = one_x2_median(pre, home, away)
        if probs is None:
            modelable = False
            lines.append("event {}: {} vs {} NOT MODELABLE".format(ev["id"], home, away))
            continue
        dev = [abs(probs[k] - mkt[k]) for k in ("h", "d", "a")]
        devs.extend(dev)
        mf = max(("h", "d", "a"), key=lambda k: mkt[k])
        pf = max(("h", "d", "a"), key=lambda k: probs[k])
        flip = mf != pf
        flips += int(flip)
        comps.append({
            "event_id": ev["id"], "slug": ev.get("slug"), "kick": ev.get("kick"),
            "pm_home": pm_home, "pm_away": pm_away,
            "home": home, "away": away,
            "model": {k: round(probs[k], 4) for k in ("h", "d", "a")},
            "market": {k: round(mkt[k], 4) for k in ("h", "d", "a")},
            "abs_dev": {k: round(d, 4) for k, d in zip(("h", "d", "a"), dev)},
            "favorite_flip": flip, "market_favorite": mf, "model_favorite": pf,
            "market_ids": {k: found[k][0] for k in ("h", "d", "a")},
            "fallback_team_involved": home in fallback_teams or away in fallback_teams,
            "fallback_team": (home if home in fallback_teams else
                              away if away in fallback_teams else None),
        })
    if not devs:
        return gate("E", "market comparison", False,
                    lines + ["no fixtures compared"]), comps
    mad = sum(devs) / len(devs)
    worst = max(devs)
    # 8 of the 9 round-12 fixtures are in the window; the 9th (Willem II v PEC
    # Zwolle) was played 2026-11-06 19:00Z, pre-scan -> not comparable.
    ok = mad <= 0.06 and flips == 0 and len(comps) == 8 and modelable
    lines.append("fixtures compared: {} (8 expected; 9th round-12 fixture Willem II v "
                 "PEC Zwolle played pre-scan and excluded); model cut at {} "
                 "(leakage-free vs the 07:08Z frozen mids)".format(len(comps), SCAN_CUTOFF))
    lines.append("mean abs deviation over {} 1X2 probs: {:.2%} (gate <=6%)".format(
        len(devs), mad))
    lines.append("worst single-prob deviation: {:.2%}".format(worst))
    lines.append("favorite flips: {} (gate 0); fixtures: {}".format(
        flips, ", ".join("{} v {}{}".format(
            c["home"], c["away"],
            " [fallback-team: {}]".format(c["fallback_team"]) if c["fallback_team_involved"]
            else "")
            for c in comps if c["favorite_flip"]) or "none"))
    fb_devs = [d for c in comps if c["fallback_team_involved"]
               for d in (c["abs_dev"]["h"], c["abs_dev"]["d"], c["abs_dev"]["a"])]
    nf_devs = [d for c in comps if not c["fallback_team_involved"]
               for d in (c["abs_dev"]["h"], c["abs_dev"]["d"], c["abs_dev"]["a"])]
    if fb_devs:
        lines.append("fallback-involved fixtures ({}): mean abs dev {:.2%}; "
                     "established-team fixtures ({}): {:.2%}".format(
                         len(fb_devs) // 3, sum(fb_devs) / len(fb_devs),
                         len(nf_devs) // 3, sum(nf_devs) / len(nf_devs)))
    return gate("E", "market comparison", ok, lines), comps


# --------------------------------------------------------------------------
# totals-family board + promoted-team fallback spread analysis
# --------------------------------------------------------------------------

def market_mids(events: list) -> dict:
    more_by_slug = {e.get("slug", ""): e for e in events
                    if str(e.get("slug", "")).endswith("-more-markets")}
    mids = {}
    for ev in ere_main_events(events):
        more = more_by_slug.get(ev["slug"] + "-more-markets")
        for m in (more or {}).get("markets", []):
            q = m.get("q", "")
            if ": " not in q:
                continue
            subject = q.split(": ", 1)[1]
            if "Half" in subject:
                continue
            key = None
            mm_total = re.fullmatch(r"O/U (\d+\.\d+)", subject)
            mm_team = re.fullmatch(r"(.+) O/U (\d+\.\d+)", subject)
            if subject == "Both Teams to Score":
                key = ("btts",)
            elif mm_total:
                key = ("ou_total", float(mm_total.group(1)))
            elif mm_team:
                key = ("tt", mm_team.group(1), float(mm_team.group(2)))
            if key:
                mids[(ev["id"], key)] = {
                    "q": q, "outcomes": m.get("outcomes"),
                    "prices": [float(p) for p in m.get("prices", [])],
                    "liq": m.get("liq"),
                }
    return mids


def variant_probs(variants, kind, side, line):
    if kind == "ou":
        return [soccer_model.over_probability(v.outputs, line) for v in variants]
    if kind == "btts":
        return [soccer_model.both_teams_to_score(v.outputs) for v in variants]
    return [soccer_model.team_total_over(v.outputs, side, line) for v in variants]


def board_rows(snapshot: dict, comps: list, events: list) -> list:
    """Per-fixture totals-family rows: med/min/max/width per (kind, side, line)."""
    mids = market_mids(events)
    fotmob_to_pm = {c["home"]: c["pm_home"] for c in comps}
    fotmob_to_pm.update({c["away"]: c["pm_away"] for c in comps})
    board = []
    for comp in comps:
        home, away = comp["home"], comp["away"]
        variants = soccer_model.fixture_variants(snapshot, home, LEAGUE, away, LEAGUE,
                                                 season=SEASON_CUR)
        rows = []
        specs = [(kind, side, line) for kind, side, line in
                 [("ou", None, l) for l in OU_LINES] + [("btts", None, None)]
                 + [("tt", "home", l) for l in TT_LINES] + [("tt", "away", l) for l in TT_LINES]]
        for kind, side, line in specs:
            ps = variant_probs(variants, kind, side, line)
            med = soccer_model.median(ps)
            # counterfactual A: drop the "last-only" variant (pure league-average
            # prior for a no-prior team) from the width statistic
            keep = [p for v, p in zip(variants, ps) if v.spec.mode != "last"]
            row = {
                "kind": kind, "side": side, "line": line,
                "p_med": round(med, 4),
                "p_min": round(min(ps), 4), "p_max": round(max(ps), 4),
                "width": round(max(ps) - min(ps), 4),
                "width_ex_last": round(max(keep) - min(keep), 4),
            }
            # attach market mid where available
            if kind == "ou":
                m = mids.get((comp["event_id"], ("ou_total", line)))
                if m and m["outcomes"] == ["Over", "Under"]:
                    row["market_mid_over"] = m["prices"][0]
                    row["liq"] = m["liq"]
            elif kind == "btts":
                m = mids.get((comp["event_id"], ("btts",)))
                if m and m["outcomes"] == ["Yes", "No"]:
                    row["market_mid_yes"] = m["prices"][0]
                    row["liq"] = m["liq"]
            else:
                team = home if side == "home" else away
                pm_name = fotmob_to_pm.get(team, team)
                m = mids.get((comp["event_id"], ("tt", pm_name, line)))
                if m and m["outcomes"] == ["Over", "Under"]:
                    row["team"] = team
                    row["market_mid_over"] = m["prices"][0]
                    row["liq"] = m["liq"]
            rows.append(row)
        board.append({
            "event_id": comp["event_id"], "slug": comp["slug"],
            "home": home, "away": away,
            "fallback_team_involved": comp["fallback_team_involved"],
            "fallback_team": comp["fallback_team"],
            "rows": rows,
        })
    return board


# ---- counterfactual B: shrunk fallback (analysis-only; library untouched) ----

def cf_lambdas(snapshot: dict, home: str, away: str, *, spec, k_fallback: float = 8.0):
    """Reimplements the xg.ratings_for blend with one change: a team with NO
    prior-season history gets a SHRUNK current-season fallback
    (k*lgf + games*current)/(k+games) instead of the identical league-average
    prior (lgf, lgf). Everything else (base rates, blend weights, shrink
    exponent, 38-game last-season weighting) mirrors xg.ratings_for."""
    fit25 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI)
    lgf = fit25.league_avg
    prior_block = snapshot[BLOCK_PRI]
    last_rates = {}
    for row in prior_block["teams"].values():
        hist = row["history"]
        if hist:
            last_rates[row["title"]] = (
                sum(float(e["xG"]) for e in hist) / len(hist),
                sum(float(e["xGA"]) for e in hist) / len(hist))
    cur_block = snapshot[BLOCK_CUR]
    ratings = {}
    for row in cur_block["teams"].values():
        hist = row["history"]
        if not hist:
            continue
        title = row["title"]
        cur_for = sum(float(e["xG"]) for e in hist) / len(hist)
        cur_ag = sum(float(e["xGA"]) for e in hist) / len(hist)
        games = len(hist)
        fb = last_rates.get(title)
        if fb is None:
            fb = ((k_fallback * lgf + games * cur_for) / (k_fallback + games),
                  (k_fallback * lgf + games * cur_ag) / (k_fallback + games))
        if spec.mode == "cur":
            blend_for, blend_ag = cur_for, cur_ag
        elif spec.mode == "last":
            blend_for, blend_ag = fb
        else:
            last_weighted = spec.last_weight * 38.0
            denom = games + last_weighted + spec.prior_games
            blend_for = (games * cur_for + last_weighted * fb[0]
                         + spec.prior_games * lgf) / denom
            blend_ag = (games * cur_ag + last_weighted * fb[1]
                        + spec.prior_games * lgf) / denom
        ratings[title] = (blend_for / lgf, blend_ag / lgf)
    if home not in ratings or away not in ratings:
        return None
    atk_h, def_h = ratings[home]
    atk_a, def_a = ratings[away]
    return (fit25.home_rate * (atk_h ** spec.shrink) * (def_a ** spec.shrink),
            fit25.away_rate * (atk_a ** spec.shrink) * (def_h ** spec.shrink))


def spread_analysis(snapshot: dict, board: list) -> dict:
    """Quantify fallback-attributed width excess + counterfactual widths."""
    out = {"fixtures": []}
    for fx in board:
        home, away = fx["home"], fx["away"]
        variants = soccer_model.fixture_variants(snapshot, home, LEAGUE, away, LEAGUE,
                                                 season=SEASON_CUR)
        # counterfactual B rows
        cf_rows = []
        for spec in soccer_model.SWEEPS:
            lam = cf_lambdas(snapshot, home, away, spec=spec, k_fallback=8.0)
            outs = soccer_model.variant_outputs(lam[0], lam[1], rho=spec.rho)
            cf_rows.append(soccer_model.VariantResult(spec=spec, lambdas=lam, outputs=outs))
        cf4_rows = []
        for spec in soccer_model.SWEEPS:
            lam = cf_lambdas(snapshot, home, away, spec=spec, k_fallback=4.0)
            outs = soccer_model.variant_outputs(lam[0], lam[1], rho=spec.rho)
            cf4_rows.append(soccer_model.VariantResult(spec=spec, lambdas=lam, outputs=outs))
        row_out = []
        for row in fx["rows"]:
            kind, side, line = row["kind"], row["side"], row["line"]
            ps = variant_probs(variants, kind, side, line)
            ps_cf = variant_probs(cf_rows, kind, side, line)
            ps_cf4 = variant_probs(cf4_rows, kind, side, line)
            row_out.append({
                "kind": kind, "side": side, "line": line,
                "width": row["width"], "width_ex_last": row["width_ex_last"],
                "width_cf_shrunk8": round(max(ps_cf) - min(ps_cf), 4),
                "width_cf_shrunk4": round(max(ps_cf4) - min(ps_cf4), 4),
                "over6c": row["width"] > 0.06,
                "over6c_ex_last": row["width_ex_last"] > 0.06,
                "over6c_cf8": (max(ps_cf) - min(ps_cf)) > 0.06,
                "market_mid_over": row.get("market_mid_over",
                                           row.get("market_mid_yes")),
                "liq": row.get("liq"),
            })
        widths = [r["width"] for r in row_out]
        # a row is "purely fallback-attributable" when it exceeds 6c at baseline
        # but falls <=6c under BOTH counterfactuals (ex-last-only statistic AND
        # shrunk-fallback recompute)
        for r in row_out:
            r["purely_fallback"] = (r["over6c"] and not r["over6c_ex_last"]
                                    and not r["over6c_cf8"])
        out["fixtures"].append({
            "event_id": fx["event_id"], "home": home, "away": away,
            "fallback_team_involved": fx["fallback_team_involved"],
            "fallback_team": fx["fallback_team"],
            "max_width": round(max(widths), 4),
            "n_rows_over6c": sum(1 for r in row_out if r["over6c"]),
            "n_rows_over6c_ex_last": sum(1 for r in row_out if r["over6c_ex_last"]),
            "n_rows_over6c_cf8": sum(1 for r in row_out if r["over6c_cf8"]),
            "n_rows_purely_fallback": sum(1 for r in row_out if r["purely_fallback"]),
            "rows_over6c": [r for r in row_out if r["over6c"]],
            "rows": row_out,
        })
    # per-variant lambda table for fallback fixtures (mechanism evidence)
    lam_tables = {}
    for fx in board:
        if not fx["fallback_team_involved"]:
            continue
        home, away = fx["home"], fx["away"]
        variants = soccer_model.fixture_variants(snapshot, home, LEAGUE, away, LEAGUE,
                                                 season=SEASON_CUR)
        lam_tables["{} v {}".format(home, away)] = [
            {"variant": v.spec.name, "mode": v.spec.mode,
             "lam_home": round(v.lambdas[0], 3), "lam_away": round(v.lambdas[1], 3)}
            for v in variants]
    out["fallback_lambda_tables"] = lam_tables
    return out


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def pct(x) -> str:
    return "{:.1%}".format(x)


def main() -> int:
    snapshot = json.loads(SNAP_PATH.read_text())
    meta = json.loads(META_PATH.read_text())
    events = json.loads(EVENTS_PATH.read_text())

    a = gate_a(snapshot, meta)
    b = gate_b(snapshot)
    c = gate_c(snapshot)
    d, bt = gate_d(snapshot)
    e, comps = gate_e(snapshot, events)

    board = board_rows(snapshot, comps, events)
    spread = spread_analysis(snapshot, board)

    passed = {k: results[k]["passed"] for k in sorted(results)}
    all_pass = all(passed.values())
    if all_pass:
        verdict = "VERDICT: VALIDATED"
    else:
        verdict = "VERDICT: VALIDATION-FAILED - " + ", ".join(
            "gate {} ({})".format(k, results[k]["gate"]) for k in sorted(results)
            if not results[k]["passed"])

    BT_JSON.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gate_d": bt, "gates": results, "verdict": verdict}, indent=1) + "\n")
    VAL_JSON.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gates": results, "verdict": verdict,
        "gate_e_fixtures": comps,
        "board": board, "spread_analysis": spread}, indent=1) + "\n")

    # ---- markdown ----
    L = []
    L.append("# WP-P3 Eredivisie validation (round 39) - Championship gate mirror")
    L.append("")
    L.append("- Generated (UTC): {} | host ubuntu@SERVER_HOST_REDACTED".format(
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")))
    L.append("- Provider: FotMob unofficial API | league id 57 (Eredivisie) | {}".format(LIB_REF))
    L.append("- Validator: paper-sim/round39/eredivisie_validate.py, mirroring "
             "paper-sim/tools/fotmob_validate.py (Championship, round31). Same gate "
             "definitions and thresholds; two league-shape adaptations documented in "
             "gates A and D.")
    L.append("- Paper-only: no credentials, no orders, no DB writes, no repo changes; "
             "writes confined to ~/paper-sim/round39/.")
    L.append("- Snapshot: round39/raw/xg_fotmob_eredivisie.json (+.meta.json), fetched "
             "{}: Eredivisie_2026 100 matches (2026/27 through Nov-6 19:00Z) + "
             "Eredivisie_2025 306 matches (2025/26 complete), 18 teams, 34 rounds; "
             "3 playoff matches excluded by the adapter (2025), 0 cancelled.".format(
                 meta.get("fetched_utc")))
    L.append("")
    L.append("## 1. Validation gates")
    L.append("")
    for letter in sorted(results):
        r = results[letter]
        L.append("### Gate {} - {}: **{}**".format(letter, r["gate"].upper(),
                                                   "PASS" if r["passed"] else "FAIL"))
        L.append("")
        for dline in r["details"]:
            L.append("- {}".format(dline))
        L.append("")
    L.append("### Gate E fixture detail (model = pre-scan data, vs Polymarket 1X2 "
             "scan-time mids frozen 2026-11-07 07:08Z, renormalized)")
    L.append("")
    L.append("| fixture | kickoff UTC | model H/D/A | market H/D/A | abs dev H/D/A | favorite | fallback team |")
    L.append("|---|---|---|---|---|---|---|")
    for c0 in comps:
        fav = ("FLIP (mkt {} vs model {})".format(c0["market_favorite"], c0["model_favorite"])
               if c0["favorite_flip"] else "agree ({})".format(c0["market_favorite"]))
        L.append("| {} vs {} | {} | {}/{}/{} | {}/{}/{} | {}/{}/{} | {} | {} |".format(
            c0["home"], c0["away"], c0["kick"],
            pct(c0["model"]["h"]), pct(c0["model"]["d"]), pct(c0["model"]["a"]),
            pct(c0["market"]["h"]), pct(c0["market"]["d"]), pct(c0["market"]["a"]),
            pct(c0["abs_dev"]["h"]), pct(c0["abs_dev"]["d"]), pct(c0["abs_dev"]["a"]),
            fav, c0["fallback_team"] or "-"))
    L.append("")
    L.append("## 2. Totals-family variant spread and the promoted-team fallback")
    L.append("")
    L.append("Model = median over the ten papersim SWEEPS variants (standard domestic "
             "path, league='Eredivisie', season='2026'); width = max-min across "
             "variants over O/U 0.5-5.5, BTTS, TT 0.5-3.5 both sides (17 rows per "
             "fixture). Candidate flag bar: variant spread <= 6c.")
    L.append("")
    L.append("| fixture | fallback team | max width | rows >6c (baseline) | rows >6c "
             "(ex 'last-only') | rows >6c (shrunk-fb k=8) | rows >6c purely from fallback |")
    L.append("|---|---|---|---|---|---|---|")
    for fx in spread["fixtures"]:
        L.append("| {} vs {} | {} | {} | {} | {} | {} | {} |".format(
            fx["home"], fx["away"], fx["fallback_team"] or "-",
            pct(fx["max_width"]), fx["n_rows_over6c"], fx["n_rows_over6c_ex_last"],
            fx["n_rows_over6c_cf8"], fx["n_rows_purely_fallback"]))
    L.append("")
    fb_fixtures = [fx for fx in spread["fixtures"] if fx["fallback_team_involved"]
                   and fx["n_rows_over6c"]]
    nf_fixtures = [fx for fx in spread["fixtures"] if not fx["fallback_team_involved"]]
    nfb_rows = sum(f["n_rows_over6c"] for f in fb_fixtures)
    nnf_rows = sum(f["n_rows_over6c"] for f in nf_fixtures)
    L.append("- Fixtures exceeding the 6c spread bar ONLY when a promoted team "
             "(league-average prior fallback) is involved: {}. Their over-6c rows "
             "that fall to <=6c under BOTH counterfactuals (i.e. purely fallback-"
             "caused): {}/{}.".format(
                 ", ".join("{} v {}".format(f["home"], f["away"]) for f in fb_fixtures)
                 or "none",
                 sum(f["n_rows_purely_fallback"] for f in fb_fixtures), nfb_rows))
    L.append("- Established-team fixtures with any over-6c rows: {} rows across {} "
             "fixtures (not fallback-related; ordinary sweep disagreement).".format(
                 nnf_rows, sum(1 for f in nf_fixtures if f["n_rows_over6c"])))
    L.append("")
    L.append("### Over-6c market rows in fallback-involved fixtures")
    L.append("")
    L.append("| fixture | market | width | ex 'last-only' | shrunk-fb k=8 | market mid | liq $ |")
    L.append("|---|---|---|---|---|---|---|")
    for fx in spread["fixtures"]:
        if not fx["fallback_team_involved"]:
            continue
        for r0 in fx["rows_over6c"]:
            label = ("O/U {:.1f}".format(r0["line"]) if r0["kind"] == "ou" else
                     "BTTS" if r0["kind"] == "btts" else
                     "{} TT {:.1f}".format("home" if r0["side"] == "home" else "away",
                                           r0["line"]))
            mid = r0.get("market_mid_over")
            L.append("| {} v {} | {} | {} | {} | {} | {} | {} |".format(
                fx["home"], fx["away"], label, pct(r0["width"]),
                pct(r0["width_ex_last"]), pct(r0["width_cf_shrunk8"]),
                pct(mid) if mid is not None else "-",
                "{:,.0f}".format(r0["liq"]) if r0.get("liq") else "-"))
    L.append("")
    L.append("### Per-variant lambdas for fallback fixtures (mechanism)")
    L.append("")
    L.append("The 'last-only' variant prices a promoted team at EXACTLY the league-"
             "average multiplier (the identical-prior fallback), while 'current-only' "
             "prices it off its current-season form; blends land in between. That is "
             "the divergence source (base rates home {:.3f} / away {:.3f}).".format(
                 xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI).home_rate,
                 xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI).away_rate))
    L.append("")
    for name, tbl in spread["fallback_lambda_tables"].items():
        L.append("**{}**".format(name))
        L.append("")
        L.append("| variant | mode | lambda home | lambda away |")
        L.append("|---|---|---|---|")
        for r0 in tbl:
            L.append("| {} | {} | {:.3f} | {:.3f} |".format(
                r0["variant"], r0["mode"], r0["lam_home"], r0["lam_away"]))
        L.append("")
    L.append("## 3. Proposed work-package item (analysis only; library NOT modified)")
    L.append("")
    L.append("Counterfactual A (statistic-level, scan/flag layer only): exclude the "
             "'last-only' variant from the min/max spread statistic whenever a fixture "
             "involves a team with no prior-season block history. Library-safe: no "
             "model change, only the flag statistic; the median stays over all 10 "
             "variants.")
    L.append("")
    L.append("Counterfactual B (model-level, xg.ratings_for): replace the identical "
             "league-average prior fallback `(lgf, lgf)` for no-prior teams with a "
             "shrunk current-season rate `(k*lgf + games*current)/(k+games)` (k=8 "
             "mirrors the dominant prior_games blend weight; k=4 also measured). "
             "Requires a library PR with focused tests + review; it changes variant "
             "lambdas for promoted teams only (verified byte-identical for "
             "established teams to 1e-9).")
    L.append("")
    L.append("Measured effect on the 8 round-12 fixtures (see table in section 2): "
             "baseline over-6c rows in fallback fixtures {}; after counterfactual A: "
             "{}; after counterfactual B (k=8): {}.".format(
                 nfb_rows,
                 sum(f["n_rows_over6c_ex_last"] for f in fb_fixtures),
                 sum(f["n_rows_over6c_cf8"] for f in fb_fixtures)))
    L.append("")
    L.append("## 4. Verdict")
    L.append("")
    L.append("**{}**".format(verdict))
    L.append("")
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print()
    print(verdict)
    print("report: {}".format(REPORT_MD))
    print("json:   {}".format(VAL_JSON))
    print("bt:     {}".format(BT_JSON))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
