"""Chronology and source-integrity tests for the explicitly offline WP-P4 study."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from tools import wp_p4_history as history

UTC = timezone.utc


@pytest.fixture
def mini_audit(monkeypatch):
    """A declared synthetic four-club double round robin, never research evidence."""
    monkeypatch.setitem(history.LEAGUES, "EPL", (47, 4, 6))
    pairs = [(('A', 'B'), ('C', 'D')), (('A', 'C'), ('D', 'B')),
             (('A', 'D'), ('B', 'C')), (('B', 'A'), ('D', 'C')),
             (('C', 'A'), ('B', 'D')), (('D', 'A'), ('C', 'B'))]
    matches, schedule, roster = [], [], []
    for season in ("2025", "2026"):
        roster.extend(("EPL", season, team, team) for team in "ABCD")
        for rnd, round_pairs in enumerate(pairs, 1):
            if season == "2026" and rnd > 4:
                continue
            kickoff = datetime(int(season), 8, 1, 12, tzinfo=UTC) + timedelta(days=7 * (rnd - 1))
            for home, away in round_pairs:
                mid = f"{season}-{rnd}-{home}"
                match = history.HistoricalMatch(mid, "EPL", season, None if season == "2025" else rnd,
                    kickoff, home, away, 1.3, 1.1, 1, 0, source_match_id=mid,
                    schedule_match_id=mid if season == "2026" else None, source_kickoff=kickoff)
                matches.append(match)
                if season == "2026":
                    schedule.append(history.ScheduleFixture(mid, "EPL", season, rnd, kickoff,
                        home, away, True, False, False, "1 - 0"))
    return history.HistoryAudit(tuple(matches), tuple(schedule), (), (), tuple(roster))


def test_complete_prefix_never_includes_target_or_later_round(mini_audit):
    folds, _ = history.build_folds(mini_audit)
    assert [fold.matchweek for fold in folds] == [3, 4]
    first = folds[0]
    assert len(first.train) == 12 + 4
    assert {m.matchweek for m in first.train if m.season == "2026"} == {1, 2}
    assert {m.match_id for m in first.train}.isdisjoint(m.match_id for m in first.test)
    assert ("EPL", "2025", None) in first.completed_matchweeks
    assert all(m.kickoff + timedelta(hours=3) < first.cutoff for m in first.train)


def test_postponed_old_round_blocks_prefix_even_with_finished_flag(mini_audit):
    future = datetime(2026, 9, 20, tzinfo=UTC)
    target = next(m for m in mini_audit.matches if m.season == "2026" and m.matchweek == 1)
    changed = replace(mini_audit,
        matches=tuple(replace(m, kickoff=future) if m.match_id == target.match_id else m for m in mini_audit.matches),
        schedule=tuple(replace(m, kickoff=future) if m.fixture_id == target.match_id else m for m in mini_audit.schedule))
    folds, skips = history.build_folds(changed)
    assert not folds
    assert all(s["reason"] == "prior_round_prefix_incomplete_at_cutoff" for s in skips if "matchweek" in s)


def test_partial_target_and_missing_schedule_fixture_do_not_pass(mini_audit):
    removed = next(m for m in mini_audit.matches if m.season == "2026" and m.matchweek == 3)
    changed = replace(mini_audit, matches=tuple(m for m in mini_audit.matches if m != removed))
    folds, skips = history.build_folds(changed)
    assert not folds
    assert any(s.get("matchweek") == 3 and s["reason"] == "target_round_incomplete" for s in skips)
    assert any(s.get("matchweek") == 4 and s["reason"] == "prior_round_prefix_incomplete_at_cutoff" for s in skips)


def test_production_rebuild_contains_each_allowed_match_once_and_no_fake_prior(mini_audit):
    fold = history.build_folds(mini_audit)[0][0]
    snapshot = history.production_snapshot(mini_audit, fold)
    assert set(snapshot) == {"EPL_2025", "EPL_2026"}
    assert len(snapshot["EPL_2025"]["dates"]) == 12
    assert len(snapshot["EPL_2026"]["dates"]) == 4
    assert sum(len(t["history"]) for t in snapshot["EPL_2026"]["teams"].values()) == 8
    no_prior = replace(fold, train=tuple(m for m in fold.train if m.season == "2026"))
    assert history.production_snapshot(mini_audit, no_prior) is None


def normalized_row(mid="old", home="A", away="B", when="2025-09-20 14:00:00"):
    return {"id": mid, "isResult": True, "h": {"title": home}, "a": {"title": away},
            "datetime": when, "goals": {"h": "1", "a": "0"}, "xG": {"h": "1.2", "a": "0.7"}}


def test_abandoned_result_is_excluded_while_replay_is_retained():
    old = history.ScheduleFixture("old", "Championship", "2025", 6,
        history.utc("2025-09-20T14:00:00Z"), "A", "B", True, True, False, "1 - 0")
    replay = replace(old, fixture_id="new", kickoff=history.utc("2025-12-02T19:45:00Z"), cancelled=False)
    rows, excluded = history.parse_matches({"dates": [normalized_row(),
        normalized_row("new", when="2025-12-02 19:45:00")]}, "Championship", "2025", (old, replay))
    assert [row.source_match_id for row in rows] == ["new"]
    assert excluded[0]["source_match_id"] == "old"


def test_opposite_home_orientation_is_quarantined_not_silently_swapped():
    official = history.ScheduleFixture("other-provider", "Ligue_1", "2025", 1,
        history.utc("2025-09-20T14:00:00Z"), "B", "A", True, False, False, "1 - 0")
    rows, excluded = history.parse_matches({"dates": [normalized_row()]}, "Ligue_1", "2025", (official,))
    assert rows == ()
    assert excluded[0]["reason"] == "official_identity_or_time_conflict"


def test_time_reconciliation_preserves_source_and_uses_later_completion_clock():
    official = history.ScheduleFixture("other-provider", "Serie_A", "2025", 1,
        history.utc("2025-09-20T14:05:00Z"), "A", "B", True, False, False, "1 - 0")
    rows, _ = history.parse_matches({"dates": [normalized_row()]}, "Serie_A", "2025", (official,))
    assert rows[0].source_kickoff == history.utc("2025-09-20T14:00:00Z")
    assert rows[0].kickoff == official.kickoff
    assert rows[0].available_at is None


def test_earlier_source_target_time_controls_freeze(mini_audit):
    earlier = datetime(2026, 8, 14, 12, tzinfo=UTC)
    changed = replace(mini_audit, matches=tuple(replace(m, source_kickoff=earlier)
        if m.season == "2026" and m.matchweek == 3 else m for m in mini_audit.matches))
    folds, _ = history.build_folds(changed)
    assert folds[0].cutoff == earlier


def test_pointer_integrity_checked_before_using_snapshot(tmp_path):
    (tmp_path / "understat_latest_pointer.json").write_text(json.dumps({"sha256": "wrong"}))
    (tmp_path / "understat_latest.json").write_text("{}")
    with pytest.raises(ValueError, match="SHA256"):
        history.load_history(tmp_path)


def test_nonfinite_and_duplicate_rows_fail_closed():
    bad = normalized_row()
    bad["xG"]["h"] = "nan"
    with pytest.raises(ValueError, match="finite"):
        history.parse_matches({"dates": [bad]}, "EPL", "2025", ())
    with pytest.raises(ValueError, match="duplicate"):
        history.parse_matches({"dates": [normalized_row(), normalized_row()]}, "EPL", "2025", ())
