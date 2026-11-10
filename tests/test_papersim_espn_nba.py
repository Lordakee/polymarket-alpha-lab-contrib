"""WP-NBA-1 tests: ESPN NBA snapshot adapter library module.

Four layers (house pattern of ``test_papersim_fotmob.py``):

- Mapping/constants layer: the frozen 30-team id table (derived live
  2026-11-10 UTC from each team's own schedule payload), season label
  <-> ESPN ``season=`` year conversion, MappingProxyType immutability.
- Transform layer (pure, synthetic payloads): a small synthetic 2-team
  season drives :func:`build_snapshot` end to end — possession formula
  with the documented per-team split, ortg/drtg per-100, rest/b2b
  derivation, latest-per-team injury reporting — plus a realistic
  3-team slice shaped exactly like the verified ESPN wire (paired
  displayValues, header scores, totalTurnovers), and the fail-closed
  matrix: season drift, team mismatch, missing summaries, missing stat
  groups, malformed pairs, negative scores, zero possessions,
  schedule-vs-summary score disagreement, game-count and duplicate-date
  ceilings (the codex review #8 finite/nonnegative discipline).
- Load/write layer: the frozen snapshot contract — exact key sets,
  30-team default table, boolean/int/null typing, NaN/Infinity
  rejection, strictly positive possessions — via round-trips through
  ``write_snapshot``/``load_nba_snapshot`` on tmp files.
- Fetch/cache layer (mocked urllib, no network): URL construction
  (including the ``/apis`` path prefix that distinguishes the working
  endpoint from the 403-ing shorthand), shared polite spacing
  (1 req / 1.2 s), retry/backoff, and the read-through on-disk cache
  (atomic writes, schedule expiry, immutable summaries, corrupt-cache
  refetch).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType

import pytest

from polymarket_alpha_lab.papersim import espn_nba

GENERATED_AT = "2026-11-10T06:30:00+00:00"


# --------------------------------------------------------------------------
# synthetic payload builders (ESPN wire shapes, verified 2026-11-10)
# --------------------------------------------------------------------------

def _wire_team(abbrev: str, display: str, team_id: int) -> dict:
    return {"id": str(team_id), "abbreviation": abbrev,
            "displayName": display}


def _schedule_event(
    eid: str,
    day: str,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    *,
    completed: bool = True,
    stamp: str | None = None,
) -> dict:
    # default stamp 17:00Z = 1pm ET: the ET calendar date equals ``day``.
    # Late starts pass the real UTC stamp (whose prefix runs a day ahead).
    return {
        "id": eid,
        "date": stamp or f"{day}T17:00Z",
        "seasonType": 2,
        "competitions": [{
            "status": {"type": {"completed": completed, "name": "STATUS_FINAL"}},
            "competitors": [
                {"homeAway": "home", "score": {"value": float(home_score),
                                               "displayValue": str(home_score)},
                 "team": _wire_team(home, home, 100)},
                {"homeAway": "away", "score": {"value": float(away_score),
                                               "displayValue": str(away_score)},
                 "team": _wire_team(away, away, 200)},
            ],
        }],
    }


def _schedule_payload(abbrev: str, display: str, events: list) -> dict:
    return {
        "requestedSeason": {"year": 2027, "type": 2,
                            "displayName": "2026-27"},
        "season": {"year": 2027, "type": 2},
        "team": _wire_team(abbrev, display, 100),
        "events": events,
    }


def _stats_groups(fga: int, oreb: int, tov: int, fta: int) -> list:
    fgm, ftm = max(fga - 38, 0), max(fta - 5, 0)
    return [
        {"name": "fieldGoalsMade-fieldGoalsAttempted",
         "displayValue": f"{fgm}-{fga}"},
        {"name": "freeThrowsMade-freeThrowsAttempted",
         "displayValue": f"{ftm}-{fta}"},
        {"name": "offensiveRebounds", "displayValue": str(oreb)},
        {"name": "turnovers", "displayValue": str(max(tov - 1, 0))},
        {"name": "totalTurnovers", "displayValue": str(tov)},
    ]


def _summary_payload(
    eid: str,
    day: str,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    home_stats: tuple,
    away_stats: tuple,
    injuries: list | None = None,
) -> dict:
    competitors = []
    for side, abbrev, score in (
        ("home", home, home_score), ("away", away, away_score),
    ):
        competitors.append({
            "homeAway": side, "score": score,
            "team": _wire_team(abbrev, abbrev, 100 if side == "home" else 200),
        })
    payload = {
        "header": {"competitions": [{
            "date": f"{day}T00:00Z", "competitors": competitors,
        }]},
        "boxscore": {"teams": [
            {"homeAway": "home", "team": _wire_team(home, home, 100),
             "statistics": _stats_groups(*home_stats)},
            {"homeAway": "away", "team": _wire_team(away, away, 200),
             "statistics": _stats_groups(*away_stats)},
        ]},
    }
    if injuries is not None:
        payload["injuries"] = injuries
    return payload


def _injury_block(abbrev: str, entries: list) -> dict:
    rows = [
        {"status": status, "date": when, "athlete": {"fullName": player}}
        for player, status, when in entries
    ]
    return {"team": _wire_team(abbrev, abbrev, 100), "injuries": rows}


def _bundle(schedules: dict, summaries: dict,
            season: str = "2026-27") -> dict:
    return {
        "season": season,
        "season_year": espn_nba.season_year(season),
        "generated_at": GENERATED_AT,
        "schedules": schedules,
        "summaries": summaries,
    }


# synthetic 2-team season: AAA hosts g1, BBB hosts g2 the next day (b2b
# for both), AAA hosts g3 four days later. Possession inputs chosen for
# exact arithmetic: AAA g1 poss = 90-10+15+0.44*25 = 106.0 exactly.
AAA_G1 = (90, 10, 15, 25)   # -> poss 106.0
BBB_G1 = (85, 8, 12, 20)    # -> poss 97.8
AAA_G2 = (88, 9, 14, 20)    # -> poss 100.8
BBB_G2 = (95, 11, 10, 30)   # -> poss 98.2... (95-11+10+13.2=107.2)
AAA_G3 = (92, 12, 18, 25)   # -> 92-12+18+11 = 109.0
BBB_G3 = (80, 6, 14, 15)    # -> 80-6+14+6.6 = 94.6

TWO_TEAM_EVENTS = [
    ("4011", "2026-10-22", "AAA", "BBB", 112, 105),
    ("4012", "2026-10-23", "BBB", "AAA", 98, 121),
    ("4013", "2026-10-27", "AAA", "BBB", 108, 99),
]
TWO_TEAM_STATS = {
    "4011": (AAA_G1, BBB_G1), "4012": (AAA_G2, BBB_G2),
    "4013": (AAA_G3, BBB_G3),
}


def _two_team_bundle() -> dict:
    schedules = {
        "AAA": _schedule_payload("AAA", "Alpha Aces", [
            _schedule_event(*spec) for spec in TWO_TEAM_EVENTS
        ]),
        "BBB": _schedule_payload("BBB", "Beta Bears", [
            _schedule_event(*spec) for spec in TWO_TEAM_EVENTS
        ]),
    }
    summaries = {
        eid: _summary_payload(
            eid, day, home, away, hs, as_,
            TWO_TEAM_STATS[eid][0] if home == "AAA" else TWO_TEAM_STATS[eid][1],
            TWO_TEAM_STATS[eid][1] if home == "AAA" else TWO_TEAM_STATS[eid][0],
        )
        for eid, day, home, away, hs, as_ in TWO_TEAM_EVENTS
    }
    return _bundle(schedules, summaries)


TEAMS_2 = {"AAA", "BBB"}


# --------------------------------------------------------------------------
# mapping / season-label layer
# --------------------------------------------------------------------------

def test_frozen_team_mapping() -> None:
    teams = espn_nba.NBA_TEAMS
    assert len(teams) == espn_nba.TEAM_COUNT == 30
    assert len({team_id for team_id, _ in teams.values()}) == 30
    assert len(set(teams)) == 30
    # spot anchors derived live 2026-11-10 (schedule payload echoes)
    assert teams["POR"] == (22, "Portland Trail Blazers")
    assert teams["LAL"] == (13, "Los Angeles Lakers")
    assert teams["ATL"] == (1, "Atlanta Hawks")
    assert teams["OKC"] == (25, "Oklahoma City Thunder")
    with pytest.raises(TypeError):
        teams["XXX"] = (99, "Nobody")  # type: ignore[index]


@pytest.mark.parametrize(
    "label,year", [("2026-27", 2027), ("2025-26", 2026), ("1999-00", 2000)]
)
def test_season_year_roundtrip(label: str, year: int) -> None:
    assert espn_nba.season_year(label) == year
    assert espn_nba._season_label(year) == label


@pytest.mark.parametrize("bad", ["2026-28", "26-27", "2026-7", "202627", ""])
def test_season_year_rejects_malformed_labels(bad: str) -> None:
    with pytest.raises(ValueError):
        espn_nba.season_year(bad)


# --------------------------------------------------------------------------
# transform layer: synthetic 2-team season
# --------------------------------------------------------------------------

def test_build_snapshot_two_team_season() -> None:
    snapshot = espn_nba.build_snapshot(
        _two_team_bundle(), expected_teams=TEAMS_2
    )
    assert snapshot["source"] == "espn-nba"
    assert snapshot["season"] == "2026-27"
    assert snapshot["generated_at"] == GENERATED_AT
    assert set(snapshot["teams"]) == TEAMS_2
    assert snapshot["injuries"] == {}
    assert snapshot["teams"]["AAA"]["display"] == "Alpha Aces"

    aaa = snapshot["teams"]["AAA"]["games"]
    assert [row["date"] for row in aaa] == [
        "2026-10-22", "2026-10-23", "2026-10-27",
    ]
    g1, g2, g3 = aaa
    # possession formula and the documented per-team split: each row
    # carries its OWN estimate (game total = sum of the two rows)
    assert g1["poss"] == pytest.approx(90 - 10 + 15 + 0.44 * 25)
    assert g1["pts"] == 112 and g1["opp_pts"] == 105
    assert g1["ortg"] == pytest.approx(100.0 * 112 / 106.0)
    assert g1["drtg"] == pytest.approx(100.0 * 105 / 106.0)
    assert isinstance(g1["pts"], int) and isinstance(g1["poss"], float)
    assert g1["home"] is True and g1["opponent"] == "BBB"
    assert g1["rest_days"] is None and g1["b2b"] is False
    assert g2["home"] is False and g2["opponent"] == "BBB"
    assert g2["rest_days"] == 1 and g2["b2b"] is True   # next-day game
    assert g3["rest_days"] == 4 and g3["b2b"] is False
    # the opponent's row for the same game is the mirror view
    bbb_g1 = snapshot["teams"]["BBB"]["games"][0]
    assert bbb_g1["poss"] == pytest.approx(85 - 8 + 12 + 0.44 * 20)
    assert bbb_g1["pts"] == 105 and bbb_g1["opp_pts"] == 112
    assert bbb_g1["ortg"] == pytest.approx(100.0 * 105 / 97.8)
    assert g1["poss"] != bbb_g1["poss"]  # split kept per-team, not 50/50


def test_build_snapshot_injuries_latest_report_per_team() -> None:
    bundle = _two_team_bundle()
    # g1 (older) report lists a returned player; g3 (latest for both
    # teams) lists only a currently-out AAA player and none for BBB
    bundle["summaries"]["4011"]["injuries"] = [
        _injury_block("AAA", [("Old Player", "Out", "2026-10-20T22:15Z")]),
    ]
    bundle["summaries"]["4013"]["injuries"] = [
        _injury_block("AAA", [("Zed Ace", "Out", "2026-11-05T22:15Z"),
                              ("Ann Ace", "Day-To-Day", "2026-11-06T22:15Z")]),
    ]
    snapshot = espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)
    assert snapshot["injuries"] == {
        "AAA": [
            {"player": "Ann Ace", "status": "Day-To-Day",
             "date": "2026-11-06T22:15Z"},
            {"player": "Zed Ace", "status": "Out",
             "date": "2026-11-05T22:15Z"},
        ],
    }


def test_build_snapshot_requires_all_expected_teams() -> None:
    bundle = _two_team_bundle()
    # default expectation = frozen 30 NBA teams; the synthetic keys are
    # outside that table
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="outside expected"):
        espn_nba.build_snapshot(bundle)
    # an expected team without its schedule fails closed
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="missing schedules"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2 | {"CCC"})
    # a schedule key outside the expected set is schema drift
    bundle["schedules"]["CCC"] = _schedule_payload("CCC", "Gamma Goats", [])
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="outside expected"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_rejects_season_mismatch() -> None:
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="!= requested"):
        espn_nba.build_snapshot(_two_team_bundle(), season="2025-26",
                                expected_teams=TEAMS_2)
    bad = _two_team_bundle()
    bad["season"] = "202627"
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="season label"):
        espn_nba.build_snapshot(bad, expected_teams=TEAMS_2)
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="no season"):
        espn_nba.build_snapshot({"schedules": {}, "summaries": {}},
                                expected_teams=TEAMS_2)


def test_build_snapshot_missing_summary_fails_closed() -> None:
    bundle = _two_team_bundle()
    del bundle["summaries"]["4012"]
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="no summary for completed event 4012"
    ):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_unplayed_games_excluded() -> None:
    schedules = {
        "AAA": _schedule_payload("AAA", "Alpha Aces", [
            _schedule_event(*TWO_TEAM_EVENTS[0]),
            _schedule_event("4099", "2026-12-25", "AAA", "BBB", 0, 0,
                            completed=False),
        ]),
        "BBB": _schedule_payload("BBB", "Beta Bears", [
            _schedule_event(*TWO_TEAM_EVENTS[0]),
            _schedule_event("4099", "2026-12-25", "AAA", "BBB", 0, 0,
                            completed=False),
        ]),
    }
    summaries = {"4011": _summary_payload(
        "4011", "2026-10-22", "AAA", "BBB", 112, 105, AAA_G1, BBB_G1,
    )}
    snapshot = espn_nba.build_snapshot(
        _bundle(schedules, summaries), expected_teams=TEAMS_2
    )
    assert [row["date"] for row in snapshot["teams"]["AAA"]["games"]] == [
        "2026-10-22"
    ]


@pytest.mark.parametrize("drop", [
    "fieldGoalsMade-fieldGoalsAttempted",
    "freeThrowsMade-freeThrowsAttempted",
    "offensiveRebounds",
])
def test_build_snapshot_missing_stat_group_fails_closed(drop: str) -> None:
    bundle = _two_team_bundle()
    groups = bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"]
    bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"] = [
        g for g in groups if g["name"] != drop
    ]
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="missing stat group"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_turnovers_fallback_without_split() -> None:
    bundle = _two_team_bundle()
    groups = bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"]
    bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"] = [
        g for g in groups if g["name"] != "totalTurnovers"
    ]  # falls back to `turnovers` (14) rather than failing
    snapshot = espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)
    g1 = snapshot["teams"]["AAA"]["games"][0]
    assert g1["poss"] == pytest.approx(90 - 10 + 14 + 0.44 * 25)
    # both turnover groups missing at once is still schema drift
    bundle = _two_team_bundle()
    groups = bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"]
    bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"] = [
        g for g in groups
        if g["name"] not in ("totalTurnovers", "turnovers")
    ]
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="totalTurnovers"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


@pytest.mark.parametrize("bad_pair", ["45", "45-85-2", "many-85", "45-x"])
def test_build_snapshot_malformed_paired_stat(bad_pair: str) -> None:
    bundle = _two_team_bundle()
    for group in bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"]:
        if group["name"] == "fieldGoalsMade-fieldGoalsAttempted":
            group["displayValue"] = bad_pair
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="malformed pair"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


@pytest.mark.parametrize("bad_value", ["x", "", "-3", "NaN", "None", None])
def test_build_snapshot_malformed_single_stat(bad_value: object) -> None:
    bundle = _two_team_bundle()
    for group in bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"]:
        if group["name"] == "offensiveRebounds":
            group["displayValue"] = bad_value
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="malformed value"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_rejects_negative_or_fractional_score() -> None:
    bundle = _two_team_bundle()
    competitor = bundle["schedules"]["AAA"]["events"][0]["competitions"][0][
        "competitors"][0]
    for bad in ({"value": -5.0}, {"value": 10.5}, "lots", None):
        competitor["score"] = bad
        with pytest.raises(
            espn_nba.EspnNbaSchemaError, match="score .* not"
        ):
            espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_zero_possessions_rejected() -> None:
    bundle = _two_team_bundle()
    bundle["summaries"]["4011"]["boxscore"]["teams"][0]["statistics"] = (
        _stats_groups(0, 0, 0, 0)
    )
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="finite positive"
    ):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_score_disagreement_rejected() -> None:
    bundle = _two_team_bundle()
    header = bundle["summaries"]["4011"]["header"]["competitions"][0]
    header["competitors"][0]["score"] = 111  # schedule says 112
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="schedule 112"
    ):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_box_teams_disagree_with_schedule() -> None:
    bundle = _two_team_bundle()
    bundle["summaries"]["4011"]["boxscore"]["teams"][0]["team"] = (
        _wire_team("CCC", "Gamma Goats", 100)
    )
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="boxscore home"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)
    # header AND box consistent with each other but foreign to the
    # schedule: caught by the build-level team-set check
    bundle = _two_team_bundle()
    summary = bundle["summaries"]["4011"]
    summary["header"]["competitions"][0]["competitors"][0]["team"] = (
        _wire_team("CCC", "Gamma Goats", 100)
    )
    summary["boxscore"]["teams"][0]["team"] = _wire_team("CCC", "Gamma Goats", 100)
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="box teams"):
        espn_nba.build_snapshot(bundle, expected_teams=TEAMS_2)


def test_build_snapshot_game_count_ceiling() -> None:
    events = [
        _schedule_event(f"50{i:03d}", f"2026-{(i // 28) % 12 + 1:02d}-"
                        f"{i % 28 + 1:02d}", "AAA", "BBB", 100, 98)
        for i in range(espn_nba.MAX_GAMES_PER_TEAM + 1)
    ]
    schedules = {
        "AAA": _schedule_payload("AAA", "Alpha Aces", events),
        "BBB": _schedule_payload("BBB", "Beta Bears", events),
    }
    summaries = {
        e["id"]: _summary_payload(
            e["id"], e["date"][:10], "AAA", "BBB", 100, 98, AAA_G1, BBB_G1,
        )
        for e in events
    }
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="exceeds sanity ceiling"
    ):
        espn_nba.build_snapshot(_bundle(schedules, summaries),
                                expected_teams=TEAMS_2)


def test_build_snapshot_duplicate_date_rejected() -> None:
    events = [
        _schedule_event("5101", "2026-10-22", "AAA", "BBB", 100, 98),
        _schedule_event("5102", "2026-10-22", "BBB", "AAA", 101, 97),
    ]
    schedules = {
        "AAA": _schedule_payload("AAA", "Alpha Aces", events),
        "BBB": _schedule_payload("BBB", "Beta Bears", events),
    }
    summaries = {
        e["id"]: _summary_payload(
            e["id"], "2026-10-22",
            *(("AAA", "BBB") if i == 0 else ("BBB", "AAA")),
            *((100, 98) if i == 0 else (101, 97)),
            AAA_G1, BBB_G1,
        )
        for i, e in enumerate(events)
    }
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="duplicate/non-increasing"
    ):
        espn_nba.build_snapshot(_bundle(schedules, summaries),
                                expected_teams=TEAMS_2)


# --------------------------------------------------------------------------
# calendar layer: ET date derivation from UTC instants
# --------------------------------------------------------------------------

@pytest.mark.parametrize("stamp,expected", [
    ("2026-10-28T00:00Z", date(2026, 10, 27)),  # DET@NYK Tue 8pm ET
    ("2026-10-28T23:00Z", date(2026, 10, 28)),  # CHA@DET same UTC prefix
    ("2026-10-22T02:00Z", date(2026, 10, 21)),  # 7pm PT opener (EDT -4)
    ("2026-11-10T00:00Z", date(2026, 11, 9)),   # 7pm ET after DST end (EST -5)
    ("2026-03-10T02:00Z", date(2026, 3, 9)),    # March, inside EDT
    ("2026-02-11T02:00Z", date(2026, 2, 10)),   # deep EST winter
    ("2026-10-25T17:00Z", date(2026, 10, 25)),  # midday: prefix is the date
])
def test_et_date_derivation(stamp: str, expected: date) -> None:
    assert espn_nba._et_date(stamp, "x") == expected
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="malformed timestamp"):
        espn_nba._et_date("not-a-timestamp", "x")


def test_real_b2b_sharing_a_utc_date_prefix() -> None:
    """Regression (real 2026-27 data, 2026-11-10): Detroit's Oct 27 @ NYK
    (stamped 2026-10-28T00:00Z) and Oct 28 vs CHA (2026-10-28T23:00Z)
    share the UTC date prefix. Prefix dates would collide (duplicate-date
    fail-closed); ET dates resolve to a genuine back-to-back."""
    events = [
        _schedule_event("409878", "2026-10-27", "NY", "DET", 105, 109,
                        stamp="2026-10-28T00:00Z"),
        _schedule_event("409883", "2026-10-28", "DET", "CHA", 112, 107,
                        stamp="2026-10-28T23:00Z"),
    ]
    schedules = {
        "NY": _schedule_payload("NY", "New York Knicks", [events[0]]),
        "DET": _schedule_payload("DET", "Detroit Pistons", events),
        "CHA": _schedule_payload("CHA", "Charlotte Hornets", [events[1]]),
    }
    summaries = {
        "409878": _summary_payload("409878", "2026-10-27", "NY", "DET",
                                   105, 109, AAA_G1, BBB_G1),
        "409883": _summary_payload("409883", "2026-10-28", "DET", "CHA",
                                   112, 107, AAA_G2, BBB_G2),
    }
    snapshot = espn_nba.build_snapshot(
        _bundle(schedules, summaries), expected_teams={"NY", "DET", "CHA"}
    )
    det = snapshot["teams"]["DET"]["games"]
    assert [row["date"] for row in det] == ["2026-10-27", "2026-10-28"]
    assert det[0]["rest_days"] is None and det[0]["b2b"] is False
    assert det[1]["rest_days"] == 1 and det[1]["b2b"] is True


# --------------------------------------------------------------------------
# transform layer: realistic 3-team slice (verified wire shapes)
# --------------------------------------------------------------------------

def test_build_snapshot_realistic_three_team_slice() -> None:
    # LAL/GS/ATL with stat lines lifted from the retained 2026-11-10
    # LAL@ATL summary (45-85, 8 oreb, 16 tov, 23 fta / 40-88, 12, 20, 23)
    # and the real 2026-27 opener date; POR has no completed games yet.
    lal_atl = _summary_payload(
        "401909952", "2026-11-09", "ATL", "LAL", 114, 124,
        (88, 12, 20, 23), (85, 8, 16, 23),
        injuries=[
            _injury_block("ATL", [("Asa Newell", "Out",
                                   "2026-11-08T22:15Z")]),
        ],
    )
    gs_at_lal = _summary_payload(
        "401809244", "2026-10-21", "LAL", "GS", 109, 119,
        (85, 10, 14, 21), (90, 11, 18, 26),
    )
    atl_at_gs = _summary_payload(
        "401909001", "2026-10-25", "GS", "ATL", 121, 116,
        (92, 9, 15, 19), (87, 7, 13, 24),
    )
    schedules = {
        "LAL": _schedule_payload("LAL", "Los Angeles Lakers", [
            _schedule_event("401809244", "2026-10-21", "LAL", "GS", 109, 119,
                            stamp="2026-10-22T02:00Z"),  # 7pm PT opener
            _schedule_event("401909952", "2026-11-09", "ATL", "LAL", 114, 124,
                            stamp="2026-11-10T00:00Z"),  # 7pm ET = Nov 9
        ]),
        "GS": _schedule_payload("GS", "Golden State Warriors", [
            _schedule_event("401809244", "2026-10-21", "LAL", "GS", 109, 119),
            _schedule_event("401909001", "2026-10-25", "GS", "ATL", 121, 116),
        ]),
        "ATL": _schedule_payload("ATL", "Atlanta Hawks", [
            _schedule_event("401909001", "2026-10-25", "GS", "ATL", 121, 116),
            _schedule_event("401909952", "2026-11-09", "ATL", "LAL", 114, 124),
        ]),
        "POR": _schedule_payload("POR", "Portland Trail Blazers", [
            _schedule_event("401999001", "2026-11-12", "POR", "LAL", 0, 0,
                            completed=False),
            _schedule_event("401999002", "2026-11-14", "GS", "POR", 0, 0,
                            completed=False),
        ]),
    }
    snapshot = espn_nba.build_snapshot(
        _bundle(schedules, {
            "401809244": gs_at_lal, "401909001": atl_at_gs,
            "401909952": lal_atl,
        }),
        expected_teams={"LAL", "GS", "ATL", "POR"},
    )
    lal = snapshot["teams"]["LAL"]["games"]
    assert [row["date"] for row in lal] == ["2026-10-21", "2026-11-09"]
    opener, latest = lal
    assert opener["home"] is True and opener["opponent"] == "GS"
    assert opener["pts"] == 109 and opener["opp_pts"] == 119
    assert latest["home"] is False and latest["opponent"] == "ATL"
    assert latest["pts"] == 124 and latest["opp_pts"] == 114
    assert latest["rest_days"] == (date(2026, 11, 9) - date(2026, 10, 21)).days
    # per-team pace sits in a realistic band. The LAL@ATL line is the
    # REAL retained sample (a high-pace game estimating ~103-106 poss
    # per side), so the slice band is wider than the study's 94-102
    # regulation-pace gate, which the model layer owns.
    for abbrev in ("LAL", "GS", "ATL"):
        for row in snapshot["teams"][abbrev]["games"]:
            assert 90.0 <= row["poss"] <= 110.0, (abbrev, row["poss"])
    # a team with no completed games still occupies the table
    assert snapshot["teams"]["POR"] == {
        "display": "Portland Trail Blazers", "games": [],
    }
    # injury report comes from ATL's latest game (the Nov 9 summary)
    assert snapshot["injuries"] == {"ATL": [{
        "player": "Asa Newell", "status": "Out",
        "date": "2026-11-08T22:15Z",
    }]}


# --------------------------------------------------------------------------
# load / write layer: frozen contract
# --------------------------------------------------------------------------

def _write_and_load(snapshot: dict, tmp_path: Path) -> dict:
    target = espn_nba.write_snapshot(
        snapshot, tmp_path / "snap.json", expected_teams=TEAMS_2
    )
    assert target.is_file()
    assert not list(tmp_path.glob("*.tmp"))  # atomic: no leftovers
    return espn_nba.load_nba_snapshot(str(target), expected_teams=TEAMS_2)


def test_snapshot_round_trip(tmp_path: Path) -> None:
    snapshot = espn_nba.build_snapshot(
        _two_team_bundle(), expected_teams=TEAMS_2
    )
    assert _write_and_load(snapshot, tmp_path) == snapshot


def test_load_enforces_default_30_team_table(tmp_path: Path) -> None:
    snapshot = espn_nba.build_snapshot(
        _two_team_bundle(), expected_teams=TEAMS_2
    )
    target = tmp_path / "snap.json"
    target.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(ValueError, match="!= expected"):
        espn_nba.load_nba_snapshot(str(target))


def test_load_rejects_contract_violations(tmp_path: Path) -> None:
    snapshot = espn_nba.build_snapshot(
        _two_team_bundle(), expected_teams=TEAMS_2
    )

    def reload_mutated(mutate) -> None:
        import copy
        mutated = copy.deepcopy(snapshot)
        mutate(mutated)
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError):
            espn_nba.load_nba_snapshot(str(path), expected_teams=TEAMS_2)

    reload_mutated(lambda s: s.pop("injuries"))              # missing key
    reload_mutated(lambda s: s.update(extra=1))              # extra key
    reload_mutated(lambda s: s.update(source="espn-nba-2"))  # wrong source
    reload_mutated(lambda s: s.update(season="2026-27x"))    # bad season
    reload_mutated(lambda s: s.update(generated_at="yesterday"))
    reload_mutated(lambda s: s["teams"]["AAA"].pop("display"))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].pop("b2b"))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(home=1))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(pts=110.5))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(pts=True))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(opp_pts=-1))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(rest_days="1"))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(rest_days=-2))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(date="10/22/26"))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(opponent="AAA"))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(opponent="ZZZ"))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(poss=0.0))
    reload_mutated(lambda s: s["teams"]["AAA"]["games"][0].update(drtg=-1.0))
    reload_mutated(lambda s: s.update(injuries={"ZZZ": []}))
    reload_mutated(lambda s: s["injuries"].update(AAA=[{"player": "X"}]))
    reload_mutated(lambda s: s["injuries"].update(AAA=[{
        "player": "", "status": "Out", "date": "2026-11-01T00:00Z"}]))


def test_load_rejects_nan_and_infinity_literals(tmp_path: Path) -> None:
    """json.load accepts bare NaN/Infinity; the load boundary must not
    (codex review #8 discipline)."""
    snapshot = espn_nba.build_snapshot(
        _two_team_bundle(), expected_teams=TEAMS_2
    )
    for bad in ("NaN", "Infinity", "-Infinity"):
        path = tmp_path / f"bad_{bad}.json"
        path.write_text(
            json.dumps(snapshot).replace('"poss": 106.0', f'"poss": {bad}'),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="not finite"):
            espn_nba.load_nba_snapshot(str(path), expected_teams=TEAMS_2)


def test_load_rejects_game_count_over_ceiling(tmp_path: Path) -> None:
    rows = [{
        "date": f"2026-{(i // 28) % 12 + 1:02d}-{i % 28 + 1:02d}",
        "home": True, "opponent": "BBB", "poss": 100.0,
        "pts": 100, "opp_pts": 98, "ortg": 100.0, "drtg": 98.0,
        "rest_days": None, "b2b": False,
    } for i in range(espn_nba.MAX_GAMES_PER_TEAM + 1)]
    payload = {
        "generated_at": GENERATED_AT, "source": "espn-nba",
        "season": "2026-27",
        "teams": {"AAA": {"display": "Alpha Aces", "games": rows},
                  "BBB": {"display": "Beta Bears", "games": []}},
        "injuries": {},
    }
    path = tmp_path / "too_many.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds"):
        espn_nba.load_nba_snapshot(str(path), expected_teams=TEAMS_2)


def test_write_snapshot_validates_before_writing(tmp_path: Path) -> None:
    import copy
    snapshot = espn_nba.build_snapshot(
        _two_team_bundle(), expected_teams=TEAMS_2
    )
    mutated = copy.deepcopy(snapshot)
    mutated["teams"]["AAA"]["games"][0]["poss"] = float("nan")
    with pytest.raises(ValueError, match="not finite"):
        espn_nba.write_snapshot(
            mutated, tmp_path / "never.json", expected_teams=TEAMS_2
        )
    assert not (tmp_path / "never.json").exists()


# --------------------------------------------------------------------------
# fetch layer: mocked urllib, no network
# --------------------------------------------------------------------------

class _StubResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _install_urlopen(monkeypatch: pytest.MonkeyPatch, responses: list) -> list:
    requests: list = []
    calls = iter(responses)

    def _fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        requests.append(request)
        try:
            item = next(calls)
        except StopIteration:
            item = responses[-1]
        if isinstance(item, Exception):
            raise item
        return _StubResponse(item)

    monkeypatch.setattr(espn_nba.urllib.request, "urlopen", _fake_urlopen)
    return requests


def _stub_schedule(abbrev: str) -> bytes:
    return json.dumps(
        _schedule_payload(abbrev, "Any Team", [])
    ).encode("utf-8")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the module-wide polite-spacing timestamp between tests."""
    monkeypatch.setattr(espn_nba, "_last_fetch_monotonic", None)
    monkeypatch.setattr(espn_nba.time, "sleep", lambda seconds: None)


def test_fetch_schedule_builds_url_and_validates_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = _install_urlopen(monkeypatch, [_stub_schedule("POR")])
    payload = espn_nba.fetch_team_schedule("POR", "2026-27", cache_dir=None)
    assert requests[0].full_url == (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        "/teams/22/schedule?season=2027&seasontype=2"
    )
    assert payload["requestedSeason"]["year"] == 2027
    summary_stub = json.dumps({"header": {}, "boxscore": {}}).encode()
    requests = _install_urlopen(monkeypatch, [summary_stub])
    espn_nba.fetch_game_summary("401909952", cache_dir=None)
    assert requests[0].full_url == (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        "/summary?event=401909952"
    )


def test_fetch_schedule_fail_closed_on_echo_and_team_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drift = _schedule_payload("POR", "Any Team", [])
    drift["requestedSeason"]["year"] = 2026
    _install_urlopen(monkeypatch, [json.dumps(drift).encode()])
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="does not echo year=2027"
    ):
        espn_nba.fetch_team_schedule("POR", cache_dir=None)
    swapped = _schedule_payload("PHX", "Any Team", [])
    _install_urlopen(monkeypatch, [json.dumps(swapped).encode()])
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="payload team block"
    ):
        espn_nba.fetch_team_schedule("POR", cache_dir=None)


@pytest.mark.parametrize("call", [
    lambda: espn_nba.fetch_team_schedule("XXX", cache_dir=None),
    lambda: espn_nba.fetch_team_schedule("POR", "2026_27", cache_dir=None),
    lambda: espn_nba.fetch_game_summary("not-an-id", cache_dir=None),
])
def test_fetch_rejects_bad_arguments(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_fetch_summary_requires_header_and_box(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_urlopen(monkeypatch, [b'{"gameInfo": {}}'])
    with pytest.raises(
        espn_nba.EspnNbaSchemaError, match="missing header/boxscore"
    ):
        espn_nba.fetch_game_summary("1", cache_dir=None)


def test_fetch_enforces_polite_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    summary_stub = json.dumps({"header": {}, "boxscore": {}}).encode()
    _install_urlopen(monkeypatch, [summary_stub, summary_stub])
    sleeps: list[float] = []
    monkeypatch.setattr(espn_nba.time, "sleep", sleeps.append)
    espn_nba.fetch_game_summary("1", cache_dir=None)
    assert sleeps == []  # first request: nothing to space against
    espn_nba._last_fetch_monotonic = time.monotonic()
    espn_nba.fetch_game_summary("2", cache_dir=None)
    assert len(sleeps) == 1
    assert 0.0 < sleeps[0] <= espn_nba.SLEEP_S
    assert espn_nba.SLEEP_S >= 1.2  # WP-NBA-1 policy floor


def test_fetch_retries_with_backoff_then_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_urlopen(
        monkeypatch, [OSError("boom"), OSError("boom"), _stub_schedule("POR")]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(espn_nba.time, "sleep", sleeps.append)
    payload = espn_nba.fetch_team_schedule("POR", cache_dir=None)
    assert payload["team"]["abbreviation"] == "POR"
    assert 5.0 in sleeps and 10.0 in sleeps


def test_fetch_gives_up_after_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    responses: list = [OSError("down")] * espn_nba.FETCH_ATTEMPTS
    requests = _install_urlopen(monkeypatch, responses)
    sleeps: list[float] = []
    monkeypatch.setattr(espn_nba.time, "sleep", sleeps.append)
    with pytest.raises(espn_nba.EspnNbaError, match="giving up"):
        espn_nba.fetch_game_summary("1", cache_dir=None)
    assert len(requests) == espn_nba.FETCH_ATTEMPTS
    assert 15.0 in sleeps


def test_fetch_rejects_non_json_and_non_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_urlopen(monkeypatch, [b"not json at all"])
    with pytest.raises(espn_nba.EspnNbaError, match="non-JSON"):
        espn_nba.fetch_game_summary("1", cache_dir=None)
    _install_urlopen(monkeypatch, [b"[1, 2]"])
    with pytest.raises(espn_nba.EspnNbaSchemaError, match="not an object"):
        espn_nba.fetch_game_summary("1", cache_dir=None)


# --------------------------------------------------------------------------
# cache layer: read-through, expiry, atomicity (tmp dirs, no network)
# --------------------------------------------------------------------------

def test_cache_round_trip_hits_without_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    requests = _install_urlopen(monkeypatch, [_stub_schedule("POR")])
    espn_nba.fetch_team_schedule("POR", cache_dir=tmp_path)
    cached = tmp_path / "schedule_POR_2027.json"
    assert cached.is_file()
    _install_urlopen(monkeypatch, [OSError("network is gone")])
    again = espn_nba.fetch_team_schedule("POR", cache_dir=tmp_path)
    assert again["team"]["abbreviation"] == "POR"
    assert len(requests) == 1  # second call never reached urlopen


def test_cache_schedule_expiry_and_summary_permanence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    summary = json.dumps({"header": {}, "boxscore": {}}).encode()
    requests = _install_urlopen(monkeypatch, [_stub_schedule("POR"), summary])
    espn_nba.fetch_team_schedule("POR", cache_dir=tmp_path)
    espn_nba.fetch_game_summary("4011", cache_dir=tmp_path)
    assert len(requests) == 2
    # age both files far beyond the schedule window
    old = time.time() - 10 * 365 * 24 * 3600
    for path in tmp_path.iterdir():
        os.utime(path, (old, old))
    _install_urlopen(monkeypatch, [_stub_schedule("POR")])
    espn_nba.fetch_game_summary("4011", cache_dir=tmp_path)  # still cached
    espn_nba.fetch_team_schedule("POR", cache_dir=tmp_path)  # refetched
    assert tmp_path.joinpath("summary_4011.json").is_file()
    # default schedule window is six hours, not ten years
    assert espn_nba.SCHEDULE_CACHE_MAX_AGE_S <= 6.5 * 3600


def test_cache_corrupt_entry_refetches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _install_urlopen(monkeypatch, [_stub_schedule("POR")])
    espn_nba.fetch_team_schedule("POR", cache_dir=tmp_path)
    (tmp_path / "schedule_POR_2027.json").write_text("{corrupt", encoding="utf-8")
    requests = _install_urlopen(monkeypatch, [_stub_schedule("POR")])
    payload = espn_nba.fetch_team_schedule("POR", cache_dir=tmp_path)
    assert payload["team"]["abbreviation"] == "POR"
    assert len(requests) == 1


def test_cache_disabled_without_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    requests = _install_urlopen(
        monkeypatch, [_stub_schedule("POR"), _stub_schedule("POR")]
    )
    espn_nba.fetch_team_schedule("POR", cache_dir=None)
    espn_nba.fetch_team_schedule("POR", cache_dir=None)
    assert len(requests) == 2
    assert list(tmp_path.iterdir()) == []


def test_fetch_nba_season_deduplicates_shared_games(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """One game appears in both teams' schedules; the season fetch must
    fetch each summary exactly once and de-duplicate the event."""
    event = _schedule_event("4011", "2026-10-22", "AAA", "BBB", 112, 105)
    schedules = {
        "AAA": _schedule_payload("AAA", "Alpha Aces", [event]),
        "BBB": _schedule_payload("BBB", "Beta Bears", [event]),
    }
    summary = _summary_payload(
        "4011", "2026-10-22", "AAA", "BBB", 112, 105, AAA_G1, BBB_G1,
    )
    calls: dict[str, int] = {"schedule": 0, "summary": 0}

    def fake_schedule(abbrev, season="2026-27", **kwargs):
        calls["schedule"] += 1
        return schedules[abbrev]

    def fake_summary(eid, **kwargs):
        calls["summary"] += 1
        return summary

    monkeypatch.setattr(espn_nba, "fetch_team_schedule", fake_schedule)
    monkeypatch.setattr(espn_nba, "fetch_game_summary", fake_summary)
    league = MappingProxyType({
        "AAA": (1, "Alpha Aces"), "BBB": (2, "Beta Bears"),
    })
    monkeypatch.setattr(espn_nba, "NBA_TEAMS", league)
    raw = espn_nba.fetch_nba_season("2026-27", cache_dir=tmp_path)
    assert calls == {"schedule": 2, "summary": 1}
    assert set(raw["schedules"]) == {"AAA", "BBB"}
    assert set(raw["summaries"]) == {"4011"}
    assert raw["season_year"] == 2027
    snapshot = espn_nba.build_snapshot(raw)
    assert len(snapshot["teams"]["AAA"]["games"]) == 1


# --------------------------------------------------------------------------
# CLI backfill entry point (mocked fetch, real file IO)
# --------------------------------------------------------------------------

def test_main_writes_validated_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys,
) -> None:
    league = MappingProxyType({
        "AAA": (1, "Alpha Aces"), "BBB": (2, "Beta Bears"),
    })
    monkeypatch.setattr(espn_nba, "NBA_TEAMS", league)
    monkeypatch.setattr(
        espn_nba, "fetch_nba_season", lambda *a, **k: _two_team_bundle()
    )
    out = tmp_path / "nba" / "snapshot_test.json"
    code = espn_nba.main([
        "--out", str(out), "--season", "2026-27",
        "--cache-dir", str(tmp_path / "cache"),
    ])
    assert code == 0
    reloaded = espn_nba.load_nba_snapshot(str(out))
    assert reloaded["source"] == "espn-nba"
    total_games = sum(len(t["games"]) for t in reloaded["teams"].values())
    assert total_games == 6  # 3 games x 2 team rows
    assert "teams=2 games=6" in capsys.readouterr().out
