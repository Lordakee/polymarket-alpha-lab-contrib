#!/usr/bin/env python3
"""WP-P2c: xG shrinkage (LASTW/PRIOR) shadow experiment on settled paper bets.

Read-only retrospective replay over the settled paper-sim ledger. For every
settled sports_soccer bet it re-derives the fixture xG lambdas from the
archived Understat snapshot of the round window that placed the bet
(truncated to strictly pre-kickoff information), under four shrinkage
configurations of ``papersim.xg.ratings_for``:

    base : last_weight=0.5, prior_games=8   (current production center)
    A    : last_weight=0.5, prior_games=16  (stronger league-average prior)
    B    : last_weight=0.25, prior_games=8  (last-season weight sensitivity)
    C    : last_weight=0.75, prior_games=8  (last-season weight sensitivity)

It then replays the frozen entry-gate arithmetic per config (single-prior
shadow gate: suspension policy + entry window + exec-edge bar with the
50-50 cancellation haircut and the r15 under-risk +8c screen), counts
decision flips versus the base config, sums counterfactual P&L (a bet the
config drops contributes 0), computes calibration on the settled O/U-over
population, and evaluates the pre-registered promotion criteria.

PRE-REGISTERED PROMOTION CRITERIA (fixed before running, from the WP-P2c
plan / codex review recommendation 5):
  C1 calibration improvement >= 3c: |mean(prob) - hit_rate| on the settled
     ou_over population must improve by >= 0.03 versus the base config.
  C2 win-rate non-degradation: hit rate of the bets the config still takes
     (ou_over population) must be >= the base config's hit rate.
  C3 counterfactual P&L >= -$250: the config's total replayed P&L across
     all settled soccer bets must be at least -$250.
  C4 var_spread stability: the median per-bet spread across the four
     config quotes must stay within the 6c production variant-spread bar.

Known limitations (documented, not silently worked around):
  - Bet #10 (Man City season outright) used a bespoke remaining-fixture
    Monte Carlo; it is not replayable through pair_lambdas and is excluded.
  - The six UCL/UEL cross-league bets were originally priced by bespoke
    pre-WP-P2a scripts (raw cross-league multiplier combination - since
    banned). Their originals cannot be reproduced through the sanctioned
    path; this replay prices them through the WP-P2a league-strength
    bridge using the archived kappa table
    (round31/raw/league_strength_kappa.json), the only sanctioned
    cross-league path. Reproduction deltas for these rows are expected
    and reported.
  - Liquidity / $250-fill / news-concordance gates are assumed satisfied
    for already-placed bets; the replay re-evaluates only the
    model-driven gates.
  - Early-window bets were placed under looser pre-freeze gates; flips
    are measured versus the BASE CONFIG REPLAY under the same frozen
    gates, not versus the historical placement decision.

Usage:
    PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src \
        python3 ~/paper-sim/tools/shadow_experiment.py

Outputs (deterministic, no network access):
    ~/paper-sim/round31/shadow_experiment.json
    ~/paper-sim/round31/shadow_report.md
"""

from __future__ import annotations

import copy
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from polymarket_alpha_lab.papersim.gates import (
    ENTRY_WINDOW,
    GATES,
    HAIRCUT_BAND,
    HAIRCUT_FACTOR,
    UNDER_RISK_EXEC_EDGE_MIN,
    suspension_policy,
    under_risk_check,
)
from polymarket_alpha_lab.papersim.league_strength import load_kappa_report
from polymarket_alpha_lab.papersim.soccer_model import (
    fixture_variants,
    over_probability,
    both_teams_to_score,
    cover_probability,
    team_total_over,
    variant_outputs,
)
from polymarket_alpha_lab.papersim.xg import (
    load_xg_snapshot,
    pair_lambdas,
    recent_form,
)

PAPER_SIM = Path.home() / "paper-sim"
LAB_SRC = "/home/ubuntu/polymarket-alpha-lab/src"
KAPPA_PATH = PAPER_SIM / "round31/raw/league_strength_kappa.json"
LEDGER_PATH = PAPER_SIM / "review/settled_ledger.json"
OUT_DIR = PAPER_SIM / "round31"

# ---------------------------------------------------------------------------
# Frozen experiment parameters
# ---------------------------------------------------------------------------

CONFIGS = [
    ("base", 0.50, 8.0),
    ("A_p16", 0.50, 16.0),
    ("B_w25", 0.25, 8.0),
    ("C_w75", 0.75, 8.0),
]

EXEC_EDGE_MIN = GATES["exec_edge_min"]          # +5c
VAR_SPREAD_MAX = GATES["variant_spread_max"]    # 6c

# Archived Understat snapshot registry: label -> path. Order irrelevant; the
# picker ranks by per-league data freshness. r23 is a virtual merge of the
# three round-23 refresh files (fetched together).
SNAPSHOT_FILES = {
    "r5c": PAPER_SIM / "round5/raw/xg_understat_5c.json",
    "r10": PAPER_SIM / "round10/raw/xg_understat_10.json",
    "r12": PAPER_SIM / "round12/raw/xg_understat_12.json",
    "r15": PAPER_SIM / "round15/raw/xg_understat_15.json",
    "r18": PAPER_SIM / "round18/raw/xg_understat_18.json",
    "r20": PAPER_SIM / "round20/raw/xg_understat_20.json",
    "r21": PAPER_SIM / "round21/raw/xg_understat_21.json",
    "r22": PAPER_SIM / "round22/raw/xg_understat_22.json",
    "r23": None,  # merged below
    "r24": PAPER_SIM / "round24/raw/xg_r24.json",
    "r25": PAPER_SIM / "round25/raw/xg_understat_25.json",
}


@dataclass(frozen=True)
class BetSpec:
    bet_id: int
    home: str
    home_league: str
    away: str
    away_league: str
    kickoff_date: str          # YYYY-MM-DD; snapshot truncated at 00:00 UTC
    market: str                # total | btts | match_winner | spread | team_total
    side: str                  # over | under | yes | home | away
    line: float | None         # total/team-total line or spread line
    tt_side: str | None        # 'home'/'away' for team totals
    note: str = ""


# Fixture/market mapping for every settled sports_soccer ledger row except
# #10 (bespoke season Monte Carlo, excluded). Team names are the exact
# Understat titles in the archived snapshots.
BETS = [
    BetSpec(9,  "Crystal Palace", "EPL", "Nottingham Forest", "EPL", "2026-10-11", "total", "over", 2.5, None),
    BetSpec(12, "Torino", "Serie_A", "Udinese", "Serie_A", "2026-10-12", "total", "over", 2.5, None),
    BetSpec(13, "Levante", "La_liga", "Sevilla", "La_liga", "2026-10-12", "total", "over", 2.5, None),
    BetSpec(15, "Bournemouth", "EPL", "Sunderland", "EPL", "2026-10-18", "total", "over", 2.5, None),
    BetSpec(16, "Brighton", "EPL", "Crystal Palace", "EPL", "2026-10-18", "btts", "yes", None, None),
    BetSpec(17, "Bournemouth", "EPL", "Sunderland", "EPL", "2026-10-18", "spread", "home", -1.5, None,
            "flagged-only kind under current policy"),
    BetSpec(18, "Paris FC", "Ligue_1", "Rennes", "Ligue_1", "2026-10-18", "total", "over", 2.5, None),
    BetSpec(19, "Tottenham", "EPL", "Coventry", "EPL", "2026-10-19", "total", "under", 2.5, None),
    BetSpec(20, "Parma Calcio 1913", "Serie_A", "Torino", "Serie_A", "2026-10-19", "total", "over", 2.5, None),
    BetSpec(21, "Monza", "Serie_A", "Cagliari", "Serie_A", "2026-10-19", "match_winner", "home", None, None),
    BetSpec(22, "Como", "Serie_A", "Manchester United", "EPL", "2026-10-21", "match_winner", "home", None, None,
            "cross-league 1X2: BANNED kind under current policy; original bespoke pre-bridge"),
    BetSpec(24, "Levante", "La_liga", "Athletic Club", "La_liga", "2026-10-21", "total", "over", 2.5, None),
    BetSpec(25, "Liverpool", "EPL", "Villarreal", "La_liga", "2026-10-20", "match_winner", "away", None, None,
            "cross-league 1X2: BANNED kind under current policy; original bespoke pre-bridge"),
    BetSpec(26, "Real Madrid", "La_liga", "RasenBallsport Leipzig", "Bundesliga", "2026-10-21", "btts", "yes", None, None,
            "cross-league; original bespoke pre-bridge"),
    BetSpec(27, "Bayern Munich", "Bundesliga", "Arsenal", "EPL", "2026-10-21", "total", "over", 2.5, None,
            "cross-league; original bespoke pre-bridge"),
    BetSpec(28, "Hoffenheim", "Bundesliga", "Lyon", "Ligue_1", "2026-10-22", "match_winner", "away", None, None,
            "cross-league 1X2: BANNED kind under current policy; original bespoke pre-bridge"),
    BetSpec(29, "Bournemouth", "EPL", "AC Milan", "Serie_A", "2026-10-22", "match_winner", "away", None, None,
            "cross-league 1X2: BANNED kind under current policy; original bespoke pre-bridge"),
    BetSpec(30, "Sunderland", "EPL", "Leeds", "EPL", "2026-10-25", "total", "over", 2.5, None),
    BetSpec(31, "Valencia", "La_liga", "Villarreal", "La_liga", "2026-10-24", "total", "over", 2.5, None),
    BetSpec(32, "Ipswich", "EPL", "Nottingham Forest", "EPL", "2026-10-23", "total", "over", 2.5, None),
    BetSpec(34, "Rayo Vallecano", "La_liga", "Elche", "La_liga", "2026-10-24", "total", "over", 2.5, None),
    BetSpec(35, "Alaves", "La_liga", "Malaga", "La_liga", "2026-10-23", "total", "over", 2.5, None),
    BetSpec(36, "Hull", "EPL", "Brentford", "EPL", "2026-10-25", "btts", "yes", None, None),
    BetSpec(37, "Arsenal", "EPL", "Everton", "EPL", "2026-10-24", "total", "over", 3.5, None),
    BetSpec(41, "Lens", "Ligue_1", "Paris FC", "Ligue_1", "2026-10-24", "total", "over", 1.5, None),
    BetSpec(43, "Udinese", "Serie_A", "AC Milan", "Serie_A", "2026-10-25", "team_total", "over", 1.5, "home"),
    BetSpec(44, "Real Sociedad", "La_liga", "Levante", "La_liga", "2026-10-25", "team_total", "over", 0.5, "away"),
    BetSpec(45, "Manchester United", "EPL", "Bournemouth", "EPL", "2026-10-25", "total", "over", 2.5, None),
    BetSpec(46, "Sevilla", "La_liga", "Osasuna", "La_liga", "2026-10-26", "team_total", "over", 1.5, "away"),
]

EXCLUDED = {
    10: "season-outright bespoke Monte Carlo (329+310 remaining fixtures); not replayable via pair_lambdas",
}


# ---------------------------------------------------------------------------
# Snapshot handling
# ---------------------------------------------------------------------------

def merge_r23() -> dict:
    merged: dict = {}
    for name in ("xg_epl_23.json", "xg_ll_bund_23.json", "xg_understat_ligue_23.json"):
        with open(PAPER_SIM / f"round23/raw/{name}", "r", encoding="utf-8") as fh:
            merged.update(json.load(fh))
    return merged


def load_registry() -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for label, path in SNAPSHOT_FILES.items():
        payload = merge_r23() if path is None else json.load(open(path, "r", encoding="utf-8"))
        registry[label] = payload
    return registry


def league_latest_date(snapshot: dict, league: str) -> str:
    """Latest current-season history date for ``league`` ('' when absent)."""
    block = snapshot.get(f"{league}_2026")
    if not isinstance(block, dict):
        return ""
    latest = ""
    for row in block.get("teams", {}).values():
        for entry in row.get("history", []):
            date = str(entry.get("date", ""))
            if date > latest:
                latest = date
    return latest[:10]


def truncate(snapshot: dict, cutoff_date: str) -> dict:
    """Keep only rows dated strictly before ``cutoff_date`` 00:00 UTC.

    Mirrors the placing agent's pre-kickoff fetch: the bet match itself and
    every same-day match are removed, prior seasons are untouched (their
    dates are a year earlier).
    """
    cutoff = f"{cutoff_date} 00:00:00"
    out: dict = {}
    for key, block in snapshot.items():
        if not isinstance(block, dict) or "teams" not in block:
            out[key] = block
            continue
        nb = copy.deepcopy(block)
        for row in nb["teams"].values():
            row["history"] = [
                h for h in row.get("history", []) if str(h.get("date", "")) < cutoff
            ]
        if "dates" in nb:
            nb["dates"] = [
                d
                for d in nb["dates"]
                if str(d.get("datetime", d.get("date", ""))) < cutoff
            ]
        out[key] = nb
    return out


def pick_snapshot(registry: dict, leagues: list[str], kickoff_date: str) -> tuple[str, str, dict]:
    """Snapshot choice for one fixture.

    Numeric source: the FRESHEST archived snapshot containing every needed
    league, history and dates truncated to strictly pre-kickoff. Understat
    per-match rows are frozen, so a later fetch truncated at kickoff
    reproduces the placement-time information set exactly (validated:
    bet #9 via r5c-truncated and r25-truncated both give 0.6068 / range
    0.5953-0.6233, matching the recorded 0.609/[0.595,0.623]; bet #45
    via r15/r25-truncated reproduces 0.6476/[0.6340,0.6628] exactly).
    The freshest archive is preferred because it additionally carries any
    matchday a placement-time fetch pulled hours before kickoff.

    Provenance label: the placement-era archive — the freshest snapshot
    whose league data strictly predates the kickoff DATE — is reported
    alongside for traceability to the round window that placed the bet.
    """
    best_label, best_key = None, None
    era_label, era_key = None, None
    for label in sorted(registry):
        snapshot = registry[label]
        dates = [league_latest_date(snapshot, lg) for lg in leagues]
        if any(d == "" for d in dates):
            continue
        key = (min(dates), label)
        if best_key is None or key > best_key:
            best_key, best_label = key, label
        latest = max(dates)
        if latest < kickoff_date:
            ekey = (latest, label)
            if era_key is None or ekey > era_key:
                era_key, era_label = ekey, label
    if best_label is None:
        raise RuntimeError(f"no archived snapshot covers leagues {leagues}")
    return best_label, (era_label or best_label), truncate(registry[best_label], kickoff_date)


# ---------------------------------------------------------------------------
# Market quotes
# ---------------------------------------------------------------------------

def market_quote(outputs, spec: BetSpec) -> float:
    if spec.market == "total":
        p_over = over_probability(outputs, float(spec.line))
        return p_over if spec.side == "over" else 1.0 - p_over
    if spec.market == "btts":
        return both_teams_to_score(outputs)
    if spec.market == "match_winner":
        return outputs.home_win if spec.side == "home" else outputs.away_win
    if spec.market == "spread":
        return cover_probability(outputs, spec.side, float(spec.line))
    if spec.market == "team_total":
        return team_total_over(outputs, spec.tt_side, float(spec.line))
    raise ValueError(f"unknown market {spec.market}")


def quote_kind_side(spec: BetSpec) -> tuple[str, str]:
    """Map to the gates-module (kind, side) vocabulary."""
    if spec.market in ("total", "team_total"):
        return "total", "over" if spec.side == "over" else "under"
    if spec.market == "btts":
        return "btts", spec.side
    return spec.market, spec.side


# ---------------------------------------------------------------------------
# Gate replay (single-prior shadow)
# ---------------------------------------------------------------------------

def gate_replay(spec: BetSpec, price: float, fair: float, lh: float, la: float,
                o25_hits: int) -> dict:
    """Frozen-gate arithmetic for one config's fair on one settled bet.

    Checks replayed: suspension policy for the market kind, entry window,
    exec-edge bar (+5c) after the 50-50 cancellation haircut, with the r15
    under-risk screen raising the bar to +8c for flagged Over/BTTS-Yes.
    Liquidity / $250 fill / news gates are assumed satisfied (the bet was
    already placed and filled at ``price``).
    """
    cross = spec.home_league != spec.away_league
    policy = suspension_policy("match_winner" if spec.market == "match_winner"
                               else "spread" if spec.market == "spread"
                               else "total", cross_league=cross)
    failed: list[str] = []
    if not policy.eligible:
        failed.append(f"kind_policy:{policy.policy}")
    if not (ENTRY_WINDOW[0] <= price <= ENTRY_WINDOW[1]):
        failed.append("entry_window")
    edge = fair - price
    haircut = HAIRCUT_FACTOR if HAIRCUT_BAND[0] <= fair <= HAIRCUT_BAND[1] else 1.0
    edge_eff = edge * haircut
    kind, side = quote_kind_side(spec)
    ur_flag, ur_reason = under_risk_check(
        kind=kind, side=side, o25_hits=o25_hits,
        lambda_total=lh + la, lambda_home=lh, lambda_away=la,
        line=float(spec.line or 2.5),
    )
    bar = UNDER_RISK_EXEC_EDGE_MIN if ur_flag else EXEC_EDGE_MIN
    if edge_eff < bar:
        failed.append(f"exec_edge {edge_eff:+.4f} < {bar:+.2f}"
                      + (" (under_risk)" if ur_flag else ""))
    return {
        "passed": not failed,
        "failed": failed,
        "edge_raw": round(edge, 4),
        "haircut": haircut,
        "edge_eff": round(edge_eff, 4),
        "bar": bar,
        "under_risk": ur_flag,
        "under_risk_reason": ur_reason,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    kappa = load_kappa_report(str(KAPPA_PATH)).kappa
    registry = load_registry()
    ledger = {b["id"]: b for b in json.load(open(LEDGER_PATH, "r", encoding="utf-8"))}

    results: list[dict] = []
    for spec in BETS:
        row = ledger[spec.bet_id]
        leagues = sorted({spec.home_league, spec.away_league})
        snap_label, era_label, snap = pick_snapshot(registry, leagues, spec.kickoff_date)
        cross = spec.home_league != spec.away_league
        bridge = kappa if cross else None

        # Production-lineage reproduction: the frozen 10-variant sweep on the
        # same truncated snapshot (bridged path for cross-league rows).
        rep = {"snapshot": snap_label, "placement_era_snapshot": era_label,
               "cross_league": cross}
        variants = fixture_variants(snap, spec.home, spec.home_league,
                                    spec.away, spec.away_league,
                                    season="2026", bridge=bridge)
        if variants is None:
            rep["error"] = "fixture refused by pair_lambdas on truncated snapshot"
            configs_out = {name: None for name, _, _ in CONFIGS}
        else:
            qs = sorted(market_quote(v.outputs, spec) for v in variants)
            med = (qs[4] + qs[5]) / 2 if len(qs) == 10 else statistics.median(qs)
            rep["sweep_median"] = round(med, 4)
            rep["sweep_range"] = [round(qs[0], 4), round(qs[-1], 4)]
            rep["recorded"] = [row.get("fair_low"), row.get("fair_high"),
                               row.get("model_prediction")]
            rep["median_delta_c"] = round((med - float(row["model_prediction"])) * 100, 2)

        # Combined last-5 O2.5 hits for the under-risk screen.
        fh = recent_form(snap, spec.home, window=5)
        fa = recent_form(snap, spec.away, window=5)
        o25 = (fh.over_2_5_hits if fh else 0) + (fa.over_2_5_hits if fa else 0)

        per_config = {}
        for name, w, p in CONFIGS:
            lambdas = pair_lambdas(
                snap, spec.home, spec.home_league, spec.away, spec.away_league,
                last_weight=w, prior_games=p, mode="blend", shrink=1.0,
                season="2026", bridge=bridge,
            )
            if lambdas is None:
                per_config[name] = None
                continue
            lh, la = lambdas
            outputs = variant_outputs(lh, la, rho=0.0)
            fair = market_quote(outputs, spec)
            per_config[name] = {
                "w": w, "p": p,
                "lambda_home": round(lh, 4), "lambda_away": round(la, 4),
                "fair": round(fair, 4),
                "gate": gate_replay(spec, float(row["price"]), fair, lh, la, o25),
            }

        base_pass = per_config["base"]["gate"]["passed"] if per_config["base"] else False
        for name, _, _ in CONFIGS:
            cfg = per_config[name]
            if cfg is None:
                continue
            cfg["flip_vs_base"] = (
                base_pass is not None and cfg["gate"]["passed"] != base_pass
            )

        quotes4 = [per_config[n]["fair"] for n, _, _ in CONFIGS
                   if per_config[n] is not None]
        spread4 = round(max(quotes4) - min(quotes4), 4) if quotes4 else None

        results.append({
            "bet_id": spec.bet_id,
            "question": row["question"],
            "market_type": row["market_type"],
            "market": spec.market, "side": spec.side, "line": spec.line,
            "tt_side": spec.tt_side,
            "fixture": f"{spec.home} vs {spec.away}",
            "leagues": leagues,
            "kickoff_date": spec.kickoff_date,
            "snapshot_used": snap_label,
            "price": row["price"], "stake": row["stake"],
            "outcome": row["outcome"], "pnl": row["pnl"],
            "won": row["outcome"] == "YES",
            "o25_hits_combined": o25,
            "note": spec.note,
            "reproduction": rep,
            "configs": per_config,
            "spread4": spread4,
        })

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------
    def cfg_pnl(name: str) -> float:
        return sum(r["pnl"] for r in results
                   if r["configs"][name] and r["configs"][name]["gate"]["passed"])

    def flips(name: str) -> list[int]:
        return [r["bet_id"] for r in results
                if r["configs"][name] and r["configs"][name].get("flip_vs_base")]

    ou_pop = [r for r in results if r["market_type"] == "ou_over"]
    over_family = [r for r in results if r["market_type"] in ("ou_over", "team_total")]

    def calibration(pop: list[dict]) -> dict:
        out: dict[str, dict] = {}
        n = len(pop)
        hits = sum(1 for r in pop if r["won"])
        hit_rate = hits / n if n else None
        out["n"] = n
        out["hits"] = hits
        out["hit_rate"] = round(hit_rate, 4) if hit_rate is not None else None
        out["production_ledger"] = {
            "mean_prob": round(statistics.fmean(
                [float(ledger[r["bet_id"]]["model_prediction"]) for r in pop]), 4),
        }
        out["production_ledger"]["calib_err"] = round(
            abs(out["production_ledger"]["mean_prob"] - hit_rate), 4) if hit_rate is not None else None
        for name, _, _ in CONFIGS:
            probs = [r["configs"][name]["fair"] for r in pop
                     if r["configs"][name] is not None]
            mean_prob = round(statistics.fmean(probs), 4)
            out[name] = {
                "mean_prob": mean_prob,
                "calib_err": round(abs(mean_prob - hit_rate), 4) if hit_rate is not None else None,
            }
        return out

    def winrate(name: str, pop: list[dict]) -> dict:
        taken = [r for r in pop if r["configs"][name]
                 and r["configs"][name]["gate"]["passed"]]
        hits = sum(1 for r in taken if r["won"])
        return {"taken": len(taken), "hits": hits,
                "win_rate": round(hits / len(taken), 4) if taken else None}

    cal_ou = calibration(ou_pop)
    cal_family = calibration(over_family)
    spreads4 = [r["spread4"] for r in results if r["spread4"] is not None]

    # Promotion criteria evaluation
    base_cal = cal_ou["base"]["calib_err"]
    criteria: dict[str, dict] = {}
    for name, _, _ in CONFIGS:
        if name == "base":
            continue
        c1 = round(base_cal - cal_ou[name]["calib_err"], 4)
        wr_cfg, wr_base = winrate(name, ou_pop), winrate("base", ou_pop)
        pnl_cfg = round(cfg_pnl(name), 2)
        c2 = (wr_cfg["win_rate"] is not None and wr_base["win_rate"] is not None
              and wr_cfg["win_rate"] >= wr_base["win_rate"])
        c3 = pnl_cfg >= -250.0
        c4 = (statistics.median(spreads4) <= VAR_SPREAD_MAX) if spreads4 else False
        criteria[name] = {
            "C1_calibration_improvement_c": round(c1 * 100, 2),
            "C1_pass": c1 >= 0.03,
            "C2_winrate": {"config": wr_cfg, "base": wr_base, "pass": bool(c2)},
            "C3_counterfactual_pnl": {"total": pnl_cfg,
                                      "delta_vs_base": round(pnl_cfg - cfg_pnl("base"), 2),
                                      "pass": bool(c3)},
            "C4_var_spread": {"median_spread4_c": round(statistics.median(spreads4) * 100, 2)
                              if spreads4 else None, "pass": bool(c4)},
            "eligible": bool(c1 >= 0.03 and c2 and c3 and c4),
        }

    eligible = [n for n, c in criteria.items() if c["eligible"]]
    best = None
    if eligible:
        best = min(eligible, key=lambda n: (cal_ou[n]["calib_err"], -cfg_pnl(n)))

    payload = {
        "experiment": "WP-P2c xG shrinkage (LASTW/PRIOR) shadow experiment",
        "generated_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "configs": [{"name": n, "last_weight": w, "prior_games": p} for n, w, p in CONFIGS],
        "promotion_criteria_preregistered": {
            "C1": "calibration improvement >= 3c vs base on settled ou_over population",
            "C2": "win-rate non-degradation on bets still taken (ou_over)",
            "C3": "counterfactual total P&L >= -$250 (dropped bets contribute 0)",
            "C4": f"median per-bet 4-config quote spread <= {VAR_SPREAD_MAX*100:.0f}c",
        },
        "gate_replay_definition": (
            "suspension policy + entry window [.10,.92] + exec edge (fair - fill price) "
            f">= +{EXEC_EDGE_MIN*100:.0f}c after 50-50 haircut, raised to "
            f"+{UNDER_RISK_EXEC_EDGE_MIN*100:.0f}c when the r15 under-risk screen flags; "
            "liq/fill/news assumed satisfied for already-placed bets"
        ),
        "snapshot_policy": (
            "freshest archived snapshot containing the fixture leagues, history and "
            "dates truncated to strictly before kickoff date 00:00 UTC"
        ),
        "excluded_bets": EXCLUDED,
        "bet_results": results,
        "aggregates": {
            "flip_counts": {n: len(flips(n)) for n, _, _ in CONFIGS},
            "flips_detail": {n: flips(n) for n, _, _ in CONFIGS},
            "counterfactual_pnl": {n: round(cfg_pnl(n), 2) for n, _, _ in CONFIGS},
            "realized_pnl_all_soccer": round(sum(r["pnl"] for r in results), 2),
            "base_replay_pnl": round(cfg_pnl("base"), 2),
            "base_replay_agreement_with_placement": {
                "bets": len(results),
                "base_pass": sum(1 for r in results if r["configs"]["base"]["gate"]["passed"]),
                "placed_all": len(results),
            },
            "calibration_ou_over": cal_ou,
            "calibration_over_family": cal_family,
            "spread4": {
                "median": round(statistics.median(spreads4), 4) if spreads4 else None,
                "max": round(max(spreads4), 4) if spreads4 else None,
                "over_6c_bets": [r["bet_id"] for r in results
                                 if r["spread4"] is not None and r["spread4"] > VAR_SPREAD_MAX],
            },
        },
        "criteria_evaluation": criteria,
        "best_config": best,
        "verdict": best if best else "BASELINE",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "shadow_experiment.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    write_report(payload)
    print(f"bet rows replayed: {len(results)}")
    print(f"flips: {payload['aggregates']['flip_counts']}")
    print(f"cf pnl: {payload['aggregates']['counterfactual_pnl']}")
    print(f"calib(ou_over): " + ", ".join(
        f"{n}={cal_ou[n]['calib_err']}" for n, _, _ in CONFIGS))
    print(f"verdict: {payload['verdict']}")
    return 0


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(payload: dict) -> None:
    agg = payload["aggregates"]
    cal = agg["calibration_ou_over"]
    calf = agg["calibration_over_family"]
    crit = payload["criteria_evaluation"]
    lines: list[str] = []
    add = lines.append

    add("# WP-P2c xG shrinkage (LASTW/PRIOR) shadow experiment — round 31")
    add("")
    add(f"Generated (UTC): {payload['generated_at_utc']}")
    add("")
    add("Paper-only / report-only retrospective on the settled paper-sim ledger.")
    add("No network access, no live markets, no configuration changes: the")
    add("production library (`papersim`) is called with alternative shrinkage")
    add("parameters read-only, over archived Understat snapshots.")
    add("")
    add("## Pre-registered promotion criteria")
    add("")
    add("Fixed before the run (WP-P2c plan; codex review recommendation 5):")
    add("")
    add("| # | Criterion | Threshold |")
    add("|---|-----------|-----------|")
    add("| C1 | Calibration improvement vs base on settled `ou_over` population | ≥ 3c |")
    add("| C2 | Win-rate non-degradation on bets still taken (`ou_over`) | ≥ base replay |")
    add("| C3 | Counterfactual total P&L (dropped bets contribute $0) | ≥ −$250 |")
    add("| C4 | var_spread stability: median per-bet 4-config quote spread | ≤ 6c |")
    add("")
    add("A config is promotable only if all four hold. Config `base` (w=0.5, p=8)")
    add("is the incumbent by construction.")
    add("")
    add("## Method")
    add("")
    add("- Configs: " + "; ".join(
        f"`{c['name']}` w={c['last_weight']:g} p={c['prior_games']:g}"
        for c in payload["configs"]))
    add("- Population: every settled `sports_soccer` ledger row (30 rows) except")
    add("  #10 (bespoke season Monte Carlo, not replayable via `pair_lambdas`).")
    add("- Snapshot: " + payload["snapshot_policy"] + ".")
    add("- Config fair: the single blend variant `pair_lambdas(w, p, mode=blend,")
    add("  rho=0)` quote for the bet's fixture/market/side on that snapshot — the")
    add("  model re-centered on each config, all else frozen.")
    add("- Gate replay: " + payload["gate_replay_definition"] + ".")
    add("- FLIP = the config's replay decision differs from the **base config's")
    add("  replay** (same gates, only the prior changed).")
    add("- Cross-league UCL/UEL rows were originally priced by bespoke pre-bridge")
    add("  scripts; they are replayed through the sanctioned WP-P2a bridge with the")
    add("  archived κ table (`round31/raw/league_strength_kappa.json`). Their")
    add("  reproduction deltas are expected (the sanctioned path differs from the")
    add("  banned raw combination) and are reported per bet.")
    add("")
    add("## Reproduction fidelity (10-variant sweep vs recorded ledger fairs)")
    add("")
    add("Numeric source for every row is the freshest lineage archive")
    add("(r25) truncated to the pre-kickoff information set; the")
    add("placement-era column names the freshest archive that strictly")
    add("predates the kickoff date (the round window that placed the bet).")
    add("")
    add("| bet | placement-era archive | recomputed med | recorded med | Δ (c) |")
    add("|-----|------------------------|----------------|--------------|-------|")
    domestic_deltas = []
    for r in payload["bet_results"]:
        rep = r["reproduction"]
        if "sweep_median" in rep:
            add(f"| #{r['bet_id']} | {rep['placement_era_snapshot']} | {rep['sweep_median']:.4f} | "
                f"{float(rep['recorded'][2]):.4f} | {rep['median_delta_c']:+.1f} |")
            if not rep.get("cross_league"):
                domestic_deltas.append(abs(rep["median_delta_c"]))
        else:
            add(f"| #{r['bet_id']} | {rep['placement_era_snapshot']} | REFUSED | "
                f"{float(rep['recorded'][2]):.4f} | n/a |")
    if domestic_deltas:
        add("")
        add(f"Domestic same-league rows (n={len(domestic_deltas)}): median |Δ| "
            f"{statistics.median(domestic_deltas):.1f}c, max {max(domestic_deltas):.1f}c. "
            "Large deltas concentrate in the six cross-league UCL/UEL rows, "
            "whose originals were bespoke pre-bridge combinations (expected; "
            "see Method).")
    add("")
    add("## Per-bet config quotes and gate replay")
    add("")
    add("| bet | mkt | px | base | A p16 | B w25 | C w75 | base gate | flip A/B/C | P&L |")
    add("|-----|-----|----|------|-------|-------|-------|-----------|------------|-----|")
    for r in payload["bet_results"]:
        c = r["configs"]
        quotes = " | ".join(f"{c[n]['fair']:.3f}" if c[n] else "—" for n, _, _ in CONFIGS)
        gates = " | ".join(
            ("PASS" if c[n]["gate"]["passed"] else "fail") if c[n] else "—" for n, _, _ in CONFIGS)
        flips = []
        for n, _, _ in CONFIGS:
            if n != "base" and c[n] and c[n].get("flip_vs_base"):
                flips.append(n.split("_")[0])
        add(f"| #{r['bet_id']} | {r['market']}{' ' + str(r['line']) if r['line'] else ''} "
            f"| {r['price']:.3f} | {quotes} | {gates} | "
            f"{','.join(flips) or '—'} | {r['pnl']:+.0f} |")
    add("")
    add("## (1) Flip counts vs base replay")
    add("")
    add("| config | flips | flipped bets |")
    add("|--------|-------|--------------|")
    for n, _, _ in CONFIGS:
        add(f"| {n} | {agg['flip_counts'][n]} | "
            f"{', '.join('#%d' % i for i in agg['flips_detail'][n]) or '—'} |")
    add("")
    add("## (2) Counterfactual P&L")
    add("")
    add("Realized settled soccer P&L (all replayed rows): "
        f"{agg['realized_pnl_all_soccer']:+.2f}")
    add("")
    add("| config | replay P&L | Δ vs base replay |")
    add("|--------|-----------|------------------|")
    for n, _, _ in CONFIGS:
        pnl = agg['counterfactual_pnl'][n]
        add(f"| {n} | {pnl:+.2f} | {pnl - agg['counterfactual_pnl']['base']:+.2f} |")
    add("")
    add("Base replay keeps "
        f"{agg['base_replay_agreement_with_placement']['base_pass']}/{agg['base_replay_agreement_with_placement']['bets']} "
        "placed bets under the frozen gates (drops are pre-freeze-era placements).")
    add("")
    add("## (3) Calibration — settled `ou_over` (n="
        f"{cal['n']}, hits {cal['hits']}, hit rate {cal['hit_rate']:.3f})")
    add("")
    add("| model | mean prob | \\|mean − hit_rate\\| (c) |")
    add("|-------|-----------|------------------------|")
    add(f"| production ledger median-of-10 (as recorded) | {cal['production_ledger']['mean_prob']:.4f} | "
        f"{cal['production_ledger']['calib_err']*100:.1f} |")
    for n, _, _ in CONFIGS:
        add(f"| {n} | {cal[n]['mean_prob']:.4f} | {cal[n]['calib_err']*100:.1f} |")
    add("")
    add(f"Over-family secondary (`ou_over` + `team_total`, n={calf['n']}, "
        f"hit rate {calf['hit_rate']:.3f}): "
        + ", ".join(f"{n} {calf[n]['calib_err']*100:.1f}c" for n, _, _ in CONFIGS) + ".")
    add("")
    add("## var_spread stability (C4)")
    add("")
    add(f"Per-bet spread across the four config quotes: median "
        f"{agg['spread4']['median']*100:.1f}c, max {agg['spread4']['max']*100:.1f}c; "
        f"bets over the 6c bar: "
        f"{', '.join('#%d' % i for i in agg['spread4']['over_6c_bets']) or 'none'}.")
    add("")
    add("## (4) Promotion-criteria verdicts")
    add("")
    add("| config | C1 calib Δ (≥3c) | C2 win-rate | C3 cf P&L (≥−$250) | C4 spread | verdict |")
    add("|--------|------------------|-------------|--------------------|-----------|---------|")
    add("| base | — (incumbent) | — | "
        f"{agg['counterfactual_pnl']['base']:+.2f} | — | BASELINE |")
    for n, c in crit.items():
        add(f"| {n} | {c['C1_calibration_improvement_c']:+.1f}c "
            f"({'PASS' if c['C1_pass'] else 'FAIL'}) | "
            f"{c['C2_winrate']['config']['win_rate']} vs base {c['C2_winrate']['base']['win_rate']} "
            f"({'PASS' if c['C2_winrate']['pass'] else 'FAIL'}) | "
            f"{c['C3_counterfactual_pnl']['total']:+.2f} "
            f"({'PASS' if c['C3_counterfactual_pnl']['pass'] else 'FAIL'}) | "
            f"{c['C4_var_spread']['median_spread4_c']:.1f}c "
            f"({'PASS' if c['C4_var_spread']['pass'] else 'FAIL'}) | "
            f"{'PROMOTE' if c['eligible'] else 'REJECT'} |")
    add("")
    add("## Verdict")
    add("")
    if payload["best_config"]:
        add(f"Best config: **{payload['best_config']}** — all four pre-registered")
        add("criteria met. Promotion still requires the walk-forward forecast")
        add("evaluation across available matches (codex review recommendation 5),")
        add("not only the selected bets replayed here.")
    else:
        add("No alternative config meets all four pre-registered criteria.")
        add("The incumbent shrinkage prior (w=0.5, p=8) stands.")
    add("")
    add(f"P2c VERDICT: {payload['verdict']}")
    add("")
    with open(OUT_DIR / "shadow_report.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
