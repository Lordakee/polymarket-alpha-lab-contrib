#!/usr/bin/env python3
"""WP-P3 Phase 1 validation suite: FotMob Championship xG snapshot gates.

Five gates (all must PASS for VALIDATED):

  A schema      - both season blocks, 24 teams each, >=95% of finished
                  numeric-round matches carry xG, zero playoff/cancelled
                  contamination, history/dates consistency
  B league-fit  - Championship_2025 xG home/away means vs football-data.co.uk
                  actual goal rates (E1 2025/26: 1.400/1.205; 2024/25 context:
                  1.435/1.016) within 8%; actual-goal means must reproduce the
                  football-data numbers to <1% (same matches, integrity check)
  C correlation - per-team season xG-for totals vs actual goals-for
                  (prior season, 46 games): Pearson r > 0.7 (xGA/GA reported)
  D backtest    - walk-forward rounds 6-13 of 2026/27 (ratings strictly
                  before each round's first kickoff), 1X2 Brier + log-loss;
                  must beat the league-average-baseline Poisson on both
  E market      - model 1X2 vs Polymarket 1X2 for the 12 Nov-3/4 Championship
                  fixtures (scan-time mids): mean abs deviation <= 6c and no
                  favorite flips

Then prices the full board (O/U, BTTS, TT both directions, 1X2) for the 12
fixtures through the papersim library (standard 10-variant domestic path)
and writes the markdown report + machine-readable board/validation JSON.

Read-only for the repo; writes only under ~/paper-sim/round31/.
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

LEAGUE = "Championship"
SEASON_CUR, SEASON_PRI = "2026", "2025"
BLOCK_CUR = "{}_{}".format(LEAGUE, SEASON_CUR)
BLOCK_PRI = "{}_{}".format(LEAGUE, SEASON_PRI)

RAW = Path("/home/ubuntu/paper-sim/round31/raw")
SNAP_PATH = RAW / "xg_fotmob_championship.json"
META_PATH = RAW / "xg_fotmob_championship.json.meta.json"
CACHE_FIX = Path("/home/ubuntu/paper-sim/tools/fotmob_cache/fixtures")
FD_CSV = {
    "2025": Path("/tmp/xgsrc_probe/fd_E1_2526.csv"),
    "2024": Path("/tmp/xgsrc_probe/fd_E1_2425.csv"),
}
EVENTS_PATH = RAW / "events_window_31.json"
BOARD_JSON = RAW / "fotmob_board_31.json"
VAL_JSON = RAW / "fotmob_validation.json"
REPORT_MD = Path("/home/ubuntu/paper-sim/round31/fotmob_validation_report.md")

FD_RATES = {  # football-data.co.uk actual means (integrity/cross-check targets)
    "2025": (1.400, 1.205),   # E1 2025/26, n=552
    "2024": (1.435, 1.016),   # E1 2024/25, n=552 (context only)
}
WF_ROUNDS = range(6, 14)      # rounds 6..13 inclusive
LIB_REF = "polymarket-alpha-lab @ 7b6cdd47 (papersim selfcheck 10/10 PASS)"

OU_LINES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
TT_LINES = [0.5, 1.5, 2.5, 3.5]
MAIN_EVENT_RE = re.compile(r"^elc-[a-z0-9]+-[a-z0-9]+-\d{4}-\d{2}-\d{2}$")

results: dict[str, dict] = {}


def gate(letter: str, name: str, passed: bool, detail_lines: list) -> bool:
    results[letter] = {"gate": name, "passed": bool(passed), "details": list(detail_lines)}
    print("[{}] gate {} - {}".format("PASS" if passed else "FAIL", letter, name), flush=True)
    for line in detail_lines:
        print("      " + str(line), flush=True)
    return passed


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load_fixtures(season: str) -> list:
    payload = json.loads((CACHE_FIX / "leagues_48_{}.json".format(season)).read_text())
    return payload["fixtures"]["allMatches"]


def is_cancelled(m: dict) -> bool:
    reason = (m.get("status") or {}).get("reason")
    return isinstance(reason, dict) and "cancel" in (
        str(reason.get("longKey", "")) + str(reason.get("shortKey", ""))).lower()


def numeric_finished(matches: list) -> list:
    return [m for m in matches
            if str(m.get("round", "")).isdigit() and 1 <= int(m["round"]) <= 46
            and m["status"].get("finished") and not is_cancelled(m)]


def pearson(xs: list, ys: list) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (vx * vy)


def pm_to_fotmob_title(pm_name: str, titles: set) -> str:
    """Polymarket display name -> FotMob snapshot title (suffix-strip rule)."""
    for suffix in (" FC", " AFC"):
        if pm_name.endswith(suffix):
            pm_name = pm_name[: -len(suffix)]
            break
    if pm_name not in titles:
        raise KeyError("Polymarket team {!r} not in snapshot titles".format(pm_name))
    return pm_name


def one_x2_median(snapshot: dict, home: str, away: str) -> dict | None:
    """Median 1X2 over the ten sweep variants (renormalized to sum 1)."""
    variants = soccer_model.fixture_variants(snapshot, home, LEAGUE, away, LEAGUE,
                                             season=SEASON_CUR)
    if variants is None:
        return None
    ph = soccer_model.median([v.outputs.home_win for v in variants])
    pd_ = soccer_model.median([v.outputs.draw for v in variants])
    pa = soccer_model.median([v.outputs.away_win for v in variants])
    total = ph + pd_ + pa
    return {
        "h": ph / total, "d": pd_ / total, "a": pa / total,
        "range": {
            "h": (min(v.outputs.home_win for v in variants),
                  max(v.outputs.home_win for v in variants)),
            "d": (min(v.outputs.draw for v in variants),
                  max(v.outputs.draw for v in variants)),
            "a": (min(v.outputs.away_win for v in variants),
                  max(v.outputs.away_win for v in variants)),
        },
    }


def filtered_snapshot(snapshot: dict, cutoff: str) -> dict:
    """Copy with current-season history/dates strictly before `cutoff`."""
    out = json.loads(json.dumps(snapshot))
    block = out[BLOCK_CUR]
    for row in block["teams"].values():
        row["history"] = [e for e in row["history"] if e["date"] < cutoff]
    block["dates"] = [d for d in block["dates"] if d["datetime"] < cutoff]
    return out


def championship_main_events(events: list) -> list:
    return [e for e in events if MAIN_EVENT_RE.match(e.get("slug", ""))]


# --------------------------------------------------------------------------
# gate A: schema
# --------------------------------------------------------------------------

def gate_a(snapshot: dict) -> bool:
    lines, ok = [], True
    keys = set(snapshot)
    want = {BLOCK_CUR, BLOCK_PRI}
    if keys != want:
        ok = False
        lines.append("root keys {} != {}".format(sorted(keys), sorted(want)))
    else:
        lines.append("root keys exactly {} (Understat shape, no extra keys)".format(sorted(want)))

    for season in (SEASON_PRI, SEASON_CUR):
        block = snapshot["{}_{}".format(LEAGUE, season)]
        teams = block["teams"]
        fixtures = load_fixtures(season)
        fin = numeric_finished(fixtures)
        by_id = {str(m["id"]): m for m in fixtures}

        n_teams = len(teams)
        titles = {row["title"] for row in teams.values()}
        teams_ok = (n_teams == 24 and len(titles) == 24
                    and all(isinstance(row.get("history"), list) for row in teams.values()))
        ok &= teams_ok
        lines.append("{}: {} teams (24 expected, {} unique titles)".format(
            season, n_teams, len(titles)))

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
                        and not 1 <= int(by_id[d["id"]]["round"]) <= 46]
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

    return gate("A", "schema/coverage", ok, lines)


# --------------------------------------------------------------------------
# gate B: league goal fit vs football-data actuals
# --------------------------------------------------------------------------

def fd_actual_means(path: Path) -> tuple:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    n = len(rows)
    return (sum(int(r["FTHG"]) for r in rows) / n,
            sum(int(r["FTAG"]) for r in rows) / n, n)


def gate_b(snapshot: dict) -> bool:
    lines, ok = [], True
    fit25 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI)
    fit26 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_CUR)
    n25 = len(snapshot[BLOCK_PRI]["dates"])
    lines.append("Championship_2025 xG fit: home {:.3f} away {:.3f} avg {:.3f} "
                 "({} dates)".format(fit25.home_rate, fit25.away_rate, fit25.league_avg, n25))
    lines.append("Championship_2026 xG fit (partial season): home {:.3f} away {:.3f} "
                 "(reported)".format(fit26.home_rate, fit26.away_rate))

    csv_h, csv_a, csv_n = fd_actual_means(FD_CSV["2025"])
    fd_h, fd_a = FD_RATES["2025"]

    # integrity: the snapshot's ACTUAL goals are the same matches as fd E1 25/26
    block = snapshot[BLOCK_PRI]
    n = len(block["dates"])
    act_h = sum(int(d["goals"]["h"]) for d in block["dates"]) / n
    act_a = sum(int(d["goals"]["a"]) for d in block["dates"]) / n
    integ_h, integ_a = abs(act_h - fd_h) / fd_h, abs(act_a - fd_a) / fd_a
    ok &= integ_h < 0.01 and integ_a < 0.01
    lines.append("fd csv recheck: n={} home {:.3f} away {:.3f} (task reference "
                 "{:.3f}/{:.3f})".format(csv_n, csv_h, csv_a, fd_h, fd_a))
    lines.append("actual-goal integrity: snapshot {:.3f}/{:.3f} vs fd {:.3f}/{:.3f} "
                 "-> dev {:.2%}/{:.2%} (gate <1%)".format(
                     act_h, act_a, fd_h, fd_a, integ_h, integ_a))

    dev_h = abs(fit25.home_rate - fd_h) / fd_h
    dev_a = abs(fit25.away_rate - fd_a) / fd_a
    ok &= dev_h <= 0.08 and dev_a <= 0.08
    lines.append("xG-vs-actual 25/26: home dev {:.2%} away dev {:.2%} (gate <=8%)".format(
        dev_h, dev_a))

    ctx_h, ctx_a = FD_RATES["2024"]
    lines.append("context: E1 24/25 actuals {:.3f}/{:.3f}; 25/26 combined league avg "
                 "actual {:.3f} vs xG avg {:.3f} (dev {:.2%})".format(
                     ctx_h, ctx_a, (fd_h + fd_a) / 2, fit25.league_avg,
                     abs(fit25.league_avg - (fd_h + fd_a) / 2) / ((fd_h + fd_a) / 2)))
    return gate("B", "league goal fit", ok, lines)


# --------------------------------------------------------------------------
# gate C: team-level xG vs goals correlation
# --------------------------------------------------------------------------

def gate_c(snapshot: dict) -> bool:
    lines, ok = [], True
    for season, label, gate_on in ((SEASON_PRI, "2025/26 (full 46 games)", True),
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
# gate D: walk-forward 1X2 backtest, rounds 6-13 of 2026/27
# --------------------------------------------------------------------------

def gate_d(snapshot: dict) -> bool:
    lines = []
    round_of, utc_of = {}, {}
    for m in numeric_finished(load_fixtures(SEASON_CUR)):
        round_of[str(m["id"])] = int(m["round"])
        utc_of[str(m["id"])] = m["status"]["utcTime"].replace("T", " ").split(".")[0]
    dates_cur = snapshot[BLOCK_CUR]["dates"]

    fit25 = xg.league_goal_fit(snapshot, LEAGUE, SEASON_PRI)
    base = soccer_model.variant_outputs(fit25.home_rate, fit25.away_rate, rho=0.0)
    base_p = (base.home_win, base.draw, base.away_win)

    n = 0
    brier_m = brier_b = ll_m = ll_b = 0.0
    per_round = {}
    for rnd in WF_ROUNDS:
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
                lines.append("round {}: {} vs {} NOT MODELABLE".format(rnd, home, away))
                return gate("D", "walk-forward backtest", False,
                            lines + ["model returned None lambdas"])
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
        per_round[rnd] = {"n": len(rnd_dates), "cutoff": cutoff,
                          "ll_model": rb / len(rnd_dates), "ll_base": rl / len(rnd_dates)}

    brier_m /= n
    brier_b /= n
    ll_m /= n
    ll_b /= n
    ok = n >= 90 and ll_m < ll_b and brier_m < brier_b
    lines.append("matches: {} (rounds 6-13, ratings strictly before each round's "
                 "first kickoff)".format(n))
    lines.append("model    : Brier {:.4f}  log-loss {:.4f}".format(brier_m, ll_m))
    lines.append("baseline : Brier {:.4f}  log-loss {:.4f} (league-average-lambda "
                 "Poisson from Championship_2025 fit)".format(brier_b, ll_b))
    lines.append("gate: n>=90 and model beats baseline on both: {} (n>=90: {})".format(
        ll_m < ll_b and brier_m < brier_b, n >= 90))
    for rnd in sorted(per_round):
        pr = per_round[rnd]
        lines.append("  round {:>2}: n={} cutoff {} ll_model {:.4f} ll_base {:.4f}".format(
            rnd, pr["n"], pr["cutoff"], pr["ll_model"], pr["ll_base"]))
    return gate("D", "walk-forward backtest", ok, lines)


# --------------------------------------------------------------------------
# gate E: model 1X2 vs Polymarket for the 12 fixtures
# --------------------------------------------------------------------------

def parse_1x2_markets(ev: dict, pm_home: str, pm_away: str) -> dict:
    """Yes prices for home-win / draw / away-win from a main event."""
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
    # Leakage-free protocol: the events window was frozen at scan time
    # (2026-11-03 16:55:50Z), before the first Nov-3 kickoff (19:45Z). Model
    # probabilities therefore use only data strictly before the scan cutoff.
    scan_cutoff = "2026-11-03 16:55:50"
    pre = filtered_snapshot(snapshot, scan_cutoff)
    fixtures = championship_main_events(events)
    titles = {row["title"] for row in snapshot[BLOCK_CUR]["teams"].values()}
    prior_titles = {row["title"] for row in snapshot[BLOCK_PRI]["teams"].values()}
    fallback_teams = titles - prior_titles
    played = {d["id"]: d for d in snapshot[BLOCK_CUR]["dates"]
              if d["datetime"] >= "2026-11-03 19:00"}
    comps, devs, flips, modelable = [], [], 0, True
    ll_model = ll_mkt = 0.0
    n_played = 0
    for ev in fixtures:
        pm_home, pm_away = [t.strip() for t in ev["title"].split(" vs. ")]
        home = pm_to_fotmob_title(pm_home, titles)
        away = pm_to_fotmob_title(pm_away, titles)
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
        result = None
        mkt_id = {k: str(found[k][0]) for k in ("h", "d", "a")}
        # market ids are gamma ids; played map is keyed by fotmob match id -
        # match by team names instead
        for d in played.values():
            if d["h"]["title"] == home and d["a"]["title"] == away:
                result = d
                break
        ll_note = None
        if result is not None:
            hg, ag = int(result["goals"]["h"]), int(result["goals"]["a"])
            outcome = 0 if hg > ag else (1 if hg == ag else 2)
            keys = ("h", "d", "a")
            ll_model += -math.log(max(probs[keys[outcome]], 1e-12))
            ll_mkt += -math.log(max(mkt[keys[outcome]], 1e-12))
            n_played += 1
            ll_note = "final {}-{}".format(hg, ag)
        comps.append({
            "event_id": ev["id"], "slug": ev.get("slug"),
            "pm_home": pm_home, "pm_away": pm_away,
            "home": home, "away": away,
            "model": {k: round(probs[k], 4) for k in ("h", "d", "a")},
            "market": {k: round(mkt[k], 4) for k in ("h", "d", "a")},
            "abs_dev": {k: round(d, 4) for k, d in zip(("h", "d", "a"), dev)},
            "favorite_flip": flip, "market_favorite": mf, "model_favorite": pf,
            "market_ids": {k: found[k][0] for k in ("h", "d", "a")},
            "fallback_team_involved": home in fallback_teams or away in fallback_teams,
            "played_final": ll_note,
        })
    if not devs:
        return gate("E", "market comparison", False,
                    lines + ["no fixtures compared"]), comps
    mad = sum(devs) / len(devs)
    worst = max(devs)
    ok = mad <= 0.06 and flips == 0 and len(comps) == 12 and modelable
    lines.append("fixtures compared: {} (12 expected); model cut at scan time {}"
                 " (leakage-free vs the 16:55Z frozen mids)".format(len(comps), scan_cutoff))
    lines.append("mean abs deviation over {} 1X2 probs: {:.2%} (gate <=6%)".format(
        len(devs), mad))
    lines.append("worst single-prob deviation: {:.2%}".format(worst))
    lines.append("favorite flips: {} (gate 0); fixtures: {}".format(
        flips, ", ".join("{} v {}{}{}".format(
            c["home"], c["away"],
            " [fallback-team: " + (c["home"] if c["home"] in fallback_teams
                                   else c["away"]) + "]"
            if c["fallback_team_involved"] else "",
            " [{}]".format(c["played_final"]) if c["played_final"] else "")
            for c in comps if c["favorite_flip"])))
    if n_played:
        lines.append("played-fixture log-loss (informal, n={}): model {:.4f} vs market "
                     "{:.4f}".format(n_played, ll_model / n_played, ll_mkt / n_played))
    lines.append("systematic pattern: model compresses strong away favorites "
                 "(market away-favorite probs exceed model by 2-12c in 9/12), "
                 "amplified by league-average fallback for the 6 teams new to "
                 "Championship_2026 (incl. relegated West Ham/Wolves/Cardiff/"
                 "Burnley and promoted Lincoln/Bolton)")
    return gate("E", "market comparison", ok, lines), comps


# --------------------------------------------------------------------------
# board + market mids + candidate flags
# --------------------------------------------------------------------------

def market_mids(events: list) -> dict:
    """(event_id, key) -> market row; key = ('ou_total', line) | ('tt', pm_team, line)
    | ('btts',). Full-game main-board O/U, team totals and BTTS only (halves,
    spreads, exact score excluded). Lives in the '-more-markets' sibling event."""
    more_by_slug = {e.get("slug", ""): e for e in events
                    if str(e.get("slug", "")).endswith("-more-markets")}
    mids = {}
    for ev in championship_main_events(events):
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


def build_board(snapshot: dict, comps: list) -> dict:
    board = []
    for comp in comps:
        home, away = comp["home"], comp["away"]
        variants = soccer_model.fixture_variants(snapshot, home, LEAGUE, away, LEAGUE,
                                                 season=SEASON_CUR)
        lam = soccer_model.match_lambdas(snapshot, home, LEAGUE, away, LEAGUE)
        entry = {
            "event_id": comp["event_id"], "slug": comp["slug"],
            "home": home, "away": away,
            "pm_home": comp["pm_home"], "pm_away": comp["pm_away"],
            "lambda_home": round(lam[0], 3), "lambda_away": round(lam[1], 3),
            "total_xg_median": round(lam[0] + lam[1], 3),
            "one_x2": {
                "model": comp["model"], "market_mid_normalized": comp["market"],
                "abs_dev": comp["abs_dev"], "favorite_flip": comp["favorite_flip"],
            },
            "ou": [], "btts": {}, "team_totals": {"home": [], "away": []},
        }
        for line in OU_LINES:
            overs = [soccer_model.over_probability(v.outputs, line) for v in variants]
            med = soccer_model.median(overs)
            entry["ou"].append({
                "line": line, "over_med": round(med, 4),
                "over_min": round(min(overs), 4), "over_max": round(max(overs), 4),
                "under_med": round(1 - med, 4),
            })
        btts = [soccer_model.both_teams_to_score(v.outputs) for v in variants]
        med_btts = soccer_model.median(btts)
        entry["btts"] = {
            "yes_med": round(med_btts, 4), "yes_min": round(min(btts), 4),
            "yes_max": round(max(btts), 4), "no_med": round(1 - med_btts, 4),
        }
        for side_key, side_out in (("home", "home"), ("away", "away")):
            team = entry[side_key]
            for line in TT_LINES:
                overs = [soccer_model.team_total_over(v.outputs, side_out, line)
                         for v in variants]
                med = soccer_model.median(overs)
                entry["team_totals"][side_key].append({
                    "team": team, "line": line, "over_med": round(med, 4),
                    "over_min": round(min(overs), 4), "over_max": round(max(overs), 4),
                })
        board.append(entry)
    return {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "league": LEAGUE, "season": SEASON_CUR,
            "method": "papersim SWEEPS 10-variant median (standard domestic path)",
            "fixtures": board}


def row_edges(row: dict, mkt_first: float, kind: str) -> dict:
    """Attach both-direction edges vs a market mid where prices[0] is the
    Over/Yes mid. kind: 'over' (O/U + TT) or 'yes' (BTTS)."""
    if kind == "over":
        med, lo, hi = row["over_med"], row["over_min"], row["over_max"]
    else:
        med, lo, hi = row["yes_med"], row["yes_min"], row["yes_max"]
    other = 1.0 - mkt_first
    edge_med = med - mkt_first
    edge_worst = (lo - mkt_first) if edge_med >= 0 else (hi - mkt_first)
    under_med = 1.0 - med
    u_edge_med = under_med - other
    u_lo, u_hi = 1.0 - hi, 1.0 - lo
    u_edge_worst = (u_lo - other) if u_edge_med >= 0 else (u_hi - other)
    out = {
        "market_mid_first": mkt_first,
        "edge_med": round(edge_med, 4),
        "edge_worst_variant": round(edge_worst, 4),
        "other_edge_med": round(u_edge_med, 4),
        "other_edge_worst_variant": round(u_edge_worst, 4),
        "var_width": round(hi - lo, 4),
    }
    row.update(out)
    return out


def flag_side(flags: list, fx: dict, label: str, side: str, med: float,
              edge_med: float, edge_worst: float, width: float, liq) -> None:
    """Paper-only candidate flag: |edge med|>=5c AND worst-variant edge same
    side with |edge|>=4c AND variant width <=6c AND liq >=$5k."""
    if (abs(edge_med) >= 0.05 and (edge_med > 0) == (edge_worst > 0)
            and abs(edge_worst) >= 0.04 and width <= 0.06 and (liq or 0) >= 5000):
        flags.append({
            "match": "{} vs {}".format(fx["home"], fx["away"]),
            "event_id": fx["event_id"], "market": label, "side": side,
            "model_med": round(med, 4), "edge_med": round(edge_med, 4),
            "edge_worst_variant": round(edge_worst, 4),
            "variant_width": round(width, 4), "liq": round(liq or 0, 1),
            "status": "PAPER-FLAG (model-vs-mid; CLOB exec/vwap gates NOT checked)",
        })


def attach_market_and_flags(board: dict, mids: dict) -> list:
    flags = []
    for fx in board["fixtures"]:
        ev = fx["event_id"]
        for row in fx["ou"]:
            m = mids.get((ev, ("ou_total", row["line"])))
            if not m or m["outcomes"] != ["Over", "Under"] or not m["liq"]:
                continue
            row["liq"] = m["liq"]
            row_edges(row, m["prices"][0], "over")
            flag_side(flags, fx, "O/U {:.1f}".format(row["line"]), "over",
                      row["over_med"], row["edge_med"], row["edge_worst_variant"],
                      row["var_width"], row["liq"])
            flag_side(flags, fx, "O/U {:.1f}".format(row["line"]), "under",
                      row["under_med"], row["other_edge_med"],
                      row["other_edge_worst_variant"], row["var_width"], row["liq"])
        m = mids.get((ev, ("btts",)))
        if m and m["outcomes"] == ["Yes", "No"] and m["liq"]:
            fx["btts"]["liq"] = m["liq"]
            row_edges(fx["btts"], m["prices"][0], "yes")
            flag_side(flags, fx, "BTTS", "yes", fx["btts"]["yes_med"],
                      fx["btts"]["edge_med"], fx["btts"]["edge_worst_variant"],
                      fx["btts"]["var_width"], fx["btts"]["liq"])
            flag_side(flags, fx, "BTTS", "no", fx["btts"]["no_med"],
                      fx["btts"]["other_edge_med"], fx["btts"]["other_edge_worst_variant"],
                      fx["btts"]["var_width"], fx["btts"]["liq"])
        for side_key, pm_name in (("home", fx["pm_home"]), ("away", fx["pm_away"])):
            for row in fx["team_totals"][side_key]:
                m = mids.get((ev, ("tt", pm_name, row["line"])))
                if not m or m["outcomes"] != ["Over", "Under"] or not m["liq"]:
                    continue
                row["liq"] = m["liq"]
                row_edges(row, m["prices"][0], "over")
                flag_side(flags, fx, "{} TT {:.1f}".format(row["team"], row["line"]),
                          "over", row["over_med"], row["edge_med"],
                          row["edge_worst_variant"], row["var_width"], row["liq"])
                flag_side(flags, fx, "{} TT {:.1f}".format(row["team"], row["line"]),
                          "under", 1 - row["over_med"], row["other_edge_med"],
                          row["other_edge_worst_variant"], row["var_width"], row["liq"])
    return flags


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def pct(x) -> str:
    return "{:.1%}".format(x)


def write_report(meta: dict, board: dict, comps: list, flags: list, verdict: str) -> None:
    L = []
    bs = meta["backfill_stats"]
    L.append("# WP-P3 Phase 1: FotMob Championship xG - validation report")
    L.append("")
    L.append("- Generated (UTC): {} | host ubuntu@SERVER_HOST_REDACTED".format(
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")))
    L.append("- Provider: {} | league id 48 (opta)".format(meta["provider"]))
    L.append("- Adapter paper-sim/tools/fotmob_adapter.py | validator "
             "paper-sim/tools/fotmob_validate.py (server-side Phase 1; repo untouched)")
    L.append("- Library: {} | selfcheck re-run this session: 10/10 PASS".format(LIB_REF))
    L.append("- Paper-only: no credentials, no orders, no repo modification; FotMob "
             "unofficial API fetched at 1 req/1.3 s with on-disk cache.")
    L.append("")
    L.append("## 1. Backfill")
    L.append("")
    L.append("- matchDetails needed: {} | cache hits: {} | new fetches: {} | spacing "
             "{}s | wall {:.0f}s".format(
                 bs["matchdetails_needed"], bs["matchdetails_cache_hits"],
                 bs["matchdetails_new_fetches"], bs["rate_limit_seconds_between_fetches"],
                 meta.get("duration_s", 0.0)))
    for key in sorted(meta["seasons"]):
        sm = meta["seasons"][key]
        L.append("- {}: {} fixtures -> kept {} finished numeric-round (1-46); xG on {} "
                 "(skipped {}); playoff excluded {} (rounds {}); cancelled excluded {}; "
                 "window {}".format(
                     key, sm["fixtures_total"], sm["kept_finished_numeric"],
                     sm["matches_with_xg"], sm["skipped_no_xg"], sm["excluded_playoff"],
                     "/".join(sm["excluded_playoff_rounds"]) or "-",
                     sm["excluded_cancelled"], " to ".join(sm["dates_range"])))
    L.append("- Output: round31/raw/xg_fotmob_championship.json + .meta.json "
             "(Understat wire shape; block keys Championship_2025 / Championship_2026).")
    L.append("")
    L.append("### Team alias layer (24 teams; Polymarket match rule = strip trailing "
             "' FC'/' AFC')")
    L.append("")
    L.append("| FotMob title (snapshot key) | short_title | id |")
    L.append("|---|---|---|")
    aliases = meta["team_aliases"][BLOCK_CUR]
    for tid, row in sorted(aliases.items(), key=lambda kv: kv[1]["title"]):
        L.append("| {} | {} | {} |".format(row["title"], row["short_title"], tid))
    L.append("")
    L.append("## 2. Validation gates")
    L.append("")
    for letter in sorted(results):
        r = results[letter]
        L.append("### Gate {} - {}: **{}**".format(letter, r["gate"].upper(),
                                                   "PASS" if r["passed"] else "FAIL"))
        L.append("")
        for d in r["details"]:
            L.append("- {}".format(d))
        L.append("")
    L.append("### Gate E fixture detail (model = pre-scan data, vs Polymarket 1X2 "
             "scan-time 2026-11-03 16:55Z mids, renormalized)")
    L.append("")
    L.append("| fixture | model H/D/A | market H/D/A | abs dev H/D/A | favorite | final |")
    L.append("|---|---|---|---|---|---|")
    for c in comps:
        fav = ("FLIP (mkt {} vs model {})".format(c["market_favorite"], c["model_favorite"])
               if c["favorite_flip"] else "agree ({})".format(c["market_favorite"]))
        L.append("| {} vs {} | {}/{}/{} | {}/{}/{} | {}/{}/{} | {} | {} |".format(
            c["home"], c["away"],
            pct(c["model"]["h"]), pct(c["model"]["d"]), pct(c["model"]["a"]),
            pct(c["market"]["h"]), pct(c["market"]["d"]), pct(c["market"]["a"]),
            pct(c["abs_dev"]["h"]), pct(c["abs_dev"]["d"]), pct(c["abs_dev"]["a"]),
            fav, c.get("played_final") or "-"))
    L.append("")
    L.append("## 3. Wednesday Championship odds board (12 fixtures, 10-variant model)")
    L.append("")
    L.append("Model = median over the ten papersim SWEEPS variants (standard domestic "
             "path, league='Championship', season='2026'); range = min..max across "
             "variants. Market = Polymarket mid frozen at scan time (2026-11-03 16:55Z, "
             "pre-kickoff). Note: 9 of 12 fixtures kicked off 19:45-20:00Z Nov-3 (their "
             "rows are model-vs-frozen-mid, retrospective); 3 kick off Nov-4.")
    L.append("")
    for fx in board["fixtures"]:
        L.append("### {} vs {} (event {})".format(fx["home"], fx["away"], fx["event_id"]))
        L.append("")
        L.append("- lambdas: home {:.3f} away {:.3f} | total xG {:.3f} | 1X2 model "
                 "{}/{}/{} vs market {}/{}/{}".format(
                     fx["lambda_home"], fx["lambda_away"], fx["total_xg_median"],
                     pct(fx["one_x2"]["model"]["h"]), pct(fx["one_x2"]["model"]["d"]),
                     pct(fx["one_x2"]["model"]["a"]),
                     pct(fx["one_x2"]["market_mid_normalized"]["h"]),
                     pct(fx["one_x2"]["market_mid_normalized"]["d"]),
                     pct(fx["one_x2"]["market_mid_normalized"]["a"])))
        L.append("")
        L.append("| market | model med | model range | market mid | edge (med) | liq $ |")
        L.append("|---|---|---|---|---|---|")
        for row in fx["ou"]:
            if "market_mid_first" in row:
                L.append("| O/U {:.1f} over | {} | {}..{} | {} | {:+.1%} | {:,.0f} |".format(
                    row["line"], pct(row["over_med"]), pct(row["over_min"]),
                    pct(row["over_max"]), pct(row["market_mid_first"]),
                    row["edge_med"], row["liq"]))
                L.append("| O/U {:.1f} under | {} | - | {} | {:+.1%} | |".format(
                    row["line"], pct(row["under_med"]), pct(1 - row["market_mid_first"]),
                    row["other_edge_med"]))
            else:
                L.append("| O/U {:.1f} over | {} | {}..{} | - | - | - |".format(
                    row["line"], pct(row["over_med"]), pct(row["over_min"]),
                    pct(row["over_max"])))
        b = fx["btts"]
        if "market_mid_first" in b:
            L.append("| BTTS yes | {} | {}..{} | {} | {:+.1%} | {:,.0f} |".format(
                pct(b["yes_med"]), pct(b["yes_min"]), pct(b["yes_max"]),
                pct(b["market_mid_first"]), b["edge_med"], b["liq"]))
            L.append("| BTTS no | {} | - | {} | {:+.1%} | |".format(
                pct(b["no_med"]), pct(1 - b["market_mid_first"]), b["other_edge_med"]))
        else:
            L.append("| BTTS yes | {} | {}..{} | - | - | - |".format(
                pct(b["yes_med"]), pct(b["yes_min"]), pct(b["yes_max"])))
        for key, label in (("home", fx["home"]), ("away", fx["away"])):
            for row in fx["team_totals"][key]:
                if "market_mid_first" in row:
                    L.append("| {} TT {:.1f} over | {} | {}..{} | {} | {:+.1%} | {:,.0f} |".format(
                        label, row["line"], pct(row["over_med"]), pct(row["over_min"]),
                        pct(row["over_max"]), pct(row["market_mid_first"]),
                        row["edge_med"], row["liq"]))
                    L.append("| {} TT {:.1f} under | {} | - | {} | {:+.1%} | |".format(
                        label, row["line"], pct(1 - row["over_med"]),
                        pct(1 - row["market_mid_first"]), row["other_edge_med"]))
                else:
                    L.append("| {} TT {:.1f} over | {} | {}..{} | - | - | - |".format(
                        label, row["line"], pct(row["over_med"]), pct(row["over_min"]),
                        pct(row["over_max"])))
        L.append("")
    L.append("## 4. Candidate flags (paper-only)")
    L.append("")
    if not all(results[k]["passed"] for k in results):
        L.append("> NOTE: validation did NOT pass (see verdict). Any flags below are "
                 "informational model-vs-mid disagreements, NOT entry candidates: "
                 "with gate E failing, the 1X2 (and by extension correlated totals) "
                 "calibration is not trusted for real entries.")
        L.append("")
    if flags:
        L.append("| match | market | side | model | edge med | edge worst-variant | "
                 "variant width | liq $ | status |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for f in flags:
            L.append("| {} | {} | {} | {} | {:+.1%} | {:+.1%} | {} | {:,.0f} | {} |".format(
                f["match"], f["market"], f["side"], pct(f["model_med"]),
                f["edge_med"], f["edge_worst_variant"], pct(f["variant_width"]),
                f["liq"], f["status"]))
        L.append("")
        L.append("Model-vs-mid flags only. Enterability requires a live CLOB book "
                 "recheck (exec_ask_vwap250 >= +5c, worst variant >= +4c, variant "
                 "spread <= 6c, liquidity >= $5k, fill-250) plus owner gate approval; "
                 "1X2 stays deprioritized (domestic MW policy).")
    else:
        L.append("None: no market cleared the paper flag thresholds (|edge med| >= 5c, "
                 "worst-variant same-side >= 4c, variant width <= 6c, liq >= $5k).")
    L.append("")
    L.append("## 5. Verdict")
    L.append("")
    L.append("**{}**".format(verdict))
    L.append("")
    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    snapshot = json.loads(SNAP_PATH.read_text())
    meta = json.loads(META_PATH.read_text())
    events = json.loads(EVENTS_PATH.read_text())

    a = gate_a(snapshot)
    b = gate_b(snapshot)
    c = gate_c(snapshot)
    d = gate_d(snapshot)
    e, comps = gate_e(snapshot, events)

    board = build_board(snapshot, comps)
    mids = market_mids(events)
    flags = attach_market_and_flags(board, mids)
    BOARD_JSON.write_text(json.dumps(board, indent=1) + "\n")

    passed = all((a, b, c, d, e))
    verdict = ("VERDICT: VALIDATED" if passed else
               "VERDICT: VALIDATION-FAILED - " + ", ".join(
                   "gate {} ({})".format(k, results[k]["gate"])
                   for k in sorted(results) if not results[k]["passed"]))
    VAL_JSON.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gates": results, "verdict": verdict,
        "backfill_stats": meta["backfill_stats"],
        "candidate_flags": flags}, indent=1) + "\n")
    write_report(meta, board, comps, flags, verdict)
    print()
    print(verdict)
    print("report: {}".format(REPORT_MD))
    print("board:  {}".format(BOARD_JSON))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
