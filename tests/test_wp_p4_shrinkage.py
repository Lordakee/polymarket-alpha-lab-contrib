"""Chronology and uncertainty checks for the shadow k-selection study."""
import math
from types import SimpleNamespace

import pytest

from tools.wp_p4_shrinkage import choose_k, cohort, k_label, paired_block_ci, summarize


def rows(n=24):
    return [{"match_id": str(i), "block": str(i // 4),
             "losses": {k_label(k): 1.0 + abs(k - 4) / 100 if not math.isinf(k) else 2.0
                        for k in (0, 4, 8, 12, 16, math.inf)}} for i in range(n)]


def test_inner_selection_never_uses_outer_or_future_outcomes():
    past = rows()
    future = {"match_id": "future", "block": "future", "losses": {str(k): -1000.0 if k == 16 else 1000.0 for k in (0, 4, 8, 12, 16)}}
    future["losses"]["inf"] = 1000.0
    selected, evidence = choose_k(past + [future], {r["match_id"] for r in past})
    assert selected == 4
    assert evidence["n"] == 24
    assert evidence["mean_log_loss"]["4"] == 1.0


def test_insufficient_inner_sample_reports_unvalidated_fallback():
    selected, evidence = choose_k(rows(5), {str(i) for i in range(5)})
    assert selected == 8
    assert evidence["status"] == "unvalidated_k8_cold_start"


def test_paired_interval_retains_constant_model_difference():
    result = paired_block_ci(rows(), "4", repeats=100)
    assert math.isclose(result["difference"], -.04)
    assert all(math.isclose(v, -.04) for v in result["ci95"])
    assert result["blocks"] == 6


def test_one_block_cannot_claim_confidence_interval():
    result = paired_block_ci(rows(4), "4", repeats=100)
    assert result["ci95"] is None


def test_empty_study_has_no_fabricated_winner():
    assert summarize([])["descriptive_winner"] is None


def test_no_prior_roster_is_not_proof_of_promotion():
    games = [SimpleNamespace(league="L", season="2025", home_team="A", away_team="B") for _ in range(8)]
    fold = SimpleNamespace(train=games, league="L", season="2025")
    result = cohort(fold, SimpleNamespace(home_team="A", away_team="B"))
    assert not result["eligible"]
    assert not result["prior_roster_available"]
    assert result["new_to_league"] == []


def test_new_to_observed_prior_roster_remains_cohort_after_eight_matches():
    games = [SimpleNamespace(league="L", season="2025", home_team="A", away_team="B")]
    games += [SimpleNamespace(league="L", season="2026", home_team="C", away_team="B") for _ in range(8)]
    fold = SimpleNamespace(train=games, league="L", season="2026")
    result = cohort(fold, SimpleNamespace(home_team="C", away_team="B"))
    assert result["eligible"]
    assert result["new_to_league"] == ["C"]
    assert result["sparse_under8"] == []


@pytest.mark.parametrize("case", ["input", "same", "symlink"])
def test_cli_refuses_archive_overwrite_or_identical_outputs_before_loading(tmp_path, monkeypatch, case):
    from tools import wp_p4_shrinkage as study
    archive = tmp_path / "archive"
    archive.mkdir()
    source = archive / "understat_latest.json"
    source.write_text("untouched historical input")
    json_out = tmp_path / "result.json"
    md_out = tmp_path / "result.md"
    if case == "input":
        json_out = source
    elif case == "same":
        md_out = json_out
    else:
        json_out.symlink_to(source)
    calls = []
    monkeypatch.setattr(study, "run_study", lambda root: calls.append(root))
    with pytest.raises(SystemExit) as error:
        study.main(["--paper-sim-root", str(archive), "--output-json", str(json_out),
                    "--output-markdown", str(md_out)])
    assert error.value.code == 2
    assert calls == []
    assert source.read_text() == "untouched historical input"
    assert not md_out.exists()
