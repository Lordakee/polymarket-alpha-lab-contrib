"""Boundary and metric tests for the isolated, read-only archive MAD diagnostic."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace

import pytest

from tools.wp_p4_market import (
    MarketAudit, MarketPredictionPair, MarketSkip, TrainingProvenance,
    archive_snapshot_availability, evaluate_market_mad, fixed_shadow_predictor,
    load_market_archive, parse_scan,
)

UTC = timezone.utc
SCAN = datetime(2026, 11, 6, 12, tzinfo=UTC)


def scan_payload():
    return {"generated_utc": SCAN.isoformat(),
        "fixtures": [{"title": "Home FC vs. Away FC", "event_id": "fixture-1",
            "understat_home": "Home", "understat_away": "Away", "home_league": "EPL",
            "away_league": "EPL", "kickoff_utc": "2026-11-07T15:00:00Z"}],
        "matches": [{"match": "Home FC vs. Away FC", "gamma_event_ids": ["fixture-1"],
            "home_league": "EPL", "away_league": "EPL", "comp": "COPIED-WRONG-LABEL",
            "kickoff_utc": "2026-11-07T15:00:00Z", "p1x2_med": {"H": 1, "D": 0, "A": 0}}],
        "board": [{"match": "Home FC vs. Away FC", "kind": "ml", "side": side,
            "id": f"market-{side}", "book_best_bid": bid, "book_best_ask": ask,
            "p_med": 0.999} for side, bid, ask in [("home", .39, .43), ("draw", .29, .33), ("away", .29, .33)]]}


def market_audit():
    observations, excluded = parse_scan(scan_payload(), "round38/raw/soccer_scan.json")
    assert not excluded
    return MarketAudit(tuple(observations), (), ())


def prediction(**overrides):
    provenance = TrainingProvenance(100, SCAN - timedelta(days=2), SCAN - timedelta(hours=1),
                                    ("historical-snapshot",), "fixed comparison")
    return MarketPredictionPair((.4, .3, .29), (.5, .25, .25), replace(provenance, **overrides))


def test_raw_coordinate_medians_and_market_overround_are_not_normalized_for_mad():
    report = evaluate_market_mad(market_audit(), lambda _: prediction())
    row = report["rows"][0]
    assert row["market_coordinate_sum"] == pytest.approx(1.03)
    assert row["frozen10_coordinate_sum"] == pytest.approx(.99)
    assert report["overall"]["frozen10_mad_cents"] == pytest.approx(4 / 3)
    assert report["overall"]["recalibrated_mad_cents"] == pytest.approx(7)
    assert sum(row["frozen10_normalized_diagnostic"]) == pytest.approx(1)
    assert row["frozen10_raw"] == (.4, .3, .29)  # Never reuse archived p_med.
    assert report["overall"]["matches"] == 1 and report["overall"]["outcomes"] == 3
    assert report["certifying_gate_E"] is False
    assert report["strict_gate_E_status"] == "UNAVAILABLE"


def test_bid_ask_midpoint_and_last_trade_are_distinct_price_kinds():
    audit = market_audit()
    ask = evaluate_market_mad(audit, lambda _: prediction(), quote_kind="ask")
    assert ask["rows"][0]["market_raw"] == (.43, .33, .33)
    trade = evaluate_market_mad(audit, lambda _: prediction(), quote_kind="last_trade")
    assert trade["overall"]["matches"] == 0
    assert trade["exclusion_counts"] == {"incomplete_last_trade_triplet": 1}
    with pytest.raises(ValueError, match="quote kind"):
        evaluate_market_mad(audit, quote_kind="gamma_as_lasttrade")


def test_explicit_canonical_mapping_overrides_copied_comp_but_never_fuzzy_names():
    payload = scan_payload()
    observations, omitted = parse_scan(payload, "scan")
    assert not omitted and observations[0].league == "EPL"
    payload["matches"][0]["gamma_event_ids"] = []
    payload["fixtures"][0]["title"] = "Home F.C. vs Away FC"
    assert parse_scan(payload, "scan")[1][0]["reason"] == "missing_or_ambiguous_domestic_fixture_mapping"


def test_exact_event_id_join_allows_archived_derivative_event_title():
    payload = scan_payload()
    payload["fixtures"][0]["title"] += " - Total Corners"
    obs, omitted = parse_scan(payload, "scan")
    assert len(obs) == 1 and not omitted
    assert "fixtures[0]" in obs[0].mapping_references


@pytest.mark.parametrize("mutate", [
    lambda p: p["fixtures"].append({**p["fixtures"][0], "understat_home": "Other"}),
    lambda p: p["fixtures"][0].update(kickoff_utc="2026-11-08T15:00:00Z"),
    lambda p: p["fixtures"][0].update(away_league="La_liga"),
    lambda p: p["matches"][0].update(home_league="La_liga"),
])
def test_ambiguous_conflicting_and_cross_league_identity_is_excluded(mutate):
    payload = scan_payload()
    mutate(payload)
    rows, excluded = parse_scan(payload, "scan")
    assert rows == [] and len(excluded) == 1


@pytest.mark.parametrize("mutate", [
    lambda p: p["board"].append(deepcopy(p["board"][0])),
    lambda p: p["board"].pop(),
    lambda p: p["board"][0].update(book_best_ask=float("nan")),
    lambda p: p["board"][0].update(book_best_bid=True),
    lambda p: p["board"][0].update(book_best_bid=.99),
    lambda p: p["board"][0].update(kickoff_utc="2026-11-08T15:00:00Z"),
])
def test_invalid_or_duplicate_prices_never_silently_select_a_favorable_quote(mutate):
    payload = scan_payload()
    mutate(payload)
    rows, excluded = parse_scan(payload, "scan")
    assert rows == []
    assert excluded[0]["reason"] == "invalid_duplicate_or_incomplete_1x2_quotes"


@pytest.mark.parametrize("stamp", [None, "2026-11-06T12:00:00", "2026-11-07T15:00:00Z"])
def test_missing_offset_or_postkickoff_report_time_is_not_replaced_by_mtime(stamp):
    payload = scan_payload()
    payload["generated_utc"] = stamp
    rows, excluded = parse_scan(payload, "scan")
    assert not rows and len(excluded) == 1


@pytest.mark.parametrize("change,reason", [
    ({"latest_kickoff": SCAN - timedelta(hours=3)}, "training_not_completed_before_scan"),
    ({"source_available_at": SCAN}, "training_snapshot_not_available_before_scan"),
    ({"history_count": -1}, "training_not_completed_before_scan"),
    ({"selection_mode": "training_only", "selection_cutoff": SCAN}, "configuration_not_selected_before_scan"),
])
def test_training_and_configuration_must_precede_scan_strictly(change, reason):
    report = evaluate_market_mad(market_audit(), lambda _: prediction(**change))
    assert report["overall"]["matches"] == 0
    assert report["exclusion_counts"] == {reason: 1}


def test_wrong_variant_count_and_future_selected_configuration_fail_closed():
    with pytest.raises(ValueError, match="ten frozen"):
        evaluate_market_mad(market_audit(), lambda _: replace(prediction(), variant_count=9))
    with pytest.raises(ValueError, match="configuration"):
        evaluate_market_mad(market_audit(), lambda _: prediction(selection_mode="best_market_mad"))


def test_earliest_usable_scan_selected_once_even_if_later_error_would_be_lower():
    audit = market_audit()
    obs = audit.observations[0]
    early = replace(obs, scan_at=SCAN - timedelta(hours=2), source_path="early")
    late = replace(obs, scan_at=SCAN + timedelta(hours=1), source_path="late")
    calls = []

    def callback(item):
        calls.append(item.source_path)
        return prediction()

    report = evaluate_market_mad(replace(audit, observations=(late, obs, early)), callback)
    assert calls == ["early", obs.source_path]
    assert report["rows"][0]["source_path"] == obs.source_path
    assert report["exclusion_counts"] == {"training_snapshot_not_available_before_scan": 1,
                                           "later_scan_duplicate_fixture": 1}


def test_missing_history_returns_explicit_skip_and_null_metric():
    report = evaluate_market_mad(market_audit(), lambda _: MarketSkip("no_2025_market_history"))
    assert report["overall"]["frozen10_mad_cents"] is None
    assert report["exclusion_counts"] == {"no_2025_market_history": 1}
    missing = evaluate_market_mad(market_audit())
    assert missing["exclusion_counts"] == {"pre_scan_prediction_provider_unavailable": 1}


def test_loader_records_exact_source_bytes_and_does_not_modify_archives(tmp_path):
    folder = tmp_path / "round38" / "raw"
    folder.mkdir(parents=True)
    file = folder / "epl_champ_scan.json"
    data = json.dumps(scan_payload()).encode()
    file.write_bytes(data)
    audit = load_market_archive(tmp_path)
    assert len(audit.observations) == 1
    assert audit.sources == ({"path": "round38/raw/epl_champ_scan.json",
                             "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},)
    assert file.read_bytes() == data


def test_snapshot_availability_uses_pinned_metadata_and_detects_changed_bytes(tmp_path):
    snap = "round39/raw/xg_fotmob_eredivisie.json"
    meta = snap + ".meta.json"
    file = tmp_path / meta
    file.parent.mkdir(parents=True)
    content = b'{"fetched_utc":"2026-11-07T07:08:12Z"}'
    file.write_bytes(content)
    history = SimpleNamespace(sources=({"path": snap},
        {"path": meta, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}))
    times = archive_snapshot_availability(history, tmp_path)
    assert times[snap] == datetime(2026, 11, 7, 7, 8, 12, tzinfo=UTC)
    file.write_bytes(content.replace(b"07:08", b"07:09"))
    with pytest.raises(ValueError, match="changed"):
        archive_snapshot_availability(history, tmp_path)


def _synthetic_history(*, current_round=1, target_round=2):
    from tools.wp_p4_history import HistoricalMatch, HistoryAudit, ScheduleFixture

    teams = ["Home", "Away", *[f"Club {n}" for n in range(18)]]
    rows, schedule = [], []
    for home in teams:
        for away in teams:
            if home == away:
                continue
            i = len(rows)
            rows.append(HistoricalMatch(
                match_id=f"prior-{i}", league="EPL", season="2025", matchweek=None,
                kickoff=SCAN - timedelta(days=400) + timedelta(hours=6 * i),
                home_team=home, away_team=away, home_xg=1.6, away_xg=1.2,
                home_goals=2, away_goals=1, source_path="synthetic"))
    for i in range(10):
        home, away = teams[2 * i:2 * i + 2]
        kickoff = SCAN - timedelta(days=7)
        rows.append(HistoricalMatch(match_id=f"current-{i}", league="EPL", season="2026",
            matchweek=current_round, kickoff=kickoff, home_team=home, away_team=away,
            home_xg=1.7, away_xg=1.1, home_goals=2, away_goals=1,
            schedule_match_id=f"current-{i}", source_path="synthetic"))
        schedule.append(ScheduleFixture(f"current-{i}", "EPL", "2026", current_round,
            kickoff, home, away, True, False, False, "2-1"))
    obs = market_audit().observations[0]
    schedule.append(ScheduleFixture("target", "EPL", "2026", target_round,
        obs.kickoff, "Home", "Away", False, False, False))
    roster = tuple(("EPL", season, team, str(i)) for season in ("2025", "2026") for i, team in enumerate(teams))
    history = HistoryAudit(tuple(rows), tuple(schedule), (), (), roster)
    return history, obs


def test_fixed_shadow_callback_fits_real_estimator_and_frozen_model_on_same_safe_history():
    history, obs = _synthetic_history()
    callback = fixed_shadow_predictor(history, {"synthetic": SCAN - timedelta(hours=1)})
    pair = callback(obs)
    assert isinstance(pair, MarketPredictionPair)
    assert pair.provenance.history_count == 390
    assert pair.provenance.completed_current_rounds == (1,)
    assert pair.variant_count == 10
    assert sum(pair.recalibrated) == pytest.approx(1)
    assert all(0 < v < 1 for v in pair.frozen10)
    result = evaluate_market_mad(market_audit(), callback)
    assert result["overall"]["matches"] == 1


def test_postponed_older_round_is_skipped_and_archive_continues_on_same_cached_model():
    from tools.wp_p4_history import ScheduleFixture

    history, postponed = _synthetic_history(current_round=2, target_round=1)
    supported = replace(postponed, kickoff=postponed.kickoff + timedelta(days=1),
                        source_path="round-later/raw/soccer_scan.json")
    later_fixture = ScheduleFixture("later-target", "EPL", "2026", 3,
        supported.kickoff, supported.home_team, supported.away_team, False, False, False)
    history = replace(history, schedule=(*history.schedule, later_fixture))
    callback = fixed_shadow_predictor(history, {"synthetic": SCAN - timedelta(hours=1)})
    report = evaluate_market_mad(MarketAudit((postponed, supported), (), ()), callback)

    assert report["overall"]["matches"] == 1
    assert report["overall"]["outcomes"] == 3
    assert report["exclusion_counts"] == {"target_round_not_after_fitted_current_rounds": 1}
    assert report["exclusions"][0]["source_path"] == postponed.source_path
    assert report["rows"][0]["source_path"] == supported.source_path
    assert report["rows"][0]["training"]["completed_current_rounds"] == (2,)
    assert report["rows"][0]["training"]["history_count"] == 390
