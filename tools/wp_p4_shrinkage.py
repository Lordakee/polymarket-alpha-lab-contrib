"""P4-2: nested chronological sparse-team k study; research/shadow only.

The other estimator settings are fixed *before* outcomes are evaluated (120-day
half-life, ordinary-team prior8). This isolates sparse-team k; it does not tune
decay on the outer holdout. Every outer selection sees only inner predictions
whose fixtures are already in that outer fold's training history. No2024 xG is
available, so2025 teams are called sparse while <8 games are observed, never
claimed to be confirmed promoted teams. New-to-league means absent from the
observed previous-season roster, not independently verified promotion status.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K_GRID = (0, 4, 8, 12, 16, math.inf)
MIN_INNER_FIXTURES = 20
MIN_INNER_BLOCKS = 3
BOOTSTRAP_SEED = 20261107
STUDY_FIT_ITERATIONS = 1000


def k_label(k):
    return "inf" if math.isinf(k) else str(int(k))


def choose_k(rows, allowed_match_ids):
    """Select on prequential inner losses available in the outer training set."""
    inner = [r for r in rows if r["match_id"] in allowed_match_ids]
    blocks = {r["block"] for r in inner}
    if len(inner) < MIN_INNER_FIXTURES or len(blocks) < MIN_INNER_BLOCKS:
        return 8, {"status": "unvalidated_k8_cold_start", "n": len(inner), "blocks": len(blocks)}
    means = {k_label(k): sum(r["losses"][k_label(k)] for r in inner) / len(inner) for k in K_GRID}
    winner = min(K_GRID, key=lambda k: (means[k_label(k)], K_GRID.index(k)))
    return winner, {"status": "inner_selected", "n": len(inner), "blocks": len(blocks), "mean_log_loss": means}


def paired_block_ci(rows, candidate, reference="8", *, repeats=2000):
    """95% percentile interval for paired loss differences; resample matchweeks."""
    blocks = defaultdict(list)
    for row in rows:
        blocks[row["block"]].append(row["losses"][candidate] - row["losses"][reference])
    if not rows:
        return {"difference": None, "ci95": None, "blocks": 0, "n": 0}
    difference = sum(sum(v) for v in blocks.values()) / len(rows)
    if len(blocks) < 2:
        return {"difference": difference, "ci95": None, "blocks": len(blocks), "n": len(rows)}
    totals = [(sum(v), len(v)) for _, v in sorted(blocks.items())]
    rng = random.Random(BOOTSTRAP_SEED)
    draws = []
    for _ in range(repeats):
        sample = [totals[rng.randrange(len(totals))] for _ in totals]
        draws.append(sum(v[0] for v in sample) / sum(v[1] for v in sample))
    draws.sort()
    return {"difference": difference, "ci95": [draws[int(.025 * (repeats - 1))], draws[int(.975 * (repeats - 1))]], "blocks": len(blocks), "n": len(rows)}


def cohort(fold, match):
    """Training-only membership; neither final-season counts nor test outcomes."""
    prior = [m for m in fold.train if m.league == fold.league and int(m.season) == int(fold.season) - 1]
    prior_teams = {t for m in prior for t in (m.home_team, m.away_team)}
    counts = Counter(t for m in fold.train if m.league == fold.league and m.season == fold.season for t in (m.home_team, m.away_team))
    teams = (match.home_team, match.away_team)
    new = [t for t in teams if prior and t not in prior_teams]
    sparse = [t for t in teams if counts[t] < 8]
    return {"eligible": bool(new or sparse), "new_to_league": new, "sparse_under8": sparse,
            "prior_roster_available": bool(prior), "current_games": {t: counts[t] for t in teams}}


def summarize(rows):
    if not rows:
        return {"n": 0, "grid": {}, "descriptive_winner": None, "nested_log_loss": None}
    grid = {k_label(k): {"log_loss": sum(r["losses"][k_label(k)] for r in rows) / len(rows),
                       "paired_vs_k8": paired_block_ci(rows, k_label(k))} for k in K_GRID}
    winner = min(grid, key=lambda key: grid[key]["log_loss"])
    # Selection from these outer losses is descriptive ONLY, not a nested claim.
    return {"n": len(rows), "blocks": len({r["block"] for r in rows}), "grid": grid,
            "descriptive_winner": winner,
            "nested_log_loss": sum(r["losses"][r["selected_k"]] for r in rows) / len(rows),
            "nested_vs_k8": paired_block_ci(rows, "nested"),
            "selected_k_fixture_counts": dict(Counter(r["selected_k"] for r in rows)),
            "new_to_league_fixtures": sum(bool(r["cohort"]["new_to_league"]) for r in rows),
            "sparse_under8_fixtures": sum(bool(r["cohort"]["sparse_under8"]) for r in rows)}


def run_study(paper_sim_root):
    from tools.wp_p4_history import build_folds, load_history, to_model_history
    from polymarket_alpha_lab.papersim.recalib import Config, Fixture, fit

    audit = load_history(Path(paper_sim_root))
    all_folds, skipped = build_folds(audit)
    rows, selections, fitted = [], [], []
    for league in ("Eredivisie", "Championship"):
        league_rows = []
        folds = sorted((f for f in all_folds if f.league == league), key=lambda f: f.cutoff)
        for fold in folds:
            eligible = [(m, cohort(fold, m)) for m in fold.test]
            eligible = [(m, c) for m, c in eligible if c["eligible"]]
            if not eligible:
                continue
            selected, selection = choose_k(league_rows, {m.match_id for m in fold.train})
            block = f"{league}:{fold.season}:{fold.matchweek}"
            selection.update(league=league, season=fold.season, matchweek=fold.matchweek,
                             cutoff=fold.cutoff.isoformat(), selected_k=k_label(selected))
            selections.append(selection)
            history = to_model_history(fold)
            # Numerical convergence budget, not an outcome-selected parameter.
            # k0's unregularized early-season fits need more than80 iterations.
            estimators = {k_label(k): fit(history, config=replace(Config(fit_iterations=STUDY_FIT_ITERATIONS), sparse_prior_matches=k)) for k in K_GRID}
            for label, estimator in estimators.items():
                fitted.append({"block": block, "k": label,
                               "parameters": asdict(estimator.league_parameters[league])})
            for match, membership in eligible:
                fixture = Fixture(league=match.league, season=match.season, matchweek=match.matchweek,
                                  kickoff=match.kickoff, home_team=match.home_team, away_team=match.away_team)
                outcome = 0 if match.home_goals > match.away_goals else 1 if match.home_goals == match.away_goals else 2
                probabilities = {}
                for label, estimator in estimators.items():
                    p = estimator.predict(fixture)
                    probabilities[label] = [p.home_win, p.draw, p.away_win]
                row = {"match_id": match.match_id, "league": league, "season": fold.season,
                       "matchweek": fold.matchweek, "block": block, "cutoff": fold.cutoff.isoformat(),
                       "kickoff": match.kickoff.isoformat(), "home": match.home_team, "away": match.away_team,
                       "cohort": membership, "probabilities": probabilities,
                       "losses": {k: -math.log(max(v[outcome], 1e-15)) for k, v in probabilities.items()},
                       "selected_k": k_label(selected), "selection_status": selection["status"],
                       "role": "outer" if membership["prior_roster_available"] else "inner_warmup"}
                row["losses"]["nested"] = row["losses"][row["selected_k"]]
                league_rows.append(row)
                rows.append(row)
            print(f"P4-2 {block}: {len(eligible)} cohort fixtures, inner-selected k={k_label(selected)}", flush=True)
    outer = [r for r in rows if r["role"] == "outer"]
    pooled = summarize(outer)
    last_selection = {league: next((s for s in reversed(selections) if s["league"] == league), None)
                      for league in ("Eredivisie", "Championship")}
    per_league = {league: summarize([r for r in outer if r["league"] == league])
                  for league in ("Eredivisie", "Championship")}
    # Strong historical support requires pre-test selection and independent
    # outer superiority in both leagues. No claim of equivalence from wide CIs.
    holds = all(last_selection[league] is not None and
                last_selection[league]["status"] == "inner_selected" and
                last_selection[league]["selected_k"] == "8" and
                result["descriptive_winner"] == "8" and
                all(metric["paired_vs_k8"]["ci95"] is not None and
                    metric["paired_vs_k8"]["ci95"][0] > 0
                    for label, metric in result["grid"].items() if label != "8")
                for league, result in per_league.items())
    return {
        "study": "WP-P4/P4-2 shadow-only nested sparse-team shrinkage", "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_only": True, "report_only": True, "readonly": True,
        "protocol": {"grid": [k_label(k) for k in K_GRID], "half_life_days": 120, "ordinary_team_prior": 8,
                     "fit_iteration_limit": STUDY_FIT_ITERATIONS,
                     "cohort": "new-to-observed-prior-league-roster OR fewer than8 observed current-season games",
                     "minimum_inner_fixtures": MIN_INNER_FIXTURES, "minimum_inner_matchweeks": MIN_INNER_BLOCKS,
                     "cold_start": "k8 unvalidated candidate, never counted as a data-selected winner",
                     "selection": "min prior-fold out-of-time1X2 log-loss, only outcomes present in current outer training; ties grid order",
                     "outer": "season with observed prior roster; earlier no-prior season predictions serve inner sparse warmup",
                     "ci": "paired matchweek percentile bootstrap2000, seed20261107; exploratory, no multiplicity correction",
                     "availability": "retrospective event-time replay, kickoff+3h assumption; no as-observed xG guarantee"},
        "sources": audit.sources, "data_exclusions": audit.exclusions,
        "skipped_folds": [s for s in skipped if s.get("league") in ("Eredivisie", "Championship")],
        "inner_warmup_n": len(rows) - len(outer), "outer": pooled,
        "per_league": per_league,
        "last_training_only_selection": last_selection, "selections": selections, "predictions": rows,
        "fits": fitted, "nonconverged_fits": [f for f in fitted if not f["parameters"]["converged"]],
        "k8_holds": holds,
        "k8_verdict": ("k8 has historical support under the predeclared exploratory criterion; production promotion still requires prospective gates."
                       if holds else "k8 is not established: it did not satisfy training-only selection and positive paired superiority over every alternative in both outer league cohorts. Wide intervals cannot establish equivalence."),
        "promotion": "No production promotion. Preserve section73 and prospective >=2 complete matchweeks plus predeclared sample and A-E gates.",
    }


def markdown(report):
    lines = ["# WP-P4/P4-2 sparse-team k study — SHADOW ONLY", "",
             "Every nested selection uses earlier out-of-time predictions whose outcomes are already in the outer training history. "
             "The fixed-grid holdout winner below is descriptive; it is not an independently validated final k.", "",
             "| League | Outer fixtures | Matchweeks | Nested selected LL | Descriptive k |", "|---|---:|---:|---:|---|"]
    for league, result in report["per_league"].items():
        ll = result["nested_log_loss"]
        lines.append(f"| {league} | {result['n']} | {result.get('blocks', 0)} | {ll:.6f} | {result['descriptive_winner']} |" if ll is not None else f"| {league} | 0 | 0 | unavailable | unavailable |")
    lines += ["", "| Cohort | k | Outer LL | LL difference vs k8 | Paired95% CI |", "|---|---:|---:|---:|---|"]
    for league, result in {**report["per_league"], "Pooled": report["outer"]}.items():
        for k, metric in result["grid"].items():
            ci = metric["paired_vs_k8"]
            bounds = "unavailable" if ci["ci95"] is None else f"[{ci['ci95'][0]:.6f}, {ci['ci95'][1]:.6f}]"
            lines.append(f"| {league} | {k} | {metric['log_loss']:.6f} | {ci['difference']:.6f} | {bounds} |")
    lines += ["", f"Inner sparse warmup: {report['inner_warmup_n']} fixtures. Neither league has a2024 xG prior;2025 promotion labels cannot be established from these data.",
              "", f"Numerical fits: {len(report['fits'])}; nonconverged: {len(report['nonconverged_fits'])}. The iteration limit is{STUDY_FIT_ITERATIONS}, held constant for every candidate.",
              "", "Final selections using training data only:"]
    for league, selection in report["last_training_only_selection"].items():
        if selection:
            lines.append(f"- {league}: k={selection['selected_k']} before {selection['season']} round{selection['matchweek']}, inner n={selection['n']} across{selection['blocks']} matchweeks.")
    lines += ["", "Intervals resample whole matchweeks, retaining fixture pairing. Few blocks, shared teams, season dependence, multiple candidates and multiple leagues make these exploratory intervals; they do not establish equivalence or significance after selection.",
              "", report["k8_verdict"], "", report["promotion"], ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-sim-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.paper_sim_root.resolve()
    json_out, markdown_out = args.output_json.resolve(), args.output_markdown.resolve()
    if json_out == markdown_out or any(p.is_relative_to(root) for p in (json_out, markdown_out)):
        parser.error("output files must differ and must be outside the read-only input archive")
    report = run_study(root)
    json_text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    markdown_text = markdown(report)
    for path in (json_out, markdown_out):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json_text)
    markdown_out.write_text(markdown_text)


if __name__ == "__main__":
    main()
