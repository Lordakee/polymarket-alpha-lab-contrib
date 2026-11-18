"""Offline regression tests for the international research CLI."""

import csv
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "wp_intl_validate", Path(__file__).resolve().parents[1] / "tools" / "wp_intl_validate.py",
)
assert _spec is not None and _spec.loader is not None
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)

KICKOFF = datetime(2026, 1, 10, 20, tzinfo=timezone.utc)
BEFORE = KICKOFF - timedelta(minutes=10)
GAME = "AAA vs. BBB"
MATCHDAY = KICKOFF.date().isoformat()
TOURNAMENT = harness.NL_TOURNAMENT


def total_market(**overrides):
    return {
        "question": f"{GAME}: O/U 2.5",
        "sportsMarketType": "totals",
        "line": 2.5,
        "gameStartTime": KICKOFF.isoformat(),
        "endDate": (KICKOFF + timedelta(hours=2)).isoformat(),
        "conditionId": "total-condition",
        "outcomes": '["Over", "Under"]',
        "outcomePrices": '["0.55", "0.45"]',
        "clobTokenIds": '["1001", "1002"]',
        "description": (
            "Resolves Over if both teams combine to score 3 or more goals in "
            "the first 90 minutes of regular play plus stoppage time."
        ),
        "updatedAt": (BEFORE - timedelta(minutes=1)).isoformat(),
        "bestBid": 0.54,
        "bestAsk": 0.56,
        **overrides,
    }


def event(*markets, **overrides):
    return {
        "id": "1",
        "title": GAME,
        "closed": False,
        "endDate": (KICKOFF + timedelta(hours=2)).isoformat(),
        "markets": list(markets),
        **overrides,
    }


def match(match_date="2026-01-01", home_goals=1, away_goals=1):
    return {
        "date": match_date,
        "home": "AAA",
        "away": "BBB",
        "home_goals": home_goals,
        "away_goals": away_goals,
        "tournament": TOURNAMENT,
        "neutral": False,
        "venue": None,
    }


def snapshot(*matches):
    return {
        "generated_at": "2026-01-09T18:00:00Z",
        "teams": {"AAA": {"elo": 1510.0}, "BBB": {"elo": 1490.0}},
        "matches": list(matches),
    }


@pytest.fixture
def run_shadow(monkeypatch, tmp_path):
    def run(
        events, *, clock_at=BEFORE, discovery_finished=None, detail_finished=None,
        detail=None, model_snapshot=None, dry_run=False,
    ):
        now = clock_at
        calls = []

        def discover(*, closed):
            assert closed is False
            nonlocal now
            if discovery_finished is not None:
                now = discovery_finished
            return events

        def fetch(event_id):
            nonlocal now
            calls.append(event_id)
            if detail_finished is not None:
                now = detail_finished
            if detail is not None:
                return detail
            return next(payload for payload in events if payload["id"] == event_id)

        monkeypatch.setattr(harness, "_utc_now", lambda: now)
        monkeypatch.setattr(harness, "gamma_nl_events", discover)
        monkeypatch.setattr(harness, "fetch_event_detail", fetch)
        path = tmp_path / "shadow.csv"
        summary = harness.record_shadow_rows(
            model_snapshot if model_snapshot is not None else snapshot(match()),
            "synthetic-snapshot.json",
            path,
            date_lo=MATCHDAY,
            date_hi=MATCHDAY,
            dry_run=dry_run,
        )
        return summary, path, calls

    return run


@pytest.mark.parametrize(
    ("advance", "when", "request_count"),
    [
        ("discovery_finished", KICKOFF, 0),
        ("clock_at", KICKOFF + timedelta(minutes=1), 0),
        ("detail_finished", KICKOFF, 1),
        ("detail_finished", KICKOFF + timedelta(seconds=1), 1),
    ],
)
def test_shadow_never_records_at_or_after_game_start(run_shadow, advance, when, request_count):
    summary, path, calls = run_shadow([event(total_market())], **{advance: when})
    assert summary["rows_prepared"] == summary["rows_recorded"] == 0
    assert len(calls) == request_count
    assert "outside the pre-kickoff window" in summary["failures"][0]["reason"]
    assert not path.exists()


@pytest.mark.parametrize(
    ("discovery", "detail"),
    [
        (event(total_market(), live=True), None),
        (event(total_market()), event(total_market(), gameStatus="STATUS_IN_PROGRESS")),
        (event(total_market(gameStartTime=KICKOFF.replace(tzinfo=None).isoformat())), None),
        (event(total_market(gameStartTime=None)), None),
        (event(total_market()), event(total_market(), updatedAt="date is unknown")),
        (event(total_market(observedAt=KICKOFF.isoformat())), None),
        (event(total_market(observedAt=(BEFORE + timedelta(seconds=1)).isoformat())), None),
        (event(total_market(observedAt="2026-01-10T19:10:00")), None),
    ],
)
def test_live_and_unverifiable_timestamps_do_not_become_pregame_rows(run_shadow, discovery, detail):
    summary, path, _ = run_shadow([discovery], detail=detail)
    assert summary["rows_prepared"] == summary["rows_recorded"] == 0
    assert summary["failures"]
    assert not path.exists()


def test_shadow_ignores_corners_and_first_half_and_keeps_source_observed_unknown(run_shadow):
    flagship = event(total_market(
        question=f"{GAME}: First Half O/U 2.5", sportsMarketType="first_half_totals",
        conditionId="first-half", outcomePrices='["0.12", "0.88"]',
    ))
    sibling = event(
        total_market(question=f"{GAME}: Corners O/U 2.5", line=2.5, conditionId="corners"),
        total_market(),
        id="2", title=f"{GAME} - More Markets",
    )
    summary, path, calls = run_shadow([flagship, sibling])
    assert summary["rows_recorded"] == 1
    assert calls == ["1", "2"]
    assert summary["totals_shadow"][0]["market_ou25.observed_utc"] is None
    with path.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["state_at_scan"] == "pre"
    assert row["tip_utc"] == KICKOFF.isoformat()
    assert row["market_ou25.condition_id"] == "total-condition"
    assert row["market_ou25.yes"] == "0.55"
    assert row["market_ou25.token"] == "1001"
    assert row["market_ou25.response_received_utc"] == BEFORE.isoformat()
    assert row["market_ou25.observed_utc"] == ""
    assert row["model.rating_source"] == "replay"
    assert row["model_totals_shadow.fallback_reason"] == "insufficient_recent_matches"


def test_shadow_rejects_conflicting_start_times_across_sibling_events(run_shadow):
    other_kickoff = (KICKOFF + timedelta(hours=1)).isoformat()
    summary, path, calls = run_shadow([
        event(total_market()),
        event(total_market(gameStartTime=other_kickoff), id="2", title=f"{GAME} - More Markets"),
    ])
    assert summary["rows_prepared"] == 0
    assert {failure["reason"] for failure in summary["failures"]} == {"conflicting fixture kickoff times"}
    assert calls == []
    assert not path.exists()


def test_shadow_over_is_aligned_to_its_token_and_observed_timestamp(run_shadow):
    observed = (BEFORE - timedelta(seconds=15)).isoformat()
    market = total_market(
        outcomes='["Under", "Over"]', outcomePrices='["0.45", "0.55"]', observedAt=observed,
    )
    summary, path, _ = run_shadow([event(market)])
    assert summary["rows_recorded"] == 1
    with path.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["market_ou25.yes"] == "0.55"
    assert row["market_ou25.token"] == "1002"
    assert row["market_ou25.observed_utc"] == observed
    assert row["market_ou25.bid"] == row["market_ou25.ask"] == ""


def test_shadow_rejects_stale_current_table_quotes(run_shadow):
    summary, path, calls = run_shadow([event(total_market())], model_snapshot=snapshot())
    assert summary["rows_prepared"] == summary["rows_recorded"] == 0
    assert summary["failures"][0]["reason"] == "strictly prior replay ratings required"
    assert calls == []
    assert not path.exists()


def test_shadow_keeps_existing_csv_header_and_appends_idempotently(run_shadow, tmp_path):
    path = tmp_path / "shadow.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=harness.LEGACY_SHADOW_COLUMNS)
        writer.writeheader()
        writer.writerow({"tip_utc": "2026-01-09T20:00:00+00:00", "game": GAME})
    first, _, _ = run_shadow([event(total_market())])
    second, _, calls = run_shadow([event(total_market())])
    assert first["rows_recorded"] == 1
    assert first["totals_shadow"][0]["model_totals_shadow.version"]
    assert second["rows_recorded"] == 0
    assert second["skipped_existing"][0]["game"] == GAME
    assert calls == []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert reader.fieldnames == harness.LEGACY_SHADOW_COLUMNS
    assert len(rows) == 2 and None not in rows[1]


def test_totals_replay_cli_scores_two_predictions_on_each_fixture(monkeypatch, tmp_path, capsys):
    source = tmp_path / "snapshot.json"
    source.write_text("synthetic", encoding="utf-8")
    matches = snapshot(match(), match(MATCHDAY, 3, 0), match("2026-01-11", 8, 0))
    monkeypatch.setattr(harness.intl_data, "load_intl_snapshot", lambda _: matches)
    monkeypatch.setattr(harness, "_get_json", lambda _: pytest.fail("offline replay used the network"))
    assert harness.main([
        "totals-replay", "--snapshot", str(source), "--date-lo", MATCHDAY, "--date-hi", MATCHDAY,
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["paired_matches"] == report["over25_outcomes"] == 1
    assert report["sample_dates"] == [MATCHDAY, MATCHDAY]
    assert report["baseline"]["brier"] == report["shadow"]["brier"]
    assert report["baseline"]["log_loss_nats"] == report["shadow"]["log_loss_nats"]
    assert report["shadow"]["matchup_coverage"] == 0.0
    assert report["shadow"]["fallback_counts"] == {"insufficient_recent_matches": 1}
    assert report["snapshot"]["sha256"]
