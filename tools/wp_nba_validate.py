"""WP-NBA-3 validation harness: NBA model walk-forward + market gates.

Report-only evaluation of the WP-NBA-2 model (:mod:`nba_model`) on the
WP-NBA-1 ESPN snapshot, mirroring the WP-P3 gate philosophy. This module
NEVER decides promotion: it computes the gate numbers and writes
``report.md`` + ``results.json`` for the coordinator's review.

What it does (paper-only, read-only inputs, no DB writes, no entries):

- Gate A (data integrity): reload the snapshot through the adapter's
  fail-closed validator, rebuild it from the retained ESPN raw-payload
  cache and byte-compare team/injury tables, and report count/pace-band
  numbers (the adapter itself enforces the hard integrity boundary).
- Walk-forward (gate D mirror): for every snapshot game with at least
  ``--min-prior-games`` strictly-earlier games for BOTH teams, re-predict
  from a snapshot TRUNCATED at the game date (ratings, sigma walk,
  league means, HCA and B2B fit all causal; ``before_date`` also passed)
  and score ML Brier/log-loss against (a) the model, (b) a league-average
  coin flip, (c) a home-always baseline, plus totals log-loss at the
  ESPN-captured DraftKings closing line (fallback: the model's own median
  exp_total, labeled as such).
- Gate B (goal/points fit, the xG analog): correlation between model
  exp_total / exp_margin and actual totals / margins over the
  walk-forward set.
- Gate C (rating sanity): Spearman correlation of full-snapshot EWMA
  ORtg / net rating against league-table order (win% and actual
  possession-weighted net rating), plus ML reliability bins.
- Gate E (market comparison): devig the ESPN-captured DraftKings
  moneylines, compare model p_home vs market implied (MAD, favorite
  flips), and pull CLOB prices-history for the most recent mapped
  Polymarket NBA moneyline markets (Gamma slug lookup) to compute
  model-vs-PM-closing MAD on the two-sided closing midpoint.
- Variant-spread audit: distribution of the six-variant spread on
  p_home and the totals quote across the walk-forward set, fraction
  above the 6c soccer bar, and the trend as games accumulate.

Usage (server, the big compute)::

    .venv/bin/python /tmp/wp_nba3/wp_nba_validate.py \
        --snapshot ~/paper-sim/nba/snapshot_20261110.json \
        --cache-dir ~/paper-sim/nba/cache \
        --out-dir  ~/paper-sim/review/wp_nba_validation

``--skip-pm`` disables the networked Polymarket part; ``--skip-dk``
disables DraftKings extraction (totals then fall back to the model
median line). The two sibling modules ``espn_nba.py`` / ``nba_model.py``
are imported from this file's directory when present (standalone /tmp
deployment) and from the installed package otherwise (local worktree).

No credentials, no order paths, no persistence beyond the report files.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# module resolution: standalone dir (server /tmp) or installed package
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
if (_HERE / "espn_nba.py").is_file() and (_HERE / "nba_model.py").is_file():
    sys.path.insert(0, str(_HERE))
    import espn_nba  # type: ignore
    import nba_model  # type: ignore
else:  # local worktree: package installed editable in .venv
    from polymarket_alpha_lab.papersim import espn_nba, nba_model  # type: ignore

#: Log-loss clip floor (0/1 probabilities of degenerate baselines).
_EPS = 1e-12

#: Walk-forward eligibility floor (task spec: >= 8 prior games BOTH teams).
DEFAULT_MIN_PRIOR_GAMES = 8

#: The soccer variant-spread bar (papersim GATES["variant_spread_max"]).
VARIANT_SPREAD_BAR = 0.06

#: Gate-D minimum scored games before a PASS-able read (stated in report).
GATE_D_MIN_N = 20

#: Gate-B bar: Pearson r(exp_total, actual total) >= 0.25 with p < 0.05.
GATE_B_MIN_R = 0.25
GATE_B_MAX_P = 0.05

#: Gate-C bar: Spearman rho(EWMA net rating, win%) >= 0.5 over 30 teams.
GATE_C_MIN_RHO = 0.5

#: Gate-E bar (task wording): market MAD <= 6c. (Round-46 feasibility
#: target was 4-5c; reported alongside.)
GATE_E_MAX_MAD = 0.06

#: ESPN abbrev -> Polymarket event-slug abbrev (probed 2026-11-09; the
#: other 24 teams are a plain lowercase of the ESPN abbreviation).
_PM_ABBREV: dict[str, str] = {
    "GS": "gsw", "NY": "nyk", "SA": "sas",
    "UTAH": "uta", "WSH": "was", "NO": "nop",
}

_GAMMA_BASE = "https://gamma-api.polymarket.com"
_CLOB_BASE = "https://clob.polymarket.com"
_UA = "polymarket-alpha-lab/0.1 (wp-nba-3 validation)"


# ---------------------------------------------------------------------------
# small statistics helpers (stdlib only)
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> float:
    return math.fsum(values) / len(values)


def _sample_std(values: list[float]) -> float:
    count = len(values)
    if count < 2:
        return float("nan")
    mu = _mean(values)
    return math.sqrt(math.fsum((v - mu) ** 2 for v in values) / (count - 1))


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (ties share the mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _corr_pvalue(r: float, n: int) -> float:
    """Two-sided p for a correlation via Fisher z (normal approx)."""
    if n < 4 or not math.isfinite(r) or abs(r) >= 1.0:
        return float("nan") if n < 4 else (0.0 if abs(r) >= 1.0 else float("nan"))
    z = 0.5 * math.log((1.0 + r) / (1.0 - r)) * math.sqrt(n - 3.0)
    return math.erfc(abs(z) / math.sqrt(2.0))


def pearson(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """(r, two-sided p) — NaN when either side is constant."""
    if len(xs) != len(ys) or len(xs) < 3:
        return (float("nan"), float("nan"))
    mx, my = _mean(xs), _mean(ys)
    cov = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var_x = math.fsum((x - mx) ** 2 for x in xs)
    var_y = math.fsum((y - my) ** 2 for y in ys)
    if var_x == 0.0 or var_y == 0.0:
        return (float("nan"), float("nan"))
    r = cov / math.sqrt(var_x * var_y)
    return (r, _corr_pvalue(r, len(xs)))


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """(rho, approx two-sided p) on average ranks."""
    if len(xs) != len(ys) or len(xs) < 3:
        return (float("nan"), float("nan"))
    return pearson(_ranks(xs), _ranks(ys))


def brier_score(probs: list[float], outcomes: list[int]) -> float:
    return _mean([(p - o) ** 2 for p, o in zip(probs, outcomes)])


def log_loss(probs: list[float], outcomes: list[int]) -> tuple[float, int]:
    """(mean NLL, clip count) with the EPS floor documented."""
    clipped = 0
    total = 0.0
    for p, o in zip(probs, outcomes):
        q = min(max(p, _EPS), 1.0 - _EPS)
        if q != p:
            clipped += 1
        total += -(math.log(q) if o else math.log(1.0 - q))
    return total / len(probs), clipped


def american_to_prob(odds: float) -> float:
    """Raw (vig-in) probability of one American-odds quote."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    if odds < 0:
        return -odds / (-odds + 100.0)
    raise ValueError(f"American odds of 0 are not a quote ({odds!r})")


def devig_2way(ml_a: float, ml_b: float) -> tuple[float, float]:
    """(devigged prob of side a, vig)."""
    pa, pb = american_to_prob(ml_a), american_to_prob(ml_b)
    total = pa + pb
    return pa / total, total - 1.0


# ---------------------------------------------------------------------------
# transport (read-only public GETs, polite)
# ---------------------------------------------------------------------------


def _get_json(url: str, *, timeout: float = 25.0, attempts: int = 3) -> object:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": _UA, "Accept": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {attempts} attempts: {url} ({last})")


def _load_json_tokens(raw: object) -> list[str]:
    """Gamma's outcomes/clobTokenIds arrive JSON-encoded as strings."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError(f"expected a JSON list, got {type(raw)!r}")
    return [str(item) for item in raw]


# ---------------------------------------------------------------------------
# snapshot plumbing
# ---------------------------------------------------------------------------


def pair_snapshot_games(snapshot: dict) -> list[dict]:
    """Pair home/away rows of every snapshot game (adapter emitted both).

    Integrity mirrors the model's pairing guard: both rows must exist,
    agree on the score, and no double-home/double-away claims.
    """
    home_side: dict[tuple[str, str], dict] = {}
    away_side: dict[tuple[str, str], dict] = {}
    for team, block in sorted(snapshot["teams"].items()):
        for row in block["games"]:
            key = (row["date"], team, row["opponent"])
            if row["home"]:
                if key in home_side:
                    raise ValueError(f"duplicate home row {key}")
                home_side[key] = row
            else:
                if key in away_side:
                    raise ValueError(f"duplicate away row {key}")
                away_side[key] = row
    games: list[dict] = []
    for (game_date, team, opponent), row in sorted(home_side.items()):
        away_row = away_side.get((game_date, opponent, team))
        if away_row is None:
            raise ValueError(f"missing away row for {game_date} {team} vs {opponent}")
        if row["pts"] != away_row["opp_pts"] or row["opp_pts"] != away_row["pts"]:
            raise ValueError(f"score disagreement {game_date} {team} vs {opponent}")
        games.append({
            "date": game_date,
            "home": team,
            "away": opponent,
            "home_pts": row["pts"],
            "away_pts": row["opp_pts"],
            "rest_home": row["rest_days"],
            "rest_away": away_row["rest_days"],
            "b2b_home": row["b2b"],
            "b2b_away": away_row["b2b"],
        })
    return games


def prior_counts(snapshot: dict, game_date: str) -> dict[str, int]:
    """Completed snapshot games strictly before ``game_date`` per team."""
    counts: dict[str, int] = {team: 0 for team in snapshot["teams"]}
    for team, block in snapshot["teams"].items():
        for row in block["games"]:
            if row["date"] < game_date:
                counts[team] += 1
    return counts


def truncate_snapshot(snapshot: dict, before_date: str) -> dict:
    """Snapshot with every team's games strictly before ``before_date``.

    rest_days / b2b of surviving rows reference only strictly-earlier
    games, so truncation leaves them valid. Top-level keys preserved
    (the model's frozen contract).
    """
    return {
        "generated_at": snapshot["generated_at"],
        "source": snapshot.get("source", "espn-nba"),
        "season": snapshot["season"],
        "teams": {
            team: {
                "display": block["display"],
                "games": [row for row in block["games"] if row["date"] < before_date],
            }
            for team, block in snapshot["teams"].items()
        },
        "injuries": snapshot.get("injuries", {}),
    }


# ---------------------------------------------------------------------------
# DraftKings odds from the retained ESPN raw cache
# ---------------------------------------------------------------------------


def dk_odds_from_cache(cache_dir: Path) -> tuple[dict[tuple[str, str, str], dict], dict]:
    """``(et_date, home_abbrev, away_abbrev) -> DK odds`` from cached summaries.

    The backfill fetched every summary after the game was final, so the
    pickcenter block is the DraftKings closing line as retained by ESPN.
    Provider is verified as Draft Kings on every payload (fail-closed:
    a non-DK provider is skipped and counted, never silently used).
    """
    odds: dict[tuple[str, str, str], dict] = {}
    skipped_provider = 0
    malformed = 0
    for path in sorted(cache_dir.glob("summary_*.json")):
        eid = path.stem.replace("summary_", "")
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        header = payload.get("header") or {}
        comps = (header.get("competitions") or [{}])[0]
        raw_date = comps.get("date")
        sides = {}
        for competitor in comps.get("competitors") or []:
            side = competitor.get("homeAway")
            team = (competitor.get("team") or {}).get("abbreviation")
            if side in ("home", "away") and isinstance(team, str):
                sides[side] = team
        if raw_date is None or set(sides) != {"home", "away"}:
            malformed += 1
            continue
        et_date = espn_nba._et_date(str(raw_date), eid).isoformat()
        pickcenter = payload.get("pickcenter") or []
        entry = None
        for candidate in pickcenter:
            name = str((candidate.get("provider") or {}).get("name", "")).lower()
            if "draft" in name and "king" in name.replace(" ", ""):
                entry = candidate
                break
        if entry is None:
            skipped_provider += 1
            continue
        home_ml = (entry.get("homeTeamOdds") or {}).get("moneyLine")
        away_ml = (entry.get("awayTeamOdds") or {}).get("moneyLine")
        if not isinstance(home_ml, (int, float)) or not isinstance(away_ml, (int, float)):
            malformed += 1
            continue
        odds[(et_date, sides["home"], sides["away"])] = {
            "event_id": eid,
            "start_utc": str(raw_date),
            "home_ml": float(home_ml),
            "away_ml": float(away_ml),
            "total_line": entry.get("overUnder"),
            "over_odds": entry.get("overOdds"),
            "under_odds": entry.get("underOdds"),
            "spread_details": entry.get("details"),
        }
    stats = {
        "summaries": len(list(cache_dir.glob("summary_*.json"))),
        "dk_mapped": len(odds),
        "skipped_non_dk_provider": skipped_provider,
        "malformed": malformed,
    }
    return odds, stats


# ---------------------------------------------------------------------------
# walk-forward evaluation
# ---------------------------------------------------------------------------


def walk_forward(
    snapshot: dict,
    games: list[dict],
    min_prior: int,
    dk: dict[tuple[str, str, str], dict] | None,
) -> tuple[list[dict], dict]:
    """Re-predict every eligible game from strictly-earlier information.

    Eligibility: at least ``min_prior`` snapshot games strictly before
    the game date for BOTH teams (the model itself refuses at zero).
    Causality: the snapshot is truncated at the game date AND
    ``before_date`` is passed, so ratings, the sigma walk, league means,
    HCA and the B2B fit see only strictly-earlier games.
    """
    records: list[dict] = []
    refused = 0
    for game in games:
        counts = prior_counts(snapshot, game["date"])
        prior_home, prior_away = counts[game["home"]], counts[game["away"]]
        if prior_home < min_prior or prior_away < min_prior:
            continue
        truncated = truncate_snapshot(snapshot, game["date"])
        fixture = nba_model.NbaFixture(
            home=game["home"],
            away=game["away"],
            rest_home=game["rest_home"],
            rest_away=game["rest_away"],
            b2b_home=game["b2b_home"],
            b2b_away=game["b2b_away"],
        )
        reason = nba_model.refusal_reason(truncated, fixture, before_date=game["date"])
        if reason is not None:
            refused += 1
            continue
        prediction = nba_model.fixture_prediction(
            truncated, fixture, before_date=game["date"]
        )
        assert prediction is not None  # refusal_reason above is None
        game_odds = (dk or {}).get((game["date"], game["home"], game["away"]))
        total_line = None
        line_source = None
        if game_odds is not None and isinstance(game_odds.get("total_line"), (int, float)):
            total_line = float(game_odds["total_line"])
            line_source = "dk_closing"
        else:
            total_line = prediction.exp_total
            line_source = "model_median"
        quote = prediction.total_line_prob(total_line)
        actual_total = game["home_pts"] + game["away_pts"]
        outcome = 1 if game["home_pts"] > game["away_pts"] else 0
        records.append({
            "date": game["date"],
            "home": game["home"],
            "away": game["away"],
            "prior_home": prior_home,
            "prior_away": prior_away,
            "min_prior": min(prior_home, prior_away),
            "home_win": outcome,
            "actual_margin": game["home_pts"] - game["away_pts"],
            "actual_total": actual_total,
            "p_home": prediction.p_home,
            "p_home_range": list(prediction.p_home_range),
            "p_home_variant_spread": prediction.p_home_variant_spread,
            "exp_margin": prediction.exp_margin,
            "exp_total": prediction.exp_total,
            "sigma_margin": prediction.sigma_margin,
            "sigma_total": prediction.sigma_total,
            "sigma_margin_residuals": prediction.sigma_margin_residuals,
            "exp_total_variant_spread": prediction.exp_total_variant_spread,
            "total_line": total_line,
            "total_line_source": line_source,
            "p_over": quote.p_over,
            "totals_variant_spread": quote.variant_spread,
            "total_push": actual_total == total_line,
            "over_outcome": None if actual_total == total_line else int(actual_total > total_line),
            "variant_p_home": {
                variant.spec.name: variant.p_home for variant in prediction.variants
            },
            "dk": game_odds,
        })
    info = {
        "min_prior_games": min_prior,
        "eligible_and_scored": len(records),
        "model_refusals_in_eligible_set": refused,
    }
    return records, info


def ml_metrics(records: list[dict]) -> dict:
    """ML Brier + log-loss: model vs coin-flip vs home-always."""
    outcomes = [record["home_win"] for record in records]
    n = len(records)
    model_p = [record["p_home"] for record in records]
    model_brier = brier_score(model_p, outcomes)
    model_ll, model_clips = log_loss(model_p, outcomes)
    coin_brier = brier_score([0.5] * n, outcomes)
    coin_ll, _ = log_loss([0.5] * n, outcomes)
    home_brier = brier_score([1.0] * n, outcomes)
    home_ll, home_clips = log_loss([1.0] * n, outcomes)
    return {
        "n": n,
        "home_win_rate": _mean(outcomes),
        "model": {"brier": model_brier, "log_loss": model_ll, "clipped": model_clips},
        "coin_flip": {"brier": coin_brier, "log_loss": coin_ll, "clipped": 0},
        "home_always": {
            "brier": home_brier, "log_loss": home_ll, "clipped": home_clips,
        },
        "model_beats_coin_brier": model_brier < coin_brier,
        "model_beats_coin_log_loss": model_ll < coin_ll,
        "model_beats_home_brier": model_brier < home_brier,
        "model_beats_home_log_loss": model_ll < home_ll,
    }


def totals_metrics(records: list[dict]) -> dict:
    """Totals log-loss at the evaluated line (DK closing when present)."""
    scored = [r for r in records if r["over_outcome"] is not None]
    n_push = sum(1 for r in records if r["total_push"])
    dk_lines = [r for r in scored if r["total_line_source"] == "dk_closing"]
    model_lines = [r for r in scored if r["total_line_source"] == "model_median"]
    outcomes = [r["over_outcome"] for r in scored]
    probs = [r["p_over"] for r in scored]
    ll, clips = log_loss(probs, outcomes)
    coin_ll, _ = log_loss([0.5] * len(scored), outcomes)
    over_rate = _mean(outcomes) if outcomes else float("nan")
    return {
        "n": len(scored),
        "pushes_excluded": n_push,
        "line_sources": {"dk_closing": len(dk_lines), "model_median": len(model_lines)},
        "over_rate": over_rate,
        "model_log_loss": ll,
        "coin_log_loss": coin_ll,
        "clipped": clips,
        "model_beats_coin": ll < coin_ll,
    }


# ---------------------------------------------------------------------------
# gates B (points fit), C (rating sanity + calibration)
# ---------------------------------------------------------------------------


def gate_b_fit(records: list[dict]) -> dict:
    exp_total = [r["exp_total"] for r in records]
    actual_total = [float(r["actual_total"]) for r in records]
    exp_margin = [r["exp_margin"] for r in records]
    actual_margin = [float(r["actual_margin"]) for r in records]
    r_total, p_total = pearson(exp_total, actual_total)
    rho_total, rho_p_total = spearman(exp_total, actual_total)
    r_margin, p_margin = pearson(exp_margin, actual_margin)
    rho_margin, _ = spearman(exp_margin, actual_margin)
    n = len(records)
    mean_abs_total_err = _mean(
        [abs(e - a) for e, a in zip(exp_total, actual_total)]
    )
    mean_abs_margin_err = _mean(
        [abs(e - a) for e, a in zip(exp_margin, actual_margin)]
    )
    passed = (
        n >= GATE_D_MIN_N
        and math.isfinite(r_total)
        and r_total >= GATE_B_MIN_R
        and p_total < GATE_B_MAX_P
    )
    return {
        "n": n,
        "pearson_exp_total_vs_actual": {"r": r_total, "p": p_total},
        "spearman_exp_total_vs_actual": {"rho": rho_total, "p": rho_p_total},
        "pearson_exp_margin_vs_actual": {"r": r_margin, "p": p_margin},
        "spearman_exp_margin_vs_actual_rho": rho_margin,
        "mean_abs_total_error_pts": mean_abs_total_err,
        "mean_abs_margin_error_pts": mean_abs_margin_err,
        "bar": f"Pearson r(exp_total, actual) >= {GATE_B_MIN_R} with p < {GATE_B_MAX_P} and n >= {GATE_D_MIN_N}",
        "passed": passed,
    }


def gate_c_sanity(snapshot: dict) -> dict:
    """EWMA ORtg / net rating vs league-table order (win%, actual net)."""
    rows_by_team: dict[str, list[dict]] = {
        team: block["games"] for team, block in snapshot["teams"].items()
    }
    table: list[dict] = []
    for team, rows in sorted(rows_by_team.items()):
        poss = math.fsum(r["poss"] for r in rows)
        wins = sum(1 for r in rows if r["pts"] > r["opp_pts"])
        table.append({
            "team": team,
            "games": len(rows),
            "win_pct": wins / len(rows),
            "actual_net_rtg": (
                100.0
                * (math.fsum(r["pts"] for r in rows) - math.fsum(r["opp_pts"] for r in rows))
                / poss
            ),
        })
    for entry in table:
        ratings = nba_model.team_ratings(snapshot, entry["team"])
        assert ratings is not None
        entry["ewma_ortg"] = ratings.ortg
        entry["ewma_drtg"] = ratings.drtg
        entry["ewma_net"] = ratings.ortg - ratings.drtg
    win = [e["win_pct"] for e in table]
    net = [e["actual_net_rtg"] for e in table]
    ortg = [e["ewma_ortg"] for e in table]
    ewma_net = [e["ewma_net"] for e in table]
    rho_ortg_win, p1 = spearman(ortg, win)
    rho_net_win, p2 = spearman(ewma_net, win)
    rho_ortg_net, _ = spearman(ortg, net)
    rho_net_net, _ = spearman(ewma_net, net)
    passed = (
        len(table) == espn_nba.TEAM_COUNT
        and math.isfinite(rho_net_win)
        and rho_net_win >= GATE_C_MIN_RHO
    )
    return {
        "teams": len(table),
        "spearman_ewma_ortg_vs_win_pct": {"rho": rho_ortg_win, "p": p1},
        "spearman_ewma_net_vs_win_pct": {"rho": rho_net_win, "p": p2},
        "spearman_ewma_ortg_vs_actual_net": rho_ortg_net,
        "spearman_ewma_net_vs_actual_net": rho_net_net,
        "bar": f"Spearman rho(EWMA net rating, win%) >= {GATE_C_MIN_RHO} over {espn_nba.TEAM_COUNT} teams",
        "passed": passed,
        "table": table,
    }


def calibration_bins(records: list[dict]) -> list[dict]:
    """ML reliability bins (0.2-wide) over the walk-forward set."""
    bins = [
        {"lo": lo / 5.0, "hi": (lo + 1) / 5.0, "n": 0, "pred_sum": 0.0, "wins": 0}
        for lo in range(5)
    ]
    for record in records:
        p, o = record["p_home"], record["home_win"]
        index = min(4, int(p * 5.0))
        bins[index]["n"] += 1
        bins[index]["pred_sum"] += p
        bins[index]["wins"] += o
    out = []
    for bin_ in bins:
        entry = {"range": f"[{bin_['lo']:.1f},{bin_['hi']:.1f})", "n": bin_["n"]}
        if bin_["n"]:
            entry["predicted_mean"] = bin_["pred_sum"] / bin_["n"]
            entry["actual_rate"] = bin_["wins"] / bin_["n"]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# variant-spread audit
# ---------------------------------------------------------------------------


def variant_audit(records: list[dict]) -> dict:
    def spread_stats(values: list[float]) -> dict:
        if not values:
            return {
                "n": 0, "mean": None, "median": None,
                "p90": None, "max": None, "fraction_over_6c": None,
            }
        ordered = sorted(values)
        return {
            "n": len(values),
            "mean": _mean(values),
            "median": ordered[len(ordered) // 2],
            "p90": ordered[min(len(ordered) - 1, int(math.ceil(0.9 * len(ordered))) - 1)],
            "max": ordered[-1],
            "fraction_over_6c": sum(1 for v in values if v > VARIANT_SPREAD_BAR) / len(values),
        }

    def bucket_by_min_prior() -> list[dict]:
        edges = [(8, 9), (10, 11), (12, 99)]
        out = []
        for lo, hi in edges:
            subset = [r for r in records if lo <= r["min_prior"] <= hi]
            out.append({
                "min_prior_bucket": f"{lo}-{hi if hi < 99 else '+'}",
                **{
                    f"p_home_{k}": v for k, v in spread_stats(
                        [r["p_home_variant_spread"] for r in subset]
                    ).items()
                },
                **{
                    f"totals_{k}": v for k, v in spread_stats(
                        [r["totals_variant_spread"] for r in subset]
                    ).items()
                },
            })
        return out

    def bucket_by_time() -> list[dict]:
        if not records:
            return []
        dates = sorted({r["date"] for r in records})
        third = max(1, len(dates) // 3)
        windows = [
            ("early_third", dates[0], dates[third - 1]),
            ("mid_third", dates[third], dates[2 * third - 1] if len(dates) > 2 * third else dates[-1]),
            ("late_third", dates[min(2 * third, len(dates) - 1)], dates[-1]),
        ]
        out = []
        for name, lo, hi in windows:
            subset = [r for r in records if lo <= r["date"] <= hi]
            if not subset:
                continue
            out.append({
                "window": name,
                "dates": f"{lo}..{hi}",
                "n": len(subset),
                "p_home_mean_spread": _mean([r["p_home_variant_spread"] for r in subset]),
                "totals_mean_spread": _mean([r["totals_variant_spread"] for r in subset]),
                "p_home_fraction_over_6c": sum(
                    1 for r in subset if r["p_home_variant_spread"] > VARIANT_SPREAD_BAR
                ) / len(subset),
                "totals_fraction_over_6c": sum(
                    1 for r in subset if r["totals_variant_spread"] > VARIANT_SPREAD_BAR
                ) / len(subset),
            })
        return out

    # which variant dimension drives the p_home spread (hl vs sigma)
    drivers = {"half_life": 0, "sigma": 0, "mixed": 0}
    for record in records:
        per_variant = record["variant_p_home"]
        hl_lo = min(per_variant[f"hl{hl:g}-sig1"] for hl in nba_model.SWEEP_HALF_LIVES)
        hl_hi = max(per_variant[f"hl{hl:g}-sig1"] for hl in nba_model.SWEEP_HALF_LIVES)
        sg_lo = min(per_variant[f"hl{nba_model.DEFAULT_HALF_LIFE:g}-sig{s:g}"] for s in nba_model.SWEEP_SIGMA_SCALES)
        sg_hi = max(per_variant[f"hl{nba_model.DEFAULT_HALF_LIFE:g}-sig{s:g}"] for s in nba_model.SWEEP_SIGMA_SCALES)
        hl_span, sg_span = hl_hi - hl_lo, sg_hi - sg_lo
        if hl_span > sg_span * 1.5:
            drivers["half_life"] += 1
        elif sg_span > hl_span * 1.5:
            drivers["sigma"] += 1
        else:
            drivers["mixed"] += 1

    return {
        "bar_cents": VARIANT_SPREAD_BAR * 100.0,
        "p_home": spread_stats([r["p_home_variant_spread"] for r in records]),
        "exp_total_pts": spread_stats([r["exp_total_variant_spread"] for r in records]),
        "totals_quote": spread_stats([r["totals_variant_spread"] for r in records]),
        "by_min_prior": bucket_by_min_prior(),
        "by_time": bucket_by_time(),
        "p_home_spread_driver": drivers,
    }


# ---------------------------------------------------------------------------
# market comparison: DraftKings devig + Polymarket closing
# ---------------------------------------------------------------------------


def market_dk(records: list[dict], all_games: list[dict], snapshot: dict, dk: dict) -> dict:
    """Model p_home vs devigged DK closing ML, walk-forward + eligible sets."""

    def compare(game_records: list[dict]) -> dict:
        rows = []
        for record in game_records:
            odds = record.get("dk")
            if odds is None:
                continue
            p_home_mkt, vig = devig_2way(odds["home_ml"], odds["away_ml"])
            rows.append({
                "date": record["date"],
                "home": record["home"],
                "away": record["away"],
                "p_home_model": record["p_home"],
                "p_home_mkt": p_home_mkt,
                "vig": vig,
                "abs_dev": abs(record["p_home"] - p_home_mkt),
                "model_favorite_home": record["p_home"] > 0.5,
                "mkt_favorite_home": p_home_mkt > 0.5,
            })
        if not rows:
            return {"n": 0}
        devs = [r["abs_dev"] for r in rows]
        ordered = sorted(devs)
        flips = sum(
            1 for r in rows if r["model_favorite_home"] != r["mkt_favorite_home"]
        )
        exact_ties = sum(
            1 for r in rows if r["p_home_model"] == 0.5 or r["p_home_mkt"] == 0.5
        )
        return {
            "n": len(rows),
            "mad": _mean(devs),
            "median_ad": ordered[len(ordered) // 2],
            "p90_ad": ordered[min(len(ordered) - 1, int(math.ceil(0.9 * len(ordered))) - 1)],
            "max_ad": ordered[-1],
            "mean_vig": _mean([r["vig"] for r in rows]),
            "favorite_flips": flips,
            "exact_0p5_ties": exact_ties,
            "rows": rows,
        }

    # wider context set: every model-eligible game (>=1 prior per team)
    eligible_records, _ = walk_forward(snapshot, all_games, 1, dk)
    return {
        "walk_forward_set": compare(records),
        "model_eligible_set_ge1": compare(eligible_records),
        "source_note": (
            "ESPN pickcenter DraftKings quotes captured post-final in the "
            "WP-NBA-1 backfill cache; treated as the closing line"
        ),
    }


def _pm_slug(away: str, home: str, game_date: str) -> str:
    return f"nba-{_PM_ABBREV.get(away, away.lower())}-{_PM_ABBREV.get(home, home.lower())}-{game_date}"


def _match_name(outcome: str, display: str) -> bool:
    """PM outcome name is a word-suffix of the ESPN display name."""
    o = outcome.strip().lower()
    d = display.strip().lower()
    return d.endswith(o) and (len(d) == len(o) or d[-len(o) - 1].isspace())


def market_pm(records: list[dict], snapshot: dict, n_markets: int) -> dict:
    """Model p_home vs Polymarket CLOB closing midpoint for recent games.

    Mapping: Gamma event slug ``nba-{away}-{home}-{date}`` (abbrev table
    probed 2026-11-09; both orders tried), moneyline market = the one
    whose two outcomes are the matchup's team names (order-agnostic; the
    home token is located by name). Closing = last prices-history point
    strictly before the market's gameStartTime, two-sided midpoint
    (home yes + 1 - away yes) / 2.
    """
    display = {t: b["display"] for t, b in snapshot["teams"].items()}
    chosen = sorted(records, key=lambda r: (r["date"], r["home"]), reverse=True)
    chosen = [r for r in chosen if r.get("dk") is not None][:n_markets]
    rows: list[dict] = []
    failures: list[dict] = []
    for record in chosen:
        home, away = record["home"], record["away"]
        event = None
        for slug in (
            _pm_slug(away, home, record["date"]),
            _pm_slug(home, away, record["date"]),
        ):
            payload = _get_json(f"{_GAMMA_BASE}/events?slug={urllib.parse.quote(slug)}")
            if isinstance(payload, list) and payload:
                event = payload[0]
                break
            time.sleep(0.4)
        if event is None:
            failures.append({"game": f"{away}@{home} {record['date']}", "reason": "slug not found"})
            continue
        time.sleep(0.4)
        market = None
        for candidate in event.get("markets") or []:
            question = str(candidate.get("question") or "")
            if question.startswith("Spread") or "O/U" in question or "Margin" in question:
                continue
            outcomes = candidate.get("outcomes")
            if not isinstance(outcomes, str):
                continue
            try:
                names = _load_json_tokens(outcomes)
            except (ValueError, json.JSONDecodeError):
                continue
            if len(names) != 2 or not all(isinstance(n, str) for n in names):
                continue
            if set(names) <= {"Yes", "No", "Over", "Under"}:
                continue
            name_match = (
                _match_name(names[0], display[home]) and _match_name(names[1], display[away])
            ) or (
                _match_name(names[0], display[away]) and _match_name(names[1], display[home])
            )
            if not name_match:
                continue
            # prefer the highest-volume matching market (the ML flagship)
            if market is None or float(candidate.get("volume") or 0.0) > float(
                market.get("volume") or 0.0
            ):
                market = candidate
        if market is None:
            failures.append({"game": f"{away}@{home} {record['date']}", "reason": "no team-name market in event"})
            continue
        names = _load_json_tokens(market["outcomes"])
        tokens = _load_json_tokens(market["clobTokenIds"])
        if len(tokens) != 2:
            failures.append({"game": f"{away}@{home} {record['date']}", "reason": "token count != 2"})
            continue
        if _match_name(names[0], display[home]):
            home_token, away_token = tokens[0], tokens[1]
        else:
            home_token, away_token = tokens[1], tokens[0]
        start_raw = market.get("gameStartTime") or event.get("endDate")
        try:
            start_epoch = datetime.fromisoformat(
                str(start_raw).replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            failures.append({"game": f"{away}@{home} {record['date']}", "reason": f"bad gameStartTime {start_raw!r}"})
            continue
        prices = {}
        for label, token in (("home_yes", home_token), ("away_yes", away_token)):
            query = urllib.parse.urlencode({
                "market": token,
                "startTs": int(start_epoch - 3 * 86400),
                "endTs": int(start_epoch),
                "fidelity": 5,
            })
            payload = _get_json(f"{_CLOB_BASE}/prices-history?{query}")
            history = (payload or {}).get("history") or []
            before = [p for p in history if float(p["t"]) <= start_epoch]
            prices[label] = float(before[-1]["p"]) if before else None
            time.sleep(0.4)
        if prices["home_yes"] is None or prices["away_yes"] is None:
            failures.append({
                "game": f"{away}@{home} {record['date']}",
                "reason": "no pre-start price history",
                "prices": prices,
            })
            continue
        pm_p_home = (prices["home_yes"] + (1.0 - prices["away_yes"])) / 2.0
        row = {
            "date": record["date"],
            "game": f"{away}@{home}",
            "event_id": str(event.get("id")),
            "condition_id": market.get("conditionId"),
            "question": market.get("question"),
            "volume": float(market.get("volume") or 0.0),
            "game_start": str(start_raw),
            "pm_close_home_yes": prices["home_yes"],
            "pm_close_away_yes": prices["away_yes"],
            "pm_p_home": pm_p_home,
            "p_home_model": record["p_home"],
            "abs_dev": abs(record["p_home"] - pm_p_home),
        }
        if record.get("dk") is not None:
            dk_p, _ = devig_2way(record["dk"]["home_ml"], record["dk"]["away_ml"])
            row["p_home_dk_devig"] = dk_p
            row["pm_vs_dk_abs_dev"] = abs(pm_p_home - dk_p)
        rows.append(row)
    summary: dict = {"n_mapped": len(rows), "failures": failures, "rows": rows}
    if rows:
        devs = [r["abs_dev"] for r in rows]
        summary["mad"] = _mean(devs)
        summary["median_ad"] = sorted(devs)[len(devs) // 2]
        summary["max_ad"] = max(devs)
        pm_dk = [r["pm_vs_dk_abs_dev"] for r in rows if "pm_vs_dk_abs_dev" in r]
        if pm_dk:
            summary["pm_vs_dk_mad"] = _mean(pm_dk)
        flips = sum(
            1 for r in rows
            if (r["p_home_model"] > 0.5) != (r["pm_p_home"] > 0.5)
        )
        summary["favorite_flips_vs_pm"] = flips
    return summary


# ---------------------------------------------------------------------------
# gate A: integrity
# ---------------------------------------------------------------------------


def gate_a_integrity(snapshot_path: Path, cache_dir: Path | None, snapshot: dict) -> dict:
    games = pair_snapshot_games(snapshot)
    team_games = {
        team: len(block["games"]) for team, block in snapshot["teams"].items()
    }
    poss = [
        row["poss"]
        for block in snapshot["teams"].values()
        for row in block["games"]
    ]
    dates = sorted({g["date"] for g in games})
    result = {
        "snapshot_path": str(snapshot_path),
        "sha256_present": True,
        "teams": len(snapshot["teams"]),
        "games": len(games),
        "team_game_counts": {"min": min(team_games.values()), "max": max(team_games.values())},
        "date_range": [dates[0], dates[-1]],
        "injured_players": sum(len(v) for v in snapshot.get("injuries", {}).values()),
        "team_poss": {
            "min": min(poss), "mean": _mean(poss), "max": max(poss),
            "share_in_94_102": sum(1 for p in poss if 94.0 <= p <= 102.0) / len(poss),
        },
        "reload_validation": "pass (load_nba_snapshot accepted)",
    }
    rebuild_equal = None
    if cache_dir is not None:
        try:
            bundle = espn_nba.fetch_nba_season(
                snapshot["season"], cache_dir=cache_dir, schedule_max_age_s=None
            )
            rebuilt = espn_nba.build_snapshot(bundle, season=snapshot["season"])
            rebuild_equal = (
                rebuilt["teams"] == snapshot["teams"]
                and rebuilt["injuries"] == snapshot["injuries"]
            )
        except Exception as exc:  # noqa: BLE001 - report, don't crash the harness
            rebuild_equal = f"rebuild failed: {exc}"
        result["rebuild_from_cache_equal"] = rebuild_equal
    checks = [
        result["teams"] == espn_nba.TEAM_COUNT,
        result["games"] > 0,
        rebuild_equal is True,
    ]
    result["passed"] = all(checks)
    return result


# ---------------------------------------------------------------------------
# report writing
# ---------------------------------------------------------------------------


def _fmt(value: object, digits: int = 4) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "n/a"
        return f"{value:.{digits}f}"
    return str(value)


def write_report(out_dir: Path, results: dict) -> Path:
    lines: list[str] = []
    meta = results["meta"]
    gate_a = results["gate_a"]
    lines.append("# WP-NBA-3 NBA model validation — walk-forward + market comparison")
    lines.append("")
    lines.append(f"- generated_at (UTC): {meta['generated_at']}")
    lines.append(f"- repo revision (both hosts): {meta['revision']}")
    lines.append(f"- snapshot: `{meta['snapshot_path']}` (sha256 {meta['snapshot_sha256'][:16]}…)")
    lines.append(f"- season {meta['season']}, {gate_a['games']} games, "
                 f"{gate_a['date_range'][0]}..{gate_a['date_range'][1]}")
    lines.append(f"- eligibility: >= {results['walk_forward_info']['min_prior_games']} strictly-earlier games for BOTH teams; "
                 "predictions from snapshots truncated at the game date (fully causal: ratings, sigma walk, league means, HCA, B2B fit)")
    lines.append("- paper-only / report-only: no entries, no DB writes, no production changes; promotion NOT decided here")
    lines.append("")

    lines.append("## Gate A — data integrity")
    lines.append("")
    lines.append(f"- reload through `load_nba_snapshot`: {gate_a['reload_validation']}")
    lines.append(f"- teams {gate_a['teams']}, games {gate_a['games']}, per-team games {gate_a['team_game_counts']['min']}..{gate_a['team_game_counts']['max']}")
    lines.append(f"- team-game possessions: min {gate_a['team_poss']['min']:.1f}, mean {gate_a['team_poss']['mean']:.2f}, max {gate_a['team_poss']['max']:.1f}; "
                 f"share in the 94-102 band: {gate_a['team_poss']['share_in_94_102']:.3f}")
    lines.append(f"- rebuild from retained raw cache byte-equal (teams+injuries): {gate_a.get('rebuild_from_cache_equal')}")
    lines.append(f"- **{gate_a['verdict']}**")
    lines.append("")

    info = results["walk_forward_info"]
    metrics = results["ml_metrics"]
    lines.append("## Walk-forward evaluation (gate D mirror)")
    lines.append("")
    lines.append(f"- eligible & scored: **n = {metrics['n']}** (model refusals inside the eligible set: {info['model_refusals_in_eligible_set']})")
    lines.append(f"- home win rate: {metrics['home_win_rate']:.3f}")
    lines.append("")
    lines.append("| moneyline | Brier | log-loss | beats? |")
    lines.append("|---|---|---|---|")
    lines.append(f"| model (6-variant median) | {metrics['model']['brier']:.4f} | {metrics['model']['log_loss']:.4f} | — |")
    lines.append(f"| coin flip (p=0.5) | {metrics['coin_flip']['brier']:.4f} | {metrics['coin_flip']['log_loss']:.4f} | "
                 f"Brier {'YES' if metrics['model_beats_coin_brier'] else 'no'}, LL {'YES' if metrics['model_beats_coin_log_loss'] else 'no'} |")
    lines.append(f"| home always (p=1, LL clipped at 1e-12) | {metrics['home_always']['brier']:.4f} | {metrics['home_always']['log_loss']:.4f} | "
                 f"Brier {'YES' if metrics['model_beats_home_brier'] else 'no'}, LL {'YES' if metrics['model_beats_home_log_loss'] else 'no'} |")
    lines.append("")
    totals = results["totals_metrics"]
    lines.append(f"- totals log-loss at the evaluated line: **{totals['model_log_loss']:.4f}** "
                 f"(coin 0.5 at the same lines: {totals['coin_log_loss']:.4f}); "
                 f"n = {totals['n']}, pushes excluded {totals['pushes_excluded']}, over rate {totals['over_rate']:.3f}")
    lines.append(f"- line sources: {totals['line_sources']} "
                 f"({'ESPN-captured DK closing total' if totals['line_sources'].get('dk_closing') else 'model median line fallback (labeled)'})")
    lines.append("")

    gate_b = results["gate_b"]
    lines.append("## Gate B — goal/points fit (xG analog)")
    lines.append("")
    lines.append(f"- Pearson r(exp_total, actual total) = {gate_b['pearson_exp_total_vs_actual']['r']:.4f} "
                 f"(p = {gate_b['pearson_exp_total_vs_actual']['p']:.2e}), Spearman rho = {gate_b['spearman_exp_total_vs_actual']['rho']:.4f}")
    lines.append(f"- Pearson r(exp_margin, actual margin) = {gate_b['pearson_exp_margin_vs_actual']['r']:.4f} (p = {gate_b['pearson_exp_margin_vs_actual']['p']:.2e})")
    lines.append(f"- mean |total error| {gate_b['mean_abs_total_error_pts']:.2f} pts, mean |margin error| {gate_b['mean_abs_margin_error_pts']:.2f} pts")
    lines.append(f"- bar: {gate_b['bar']}")
    lines.append(f"- **{gate_b['verdict']}**")
    lines.append("")

    gate_c = results["gate_c"]
    lines.append("## Gate C — rating sanity vs league table")
    lines.append("")
    lines.append(f"- Spearman rho(EWMA net rating, win%) = {gate_c['spearman_ewma_net_vs_win_pct']['rho']:.4f} (p = {gate_c['spearman_ewma_net_vs_win_pct']['p']:.2e})")
    lines.append(f"- Spearman rho(EWMA ORtg, win%) = {gate_c['spearman_ewma_ortg_vs_win_pct']['rho']:.4f}; "
                 f"rho(EWMA ORtg, actual net rtg) = {gate_c['spearman_ewma_ortg_vs_actual_net']:.4f}")
    lines.append(f"- bar: {gate_c['bar']}")
    lines.append(f"- **{gate_c['verdict']}**")
    lines.append("")

    lines.append("### ML reliability bins (walk-forward set)")
    lines.append("")
    lines.append("| p_home bin | n | predicted mean | actual rate |")
    lines.append("|---|---|---|---|")
    for bin_ in results["calibration_bins"]:
        lines.append(f"| {bin_['range']} | {bin_['n']} | "
                     f"{_fmt(bin_.get('predicted_mean'))} | {_fmt(bin_.get('actual_rate'))} |")
    lines.append("")

    market = results["market_dk"]
    wf = market["walk_forward_set"]
    wide = market["model_eligible_set_ge1"]
    lines.append("## Gate E — market comparison (DK closing devig)")
    lines.append("")
    lines.append(f"- {market['source_note']}")
    if wf["n"]:
        lines.append(f"- walk-forward set (n = {wf['n']}): **MAD {wf['mad']:.4f}** "
                     f"({100 * wf['mad']:.1f}c), median {wf['median_ad']:.4f}, p90 {wf['p90_ad']:.4f}, max {wf['max_ad']:.4f}; "
                     f"mean book vig {wf['mean_vig']:.4f}")
        lines.append(f"- favorite flips: {wf['favorite_flips']}/{wf['n']} (exact-0.5 ties {wf['exact_0p5_ties']})")
    if wide["n"]:
        lines.append(f"- wider model-eligible set (>=1 prior, n = {wide['n']}): MAD {wide['mad']:.4f} "
                     f"({100 * wide['mad']:.1f}c), flips {wide['favorite_flips']}/{wide['n']}")
    lines.append(f"- bar: MAD <= {GATE_E_MAX_MAD:.2f} (task wording; round-46 feasibility target 4-5c)")
    lines.append(f"- **{results['gates']['E']}** (DK number above; PM closing below)")
    lines.append("")

    pm = results["market_pm"]
    lines.append("### Polymarket CLOB closing comparison (mapped ML markets)")
    lines.append("")
    if pm["n_mapped"]:
        lines.append(f"- mapped: {pm['n_mapped']} moneyline markets; **PM-closing MAD vs model: {pm['mad']:.4f}** "
                     f"({100 * pm['mad']:.1f}c), median {pm['median_ad']:.4f}, max {pm['max_ad']:.4f}; "
                     f"flips {pm.get('favorite_flips_vs_pm')}/{pm['n_mapped']}")
        if "pm_vs_dk_mad" in pm:
            lines.append(f"- PM closing vs DK devig MAD: {pm['pm_vs_dk_mad']:.4f} (cross-book sanity)")
        lines.append("")
        lines.append("| date | game | PM close home | DK devig home | model p_home | |model-PM| | volume $ |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in sorted(pm["rows"], key=lambda r: r["date"]):
            lines.append(f"| {row['date']} | {row['game']} | {row['pm_p_home']:.3f} | "
                         f"{row.get('p_home_dk_devig', float('nan')):.3f} | {row['p_home_model']:.3f} | "
                         f"{row['abs_dev']:.3f} | {row['volume']:,.0f} |")
    else:
        lines.append("- no markets mapped" + (f": {pm['failures']}" if pm["failures"] else ""))
    lines.append("")

    audit = results["variant_audit"]
    lines.append("## Variant-spread audit (6-variant envelope, soccer bar 6c)")
    lines.append("")
    lines.append(f"- p_home spread: mean {audit['p_home']['mean']:.4f} ({100 * audit['p_home']['mean']:.1f}c), "
                 f"median {audit['p_home']['median']:.4f}, p90 {audit['p_home']['p90']:.4f}, max {audit['p_home']['max']:.4f}; "
                 f"**fraction > 6c: {audit['p_home']['fraction_over_6c']:.3f}**")
    lines.append(f"- totals-quote spread: mean {audit['totals_quote']['mean']:.4f} ({100 * audit['totals_quote']['mean']:.1f}c), "
                 f"max {audit['totals_quote']['max']:.4f}; fraction > 6c: {audit['totals_quote']['fraction_over_6c']:.3f}")
    lines.append(f"- exp_total spread (pts): mean {audit['exp_total_pts']['mean']:.2f}, max {audit['exp_total_pts']['max']:.2f}")
    lines.append(f"- spread driver: {audit['p_home_spread_driver']}")
    lines.append("")
    lines.append("| min-prior bucket | n | p_home mean spread | p_home >6c | totals mean spread | totals >6c |")
    lines.append("|---|---|---|---|---|---|")
    for bucket in audit["by_min_prior"]:
        if not bucket["p_home_n"]:
            lines.append(f"| {bucket['min_prior_bucket']} | 0 | — | — | — | — |")
            continue
        lines.append(f"| {bucket['min_prior_bucket']} | {bucket['p_home_n']} | "
                     f"{bucket['p_home_mean']:.4f} | {bucket['p_home_fraction_over_6c']:.3f} | "
                     f"{bucket['totals_mean']:.4f} | {bucket['totals_fraction_over_6c']:.3f} |")
    lines.append("")
    lines.append("| time window | dates | n | p_home mean | >6c | totals mean | >6c |")
    lines.append("|---|---|---|---|---|---|---|")
    for window in audit["by_time"]:
        lines.append(f"| {window['window']} | {window['dates']} | {window['n']} | "
                     f"{window['p_home_mean_spread']:.4f} | {window['p_home_fraction_over_6c']:.3f} | "
                     f"{window['totals_mean_spread']:.4f} | {window['totals_fraction_over_6c']:.3f} |")
    lines.append("")

    lines.append("## Gate table")
    lines.append("")
    lines.append("| gate | check | verdict | key numbers |")
    lines.append("|---|---|---|---|")
    for key, gate in results["gates_detail"].items():
        lines.append(f"| {key} | {gate['check']} | **{gate['verdict']}** | {gate['numbers']} |")
    lines.append("")
    lines.append("## Verdict notes (report only — promotion not decided here)")
    lines.append("")
    for note in results["verdict_notes"]:
        lines.append(f"- {note}")
    lines.append("")

    target = out_dir / "report.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="WP-NBA-3 NBA validation harness (report-only, paper-only)"
    )
    parser.add_argument("--snapshot", required=True, help="snapshot JSON path")
    parser.add_argument("--cache-dir", default=None, help="ESPN raw cache dir (DK odds + rebuild)")
    parser.add_argument("--out-dir", required=True, help="review output dir (report.md, results.json)")
    parser.add_argument("--min-prior-games", type=int, default=DEFAULT_MIN_PRIOR_GAMES)
    parser.add_argument("--pm-markets", type=int, default=10, help="Polymarket markets to map (recent first)")
    parser.add_argument("--skip-dk", action="store_true", help="no DK cache read (totals fall back to model median)")
    parser.add_argument("--skip-pm", action="store_true", help="skip the networked Polymarket part")
    parser.add_argument("--revision", default="1a2760bc (same commit on both hosts)")
    args = parser.parse_args(argv)

    snapshot_path = Path(args.snapshot)
    snapshot = espn_nba.load_nba_snapshot(str(snapshot_path))
    games = pair_snapshot_games(snapshot)

    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    dk: dict[tuple[str, str, str], dict] = {}
    dk_stats: dict = {"disabled": True}
    if cache_dir is not None and not args.skip_dk:
        dk, dk_stats = dk_odds_from_cache(cache_dir)

    # -- gate A
    gate_a = gate_a_integrity(snapshot_path, cache_dir, snapshot)

    # -- walk-forward (the big compute)
    records, info = walk_forward(snapshot, games, args.min_prior_games, dk)
    if not records:
        raise SystemExit(
            f"no walk-forward games with >= {args.min_prior_games} prior games for both teams; "
            "rerun with a lower --min-prior-games or a later snapshot"
        )
    metrics = ml_metrics(records)
    totals = totals_metrics(records)
    gate_b = gate_b_fit(records)
    gate_c = gate_c_sanity(snapshot)
    calibration = calibration_bins(records)
    audit = variant_audit(records)
    market = market_dk(records, games, snapshot, dk) if dk else {
        "walk_forward_set": {"n": 0},
        "model_eligible_set_ge1": {"n": 0},
        "source_note": "DK cache not read (--skip-dk or no cache)",
    }
    pm = (
        market_pm(records, snapshot, args.pm_markets)
        if not args.skip_pm
        else {"n_mapped": 0, "failures": [], "rows": [], "skipped": True}
    )

    # -- gate verdicts
    wf_market = market["walk_forward_set"]
    gate_d_pass = (
        metrics["model_beats_coin_brier"]
        and metrics["model_beats_coin_log_loss"]
        and metrics["model_beats_home_brier"]
        and metrics["model_beats_home_log_loss"]
    )
    if metrics["n"] < GATE_D_MIN_N:
        gate_d_verdict = "INSUFFICIENT-DATA"
    else:
        gate_d_verdict = "PASS" if gate_d_pass else "FAIL"
    dk_mad = wf_market.get("mad")
    if wf_market.get("n", 0) == 0:
        gate_e_verdict = "INSUFFICIENT-DATA"
    else:
        gate_e_verdict = "PASS" if (dk_mad is not None and dk_mad <= GATE_E_MAX_MAD) else "FAIL"
    gate_a["verdict"] = "PASS" if gate_a["passed"] else "FAIL"
    gate_b["verdict"] = (
        "PASS" if gate_b["passed"] else ("INSUFFICIENT-DATA" if gate_b["n"] < GATE_D_MIN_N else "FAIL")
    )
    gate_c["verdict"] = "PASS" if gate_c["passed"] else "FAIL"

    gates = {
        "A": gate_a["verdict"],
        "B": gate_b["verdict"],
        "C": gate_c["verdict"],
        "D": gate_d_verdict,
        "E": gate_e_verdict,
    }
    gates_detail = {
        "A": {
            "check": "data integrity (adapter-enforced; reload + cache rebuild)",
            "verdict": gates["A"],
            "numbers": f"{gate_a['teams']} teams, {gate_a['games']} games, rebuild-equal {gate_a.get('rebuild_from_cache_equal')}, poss 94-102 share {gate_a['team_poss']['share_in_94_102']:.3f}",
        },
        "B": {
            "check": "goal/points fit: exp_total vs actual totals correlation",
            "verdict": gates["B"],
            "numbers": f"r={gate_b['pearson_exp_total_vs_actual']['r']:.4f} (p={gate_b['pearson_exp_total_vs_actual']['p']:.1e}), rho={gate_b['spearman_exp_total_vs_actual']['rho']:.4f}, n={gate_b['n']}",
        },
        "C": {
            "check": "rating sanity: EWMA ORtg/net vs league-table order",
            "verdict": gates["C"],
            "numbers": f"rho(net,win%)={gate_c['spearman_ewma_net_vs_win_pct']['rho']:.4f}, rho(ORtg,win%)={gate_c['spearman_ewma_ortg_vs_win_pct']['rho']:.4f}, {gate_c['teams']} teams",
        },
        "D": {
            "check": f"walk-forward beats coin-flip AND home-always on BOTH Brier and log-loss (n>={GATE_D_MIN_N})",
            "verdict": gates["D"],
            "numbers": f"n={metrics['n']}: model Brier {metrics['model']['brier']:.4f} vs coin {metrics['coin_flip']['brier']:.4f}/home {metrics['home_always']['brier']:.4f}; LL {metrics['model']['log_loss']:.4f} vs {metrics['coin_flip']['log_loss']:.4f}/{metrics['home_always']['log_loss']:.4f}; totals LL {totals['model_log_loss']:.4f} vs coin {totals['coin_log_loss']:.4f}",
        },
        "E": {
            "check": f"market MAD <= {GATE_E_MAX_MAD:.2f} (DK closing devig; PM closing reported)",
            "verdict": gates["E"],
            "numbers": (
                f"DK MAD {dk_mad:.4f} ({100 * dk_mad:.1f}c) n={wf_market['n']}, flips {wf_market['favorite_flips']}/{wf_market['n']}"
                if wf_market.get("n")
                else "no DK coverage"
            )
            + (
                f"; PM closing MAD {pm['mad']:.4f} over {pm['n_mapped']} markets"
                if pm.get("n_mapped")
                else "; PM closing: not mapped"
            ),
        },
    }

    verdict_notes = [
        f"Walk-forward n = {metrics['n']} of {len(games)} snapshot games meet the >= {args.min_prior_games}-prior bar; "
        "every other gate number inherits this small-sample caveat.",
        f"Sigma walk: model used data-fit sigma on games whose truncated snapshot passed "
        f"MIN_RESIDUAL_GAMES={nba_model.MIN_RESIDUAL_GAMES} residuals; residual counts per prediction are in results.json.",
        f"Variant spread fraction > 6c: p_home {audit['p_home']['fraction_over_6c']:.3f}, totals {audit['totals_quote']['fraction_over_6c']:.3f}; "
        "early-season expectation is wide — recheck as games accumulate.",
        "Promotion is NOT decided by this harness: these are the coordinator's gate inputs.",
        "More data needed for a confident promotion decision: walk-forward n grows with each backfill; "
        "~4-6 more team-games per team (2 weeks) roughly triples the eligible set, and PM mapped-market MAD "
        "should be re-pulled on the larger set.",
    ]

    results = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "harness": "tools/wp_nba_validate.py (WP-NBA-3)",
            "revision": args.revision,
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": _sha256(snapshot_path),
            "season": snapshot["season"],
            "paper_only": True,
            "params": {
                "min_prior_games": args.min_prior_games,
                "pm_markets": args.pm_markets,
                "skip_dk": args.skip_dk,
                "skip_pm": args.skip_pm,
            },
        },
        "dk_cache_stats": dk_stats,
        "gate_a": gate_a,
        "walk_forward_info": info,
        "ml_metrics": metrics,
        "totals_metrics": totals,
        "gate_b": gate_b,
        "gate_c": gate_c,
        "calibration_bins": calibration,
        "variant_audit": audit,
        "market_dk": market,
        "market_pm": pm,
        "gates": gates,
        "gates_detail": gates_detail,
        "verdict_notes": verdict_notes,
        "walk_forward_records": records,
    }
    # keep results.json bounded: DK row detail stays, per-variant p_home stays
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_target = out_dir / "results.json"
    with open(json_target, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True, allow_nan=False)
    report_target = write_report(out_dir, results)

    print(f"WP-NBA-3 validation written: {report_target}")
    print(f"results: {json_target}")
    print(f"gates: {gates}")
    print(
        f"walk-forward n={metrics['n']}: Brier {metrics['model']['brier']:.4f} "
        f"(coin {metrics['coin_flip']['brier']:.4f}, home {metrics['home_always']['brier']:.4f}); "
        f"LL {metrics['model']['log_loss']:.4f} (coin {metrics['coin_flip']['log_loss']:.4f}, "
        f"home {metrics['home_always']['log_loss']:.4f})"
    )
    if wf_market.get("n"):
        print(f"DK MAD {wf_market['mad']:.4f} over n={wf_market['n']}; flips {wf_market['favorite_flips']}")
    if pm.get("n_mapped"):
        print(f"PM closing MAD {pm['mad']:.4f} over {pm['n_mapped']} markets")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
