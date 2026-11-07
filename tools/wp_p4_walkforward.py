"""WP-P4 T3: offline, chronological shadow comparison with nested tuning.

No network, database, order, or production-configuration writes. JSON and Markdown
are emitted only to explicit caller-selected paths. Run with PYTHONPATH=src:tools.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import timedelta
import json
import math
from pathlib import Path
import random
import statistics
import sys

if not __package__:
    # Optional sibling tools also use the tools namespace when run directly.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from .wp_p4_history import (LEAGUES, Fold, HistoryAudit, build_folds, inventory, iso,
                               load_history, production_snapshot, to_model_history)
except ImportError:  # Direct script invocation.
    from wp_p4_history import (LEAGUES, Fold, HistoryAudit, build_folds, inventory, iso,
                              load_history, production_snapshot, to_model_history)

HALF_LIVES = (60.0, 120.0, 240.0)
TEAM_PRIORS = (4.0, 8.0, 16.0)
TOTAL_LINES = (1.5, 2.5, 3.5)
EPSILON = 1e-12


def model_fixture(match):
    from polymarket_alpha_lab.papersim.recalib import Fixture
    return Fixture(league=match.league, season=match.season, matchweek=match.matchweek,
                   kickoff=match.kickoff, home_team=match.home_team, away_team=match.away_team)


def score_forecast(probabilities, totals, home_goals: int, away_goals: int) -> dict:
    """Normalize categorical medians for scoring only, and retain raw sensitivity."""
    raw = tuple(float(p) for p in probabilities)
    if len(raw) != 3 or any(not math.isfinite(p) or p < 0 or p > 1 for p in raw):
        raise ValueError("three finite probabilities required")
    total = sum(raw)
    if total <= 0:
        raise ValueError("categorical probability mass must be positive")
    normalized = tuple(p / total for p in raw)
    outcome = 0 if home_goals > away_goals else 1 if home_goals == away_goals else 2
    target = tuple(float(i == outcome) for i in range(3))
    line_losses = {}
    for line in TOTAL_LINES:
        probability = float(totals[line])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("totals probabilities must be finite and within [0, 1]")
        realized = home_goals + away_goals > line
        line_losses[str(line)] = -math.log(max(EPSILON, probability if realized else 1 - probability))
    return {
        "raw_1x2": raw, "raw_1x2_sum": total, "scoring_1x2": normalized,
        "brier_1x2": sum((p - y) ** 2 for p, y in zip(normalized, target)),
        "logloss_1x2": -math.log(max(EPSILON, normalized[outcome])),
        "raw_median_brier_1x2": sum((p - y) ** 2 for p, y in zip(raw, target)),
        "raw_median_logloss_1x2": -math.log(max(EPSILON, raw[outcome])),
        "totals_probabilities": {str(line): totals[line] for line in TOTAL_LINES},
        "totals_logloss_by_line": line_losses,
        "totals_logloss": statistics.fmean(line_losses.values()),
    }


def _prediction_loss(prediction, match) -> dict:
    return score_forecast((prediction.home_win, prediction.draw, prediction.away_win),
                          {line: prediction.over_probability(line) for line in TOTAL_LINES},
                          match.home_goals, match.away_goals)


def select_config(audit: HistoryAudit, fold: Fold, *, cache: dict | None = None,
                  half_lives=HALF_LIVES, team_priors=TEAM_PRIORS,
                  min_inner_folds: int = 2, folds: tuple[Fold, ...] | None = None):
    """Select on earlier held-out 1X2 loss wholly inside this outer training set.

    Fixed before seeing results: 60/120/240-day decay x 4/8/16-match shrinkage,
    1X2 log loss objective, deterministic grid-order ties, 120/8 fallback until
    two inner folds exist. Totals and the outer cohort never select parameters.
    """
    from polymarket_alpha_lab.papersim.recalib import Config, fit
    if cache is None:
        cache = {}
    if folds is None:
        folds, _ = build_folds(audit, league=fold.league,
                                completion_lag_hours=fold.completion_lag_hours)
    outer_ids = {m.match_id for m in fold.train}
    lag = timedelta(hours=fold.completion_lag_hours)
    inner = [f for f in folds if f.league == fold.league and f.cutoff < fold.cutoff
             and f.test and {m.match_id for m in (*f.train, *f.test)} <= outer_ids
             and all(m.kickoff + lag < fold.cutoff for m in f.test)]
    common = {
        "objective": "mean_inner_1x2_logloss", "tie_break": "declared_grid_order",
        "inner_blocks": [f.block_id for f in inner],
        "inner_fixture_ids": [m.match_id for f in inner for m in f.test],
        "inner_fold_count": len(inner), "inner_fixture_count": sum(len(f.test) for f in inner),
        "selected_at_event_cutoff": iso(fold.cutoff),
        "latest_inner_result_kickoff": iso(max(m.kickoff for f in inner for m in f.test)) if inner else None,
        "selection_is_retrospective_event_time_replay": True,
    }
    if len(inner) < min_inner_folds:
        config = Config(half_life_days=120.0, team_prior_matches=8.0,
                        completion_lag_hours=fold.completion_lag_hours)
        return config, {**common, "status": "fixed_predeclared_fallback_insufficient_inner_folds",
                        "config": asdict(config), "candidate_scores": []}
    scores = []
    for half_life in half_lives:
        for prior in team_priors:
            config = Config(half_life_days=half_life, team_prior_matches=prior,
                            completion_lag_hours=fold.completion_lag_hours)
            losses = []
            nonconverged = []
            for inner_fold in inner:
                key = (inner_fold.block_id, iso(inner_fold.cutoff),
                       tuple(m.match_id for m in inner_fold.train), half_life, prior,
                       fold.completion_lag_hours)
                if key not in cache:
                    estimator = fit(to_model_history(inner_fold), config=config)
                    cache[key] = {
                        "losses": tuple(_prediction_loss(estimator.predict(model_fixture(m)), m)["logloss_1x2"]
                                        for m in inner_fold.test),
                        "converged": estimator.league_parameters[inner_fold.league].converged,
                    }
                losses.extend(cache[key]["losses"])
                if not cache[key]["converged"]:
                    nonconverged.append(inner_fold.block_id)
            scores.append({"half_life_days": half_life, "team_prior_matches": prior,
                           "mean_inner_1x2_logloss": statistics.fmean(losses), "n": len(losses),
                           "eligible": not nonconverged, "nonconverged_inner_blocks": nonconverged})
    eligible = [score for score in scores if score["eligible"]]
    if not eligible:
        config = Config(half_life_days=120.0, team_prior_matches=8.0,
                        completion_lag_hours=fold.completion_lag_hours)
        return config, {**common, "status": "fixed_fallback_no_fully_converged_candidate",
                        "config": asdict(config), "candidate_scores": scores}
    winner = min(eligible, key=lambda s: s["mean_inner_1x2_logloss"])
    config = Config(half_life_days=winner["half_life_days"], team_prior_matches=winner["team_prior_matches"],
                    completion_lag_hours=fold.completion_lag_hours)
    return config, {**common, "status": "nested_training_only_selection", "config": asdict(config),
                    "candidate_scores": scores}


def evaluate_fold(audit: HistoryAudit, fold: Fold, config) -> list[dict]:
    from polymarket_alpha_lab.papersim.recalib import fit
    from polymarket_alpha_lab.papersim.soccer_model import fixture_variants, median, over_probability, variant_outputs
    estimator = fit(to_model_history(fold), config=config)
    snapshot = production_snapshot(audit, fold)
    avg_home = statistics.fmean(m.home_xg for m in fold.train)
    avg_away = statistics.fmean(m.away_xg for m in fold.train)
    average = variant_outputs(avg_home, avg_away, rho=0.0)
    result = []
    for match in fold.test:
        prediction = estimator.predict(model_fixture(match))
        forecasts = {
            "recalibrated": {**_prediction_loss(prediction, match),
                             "lambda_home": prediction.lambda_home, "lambda_away": prediction.lambda_away,
                             "rho": prediction.rho,
                             "fitted_parameters": {**asdict(prediction.parameters),
                                                    "as_of": iso(prediction.parameters.as_of)}},
            "league_average_lambda": score_forecast(
                (average.home_win, average.draw, average.away_win),
                {line: over_probability(average, line) for line in TOTAL_LINES},
                match.home_goals, match.away_goals),
        }
        if snapshot is not None:
            variants = fixture_variants(snapshot, match.home_team, match.league,
                                        match.away_team, match.league, season=match.season)
            if variants is None or len(variants) != 10:
                raise ValueError(f"expected all frozen production variants: {match.match_id}")
            raw = tuple(median([getattr(v.outputs, name) for v in variants])
                        for name in ("home_win", "draw", "away_win"))
            forecasts["production10"] = {
                **score_forecast(raw, {line: median([over_probability(v.outputs, line) for v in variants])
                                      for line in TOTAL_LINES}, match.home_goals, match.away_goals),
                "variant_count": 10,
                "lambda_home": median([v.lambdas[0] for v in variants]),
                "lambda_away": median([v.lambdas[1] for v in variants]),
            }
        result.append({"match_id": match.match_id, "league": match.league, "season": match.season,
                       "matchweek": match.matchweek, "block_id": fold.block_id,
                       "cutoff": iso(fold.cutoff), "kickoff": iso(match.kickoff),
                       "source_kickoff": iso(match.source_kickoff or match.kickoff),
                       "home_team": match.home_team, "away_team": match.away_team,
                       "home_goals": match.home_goals, "away_goals": match.away_goals,
                       "training_matches": len(fold.train), "forecasts": forecasts,
                       "production_unsupported_reason": None if snapshot is not None else "missing_complete_actual_prior_season"})
    return result


def paired_block_interval(rows: list[dict], left: str, right: str, metric: str,
                          *, repetitions: int = 2000, seed: int = 20261107) -> dict:
    """Paired whole-matchweek resampling; three totals lines stay with their match."""
    blocks = defaultdict(list)
    for row in rows:
        forecasts = row["forecasts"]
        if left in forecasts and right in forecasts:
            blocks[row["block_id"]].append(forecasts[left][metric] - forecasts[right][metric])
    paired = [value for block in blocks.values() for value in block]
    if not paired:
        return {"n_fixtures": 0, "n_blocks": 0, "mean_delta": None, "ci95": None, "conclusion": "no_paired_observations"}
    mean = statistics.fmean(paired)
    if len(blocks) < 2:
        return {"n_fixtures": len(paired), "n_blocks": len(blocks), "mean_delta": mean,
                "ci95": None, "conclusion": "insufficient_independent_blocks"}
    if repetitions < 100:
        raise ValueError("at least 100 bootstrap repetitions required")
    rng, group = random.Random(seed), [blocks[key] for key in sorted(blocks)]
    draws = []
    for _ in range(repetitions):
        selected = [group[rng.randrange(len(group))] for _ in group]
        draws.append(sum(sum(block) for block in selected) / sum(len(block) for block in selected))
    draws.sort()
    lo, hi = draws[int(.025 * (repetitions - 1))], draws[int(.975 * (repetitions - 1))]
    return {"n_fixtures": len(paired), "n_blocks": len(blocks), "mean_delta": mean,
            "ci95": [lo, hi], "bootstrap_repetitions": repetitions,
            "conclusion": "lower_loss_supported_descriptively" if hi < 0 else
                          "higher_loss_supported_descriptively" if lo > 0 else "difference_within_resampling_noise",
            "small_block_sample": len(blocks) < 10,
            "limitations": "Matchweek bootstrap is descriptive: few seasons, serial dependence, selection and multiple comparisons prevent promotion claims."}


def summarize(rows: list[dict], *, repetitions: int = 2000) -> dict:
    summaries = {}
    for label, sub in [("ALL", rows)] + [(lg, [r for r in rows if r["league"] == lg]) for lg in LEAGUES]:
        models = {}
        for name in ("production10", "recalibrated", "league_average_lambda"):
            fs = [r["forecasts"][name] for r in sub if name in r["forecasts"]]
            models[name] = {"n_fixtures": len(fs), "n_totals_line_observations": len(fs) * len(TOTAL_LINES),
                            **{metric: statistics.fmean(f[metric] for f in fs) if fs else None
                               for metric in ("brier_1x2", "logloss_1x2", "totals_logloss",
                                              "raw_median_brier_1x2", "raw_median_logloss_1x2")}}
        differences = {}
        for comparator in ("production10", "league_average_lambda"):
            differences[comparator] = {metric: paired_block_interval(sub, "recalibrated", comparator, metric,
                                                                      repetitions=repetitions)
                                       for metric in ("brier_1x2", "logloss_1x2", "totals_logloss")}
        sums = [r["forecasts"]["production10"]["raw_1x2_sum"] for r in sub if "production10" in r["forecasts"]]
        summaries[label] = {"models": models, "paired_recalibrated_minus_comparator": differences,
                            "production_raw_probability_sum_range": [min(sums), max(sums)] if sums else None,
                            "production_unsupported_fixtures": sum("production10" not in r["forecasts"] for r in sub)}
    return summaries


def run(audit: HistoryAudit, *, repetitions: int = 2000, progress=None) -> dict:
    folds, skipped = build_folds(audit)
    rows, configs, cache = [], [], {}
    for index, fold in enumerate(folds):
        config, selection = select_config(audit, fold, cache=cache, folds=folds)
        rows.extend(evaluate_fold(audit, fold, config))
        configs.append({"block_id": fold.block_id, "league": fold.league, "season": fold.season,
                        "matchweek": fold.matchweek, "cutoff": iso(fold.cutoff), **selection})
        if progress:
            progress(index + 1, len(folds), fold)
    return {
        "study": "WP-P4 T3 shadow-only expanding-window replay", "paper_only": True,
        "report_only": True, "readonly": True, "production_policy_changed": False,
        "protocol": {"information_mode": "event_time_replay", "completion_lag_hours": 3,
                     "rounds": "train complete official prefix 1..k; predict full official round k+1 before earliest source kickoff",
                     "prior_seasons": "only actual complete seasons; no fabricated prior block",
                     "half_life_grid_days": HALF_LIVES, "team_prior_grid_matches": TEAM_PRIORS,
                     "selection": "nested prior 1X2 logloss; 120/8 predeclared fallback below two inner folds",
                     "baseline": "Poisson lambda from mean home/away xG over identical permitted expanding training rows; rho=0",
                     "production": "unchanged ten variants, raw per-outcome medians retained; renormalization only for categorical scoring",
                     "totals_lines": TOTAL_LINES, "totals_aggregation": "equal-weight per-fixture mean of three binary log losses",
                     "probability_log_floor": EPSILON, "bootstrap_unit": "league-season-official-matchweek",
                     "promotion_status": "not certified; prospective two complete matchweeks and predeclared out-of-time evidence remain required"},
        "sources": list(audit.sources), "source_notes": list(audit.notes), "exclusions": list(audit.exclusions),
        "inventory": inventory(audit), "skipped_folds": list(skipped), "fold_configs": configs,
        "fixture_predictions": rows, "summary": summarize(rows, repetitions=repetitions),
        "gate_e": {"status": "not_evaluated_in_T3", "reason": "separate timestamp-qualified market archive evaluation required"},
    }


def markdown(report: dict) -> str:
    lines = ["# WP-P4 T3 shadow walk-forward", "",
             "Retrospective event-time replay; no production acceptance, sizing, or threshold change.", "",
             "Official complete prefixes only. A three-hour result-completion assumption is used; original xG publication/revision timestamps are unavailable.", "",
             "The unchanged ten-variant median is retained raw. Categorical scores normalize its three medians solely to form a proper probability vector; raw-score sensitivity is in JSON. Totals average three lines (1.5, 2.5, 3.5) per fixture.", "",
             "| League | Model | Fixtures | 1X2 Brier | 1X2 log loss | Totals log loss |",
             "|---|---|---:|---:|---:|---:|"]
    for league, summary in report["summary"].items():
        for model, row in summary["models"].items():
            vals = ["n/a" if row[key] is None else f"{row[key]:.6f}" for key in ("brier_1x2", "logloss_1x2", "totals_logloss")]
            lines.append(f"| {league} | {model} | {row['n_fixtures']} | {' | '.join(vals)} |")
    lines += ["", "Rows from unsupported production seasons remain in the shadow/baseline summaries. Every reported paired delta uses exactly the same fixtures.", "",
              "| League | Comparator | 1X2 log-loss delta (shadow minus comparator) | 95% block interval | Paired fixtures / blocks |",
              "|---|---|---:|---|---:|"]
    for league, summary in report["summary"].items():
        for comp, metrics in summary["paired_recalibrated_minus_comparator"].items():
            cell = metrics["logloss_1x2"]
            mean = "n/a" if cell["mean_delta"] is None else f"{cell['mean_delta']:.6f}"
            ci = "n/a" if cell["ci95"] is None else f"[{cell['ci95'][0]:.6f}, {cell['ci95'][1]:.6f}]"
            lines.append(f"| {league} | {comp} | {mean} | {ci} | {cell['n_fixtures']} / {cell['n_blocks']} |")
    lines += ["", "Intervals are descriptive and do not eliminate serial dependence, small-season or multiple-comparison uncertainty. Per-fixture losses, block IDs, tuning cohorts, exclusions, skipped rounds and SHA256/byte source manifests are in the companion JSON.", "", "## Data limitations", ""]
    lines += ["- " + note for note in report["source_notes"]]
    lines += ["", "Quarantined source rows:", ""]
    lines += ["- " + json.dumps(row, sort_keys=True, ensure_ascii=False) for row in report["exclusions"]]
    lines += ["", "No Gate-E pass is asserted by this outcome-scoring harness. The market archive study is separate; prospective shadow evidence remains outstanding.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--include-market", action="store_true",
                        help="also run the descriptive archived scan-time MAD study; does not certify Gate E")
    args = parser.parse_args(argv)
    root = args.input_root.resolve()
    outputs = [args.json_out.resolve(), args.md_out.resolve()]
    if outputs[0] == outputs[1] or any(path.is_relative_to(root) for path in outputs):
        parser.error("output files must differ and must be outside the read-only input archive")
    if any(not path.parent.is_dir() for path in outputs):
        parser.error("create the explicit output parent directories before running")
    audit = load_history(root)
    report = run(audit, repetitions=args.bootstrap_repetitions,
                 progress=lambda n, total, fold: print(f"{n}/{total} {fold.block_id}", flush=True))
    if args.include_market:
        try:
            from .wp_p4_market import (archive_snapshot_availability, evaluate_market_mad,
                                       fixed_shadow_predictor, load_market_archive)
        except ImportError:
            from wp_p4_market import (archive_snapshot_availability, evaluate_market_mad,
                                      fixed_shadow_predictor, load_market_archive)
        market = load_market_archive(root)
        predictor = fixed_shadow_predictor(audit, archive_snapshot_availability(audit, root))
        report["archived_market_mad"] = {
            "midpoint": evaluate_market_mad(market, predictor),
            "ask": evaluate_market_mad(market, predictor, quote_kind="ask"),
            "configuration_note": "Separate predeclared fixed120day/8match shadow diagnostic; not the adaptively tuned T3 model, not formal Gate E certification.",
        }
    # Serialize both before the first write; malformed/nonfinite outputs fail closed.
    json_text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    md_text = markdown(report)
    args.json_out.write_text(json_text, encoding="utf-8")
    args.md_out.write_text(md_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
