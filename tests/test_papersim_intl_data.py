"""WP-INTL-1 tests: international-soccer snapshot adapter library module.

Four layers (house pattern of ``test_papersim_espn_nba.py``):

- Elo engine layer (pure, hand-computed): the probe-validated
  eloratings.net arithmetic replayed over 3-4 hand-computed matches —
  logistic expectation with the full +100 home advantage, the
  goal-difference multiplier 1.0 / 1.5 / (11+N)/8, the K bucket table
  (60/50/40/20) and its uniform override — plus determinism, monotone
  checkpoint dates and the fail-closed input matrix (unordered dates,
  negative / NaN / non-integral goals, bad flags).
- Transform layer (pure, fixture CSV/TSV slices):
  :func:`intl_data.build_snapshot` end to end on a synthetic corpus —
  frozen keys, self-computed final Elo equal to the last history
  checkpoint per team, venue/neutral typing — and the fail-closed
  matrix: header drift, wrong field count, duplicate rows, unordered
  dates, negative/NaN/fractional goals, team-count and World.tsv
  floors.
- Load/write layer: the frozen snapshot contract via round-trips
  through ``write_snapshot``/``load_intl_snapshot`` on tmp files
  (byte-deterministic output; NaN/Infinity literals, wrong source,
  extra/missing keys, bool/float goals, non-monotone matches,
  elo_history/teams mismatch all rejected).
- Fetch/cache layer (mocked urllib, no network): URL constants, the
  fetch-boundary header sniffs, read-through verbatim caching with
  atomic writes, polite 2.0 s spacing, retry/backoff.

Hand-computed fixtures: every expected Elo literal below was derived
with the eloratings.net formula by independent arithmetic (not by
calling the module), e.g. ``We(100) = 1/(10^(-0.25)+1) =
0.640064999803`` and ``We(0) = 0.5`` exactly.
"""

from __future__ import annotations

import json
import time
import urllib.error
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim import intl_data

# Hand-computed expectations (see module docstring):
WE_100 = 0.640064999803       # We at dr=+100 (home advantage, equal elos)
WE_65 = 0.592466230584        # We at dr=+65
M1_ITALY = 1500.0 + 20.0 * (1.0 - WE_100)      # 1507.198700003942
M1_FRANCE = 1500.0 - 20.0 * (1.0 - WE_100)     # 1492.801299996058
M2_WE = 0.520707672469        # We at dr = M1_ITALY - M1_FRANCE, neutral
M2_DELTA = 20.0 * (0.5 - M2_WE)                # -0.414153449379
M2_ITALY = M1_ITALY + M2_DELTA                 # 1506.784546554564
M2_FRANCE = M1_FRANCE - M2_DELTA               # 1493.215453445436
M3_WE = 0.621880176812        # We at dr = (M2_FRANCE+100) - M2_ITALY
M3_DELTA = 40.0 * 1.875 * (1.0 - M3_WE)        # 28.358986739081
M3_FRANCE = M2_FRANCE + M3_DELTA               # 1521.574440184517
M3_ITALY = M2_ITALY - M3_DELTA                 # 1478.425559815483
WIN_K20_HA100 = 20.0 * (1.0 - WE_100)          # 7.198700003942
WIN_K20_HA65 = 20.0 * (1.0 - WE_65)            # 8.150675388313
WIN_K20_NEUTRAL = 20.0 * 0.5                   # 10.0 exactly

RESULTS_HEADER_LINE = (
    "date,home_team,away_team,home_score,away_score,tournament,"
    "city,country,neutral"
)


def _match_dict(
    day: str,
    home: str,
    away: str,
    home_goals: int,
    away_goals: int,
    tournament: str = "Friendly",
    neutral: bool = False,
    venue: str | None = "Lima",
) -> dict:
    return {
        "date": day, "home": home, "away": away,
        "home_goals": home_goals, "away_goals": away_goals,
        "tournament": tournament, "neutral": neutral, "venue": venue,
    }


def _row(
    day: str,
    home: str,
    away: str,
    home_goals: int | str,
    away_goals: int | str,
    tournament: str = "Friendly",
    city: str = "Lima",
    country: str = "Peru",
    neutral: str = "FALSE",
) -> str:
    return (
        f"{day},{home},{away},{home_goals},{away_goals},{tournament},"
        f"{city},{country},{neutral}"
    )


def _world_tsv(rows: int = 150) -> str:
    # rank, rank, code, rating, history-padding columns
    return "\n".join(
        f"{rank}\t{rank}\tT{rank:02d}\t{1500 + rank}\t1\t{1500 + rank}"
        for rank in range(1, rows + 1)
    ) + "\n"


def _write_results_csv(tmp_path: Path, rows: list[str], header: str | None = None) -> Path:
    path = tmp_path / "results.csv"
    path.write_text(
        (header or RESULTS_HEADER_LINE) + "\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    return path


def _write_world_tsv(tmp_path: Path, content: str | None = None) -> Path:
    path = tmp_path / "World.tsv"
    path.write_text(
        content if content is not None else _world_tsv(),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------
# layer 1: Elo engine (pure, hand-computed)
# --------------------------------------------------------------------------

def _hand_series() -> list[dict]:
    """The 3-match hand-computed Italy/France series.

    M1 1900-01-01 Italy(H) 1-0 France, Friendly, not neutral (K=20,
    HA=100); M2 1900-01-02 Italy(H) 0-0 France, Friendly, NEUTRAL;
    M3 1900-01-03 France(H) 4-0 Italy, UEFA Nations League, not
    neutral (K=40, G=1.875).
    """
    return [
        _match_dict("1900-01-01", "Italy", "France", 1, 0),
        _match_dict("1900-01-02", "Italy", "France", 0, 0, neutral=True),
        _match_dict(
            "1900-01-03", "France", "Italy", 4, 0,
            tournament="UEFA Nations League",
        ),
    ]


def test_elo_hand_computed_checkpoints() -> None:
    checkpoints = intl_data.compute_elo_history(_hand_series())
    # two checkpoints per match, home side first
    assert checkpoints == [
        ("1900-01-01", "Italy", pytest.approx(M1_ITALY)),
        ("1900-01-01", "France", pytest.approx(M1_FRANCE)),
        ("1900-01-02", "Italy", pytest.approx(M2_ITALY)),
        ("1900-01-02", "France", pytest.approx(M2_FRANCE)),
        ("1900-01-03", "France", pytest.approx(M3_FRANCE)),
        ("1900-01-03", "Italy", pytest.approx(M3_ITALY)),
    ]


def test_elo_home_advantage_by_hand() -> None:
    home_win = _match_dict("1900-01-01", "Italy", "France", 1, 0)
    # neutral, equal elos: We=0.5 exactly -> winner gains K/2 = 10.000
    neutral = intl_data.compute_elo_history(
        [dict(home_win, neutral=True)]
    )
    assert neutral[0][2] == pytest.approx(1500.0 + WIN_K20_NEUTRAL)
    assert neutral[1][2] == pytest.approx(1500.0 - WIN_K20_NEUTRAL)
    # full +100 home advantage: We(100)=0.640064999803
    ha100 = intl_data.compute_elo_history([home_win])
    assert ha100[0][2] == pytest.approx(1500.0 + WIN_K20_HA100)
    assert ha100[1][2] == pytest.approx(1500.0 - WIN_K20_HA100)
    # home_adv=65.0 (the task sketch's constant) works verbatim
    ha65 = intl_data.compute_elo_history([home_win], home_adv=65.0)
    assert ha65[0][2] == pytest.approx(1500.0 + WIN_K20_HA65)
    # home_adv=0.0 reproduces the neutral expectation exactly
    ha0 = intl_data.compute_elo_history([home_win], home_adv=0.0)
    assert ha0 == neutral


def test_elo_k_buckets_and_uniform_override() -> None:
    win = lambda tournament: _match_dict(  # noqa: E731 - test-local
        "1900-01-01", "Italy", "France", 2, 1, tournament=tournament,
    )
    deltas = {
        tournament: intl_data.compute_elo_history([win(tournament)])[0][2]
        - 1500.0
        for tournament in (
            "Friendly", "UEFA Nations League", "FIFA World Cup qualification",
            "Copa América qualification", "CECAFA Cup",
            "UEFA Euro", "Gold Cup",
            "FIFA World Cup",
        )
    }
    we = WE_100  # 2-1 win, margin 1 -> G = 1.0, dr = 100
    assert deltas["Friendly"] == pytest.approx(20.0 * (1.0 - we))
    for label in (
        "UEFA Nations League", "FIFA World Cup qualification",
        "Copa América qualification", "CECAFA Cup",
    ):
        assert deltas[label] == pytest.approx(40.0 * (1.0 - we))
    for label in ("UEFA Euro", "Gold Cup"):
        assert deltas[label] == pytest.approx(50.0 * (1.0 - we))
    assert deltas["FIFA World Cup"] == pytest.approx(60.0 * (1.0 - we))
    # uniform k override ignores the tournament label
    overridden = intl_data.compute_elo_history(
        [win("FIFA World Cup")], k=40
    )
    assert overridden[0][2] - 1500.0 == pytest.approx(40.0 * (1.0 - we))


def test_elo_goal_difference_multiplier() -> None:
    def delta(home_goals: int, away_goals: int) -> float:
        checkpoints = intl_data.compute_elo_history([
            _match_dict(
                "1900-01-01", "Italy", "France", home_goals, away_goals,
                tournament="UEFA Nations League",
            )
        ])
        return checkpoints[0][2] - 1500.0

    one_nil = delta(1, 0)
    assert one_nil == pytest.approx(40.0 * 1.0 * (1.0 - WE_100))
    # margin 2 -> G = 1.5 exactly
    assert delta(2, 0) == pytest.approx(1.5 * one_nil)
    # margin 4 -> G = (11+4)/8 = 1.875 exactly
    assert delta(4, 0) == pytest.approx(1.875 * one_nil)
    # the trailing-goal side of a zero-sum update
    assert intl_data.compute_elo_history([
        _match_dict(
            "1900-01-01", "Italy", "France", 4, 0,
            tournament="UEFA Nations League",
        )
    ])[1][2] == pytest.approx(1500.0 - 1.875 * one_nil)


def test_elo_rejects_unordered_and_malformed_dates() -> None:
    unordered = [
        _match_dict("1900-01-02", "Italy", "France", 1, 0),
        _match_dict("1900-01-01", "France", "Italy", 1, 0),
    ]
    with pytest.raises(ValueError, match="unordered"):
        intl_data.compute_elo_history(unordered)
    malformed = [_match_dict("1900-1-1", "Italy", "France", 1, 0)]
    with pytest.raises(ValueError, match="malformed date"):
        intl_data.compute_elo_history(malformed)


@pytest.mark.parametrize(
    "home_goals,away_goals",
    [(2, -1), (-3, 0), (float("nan"), 1), (1, float("inf")), (1.5, 0)],
)
def test_elo_rejects_bad_goals(home_goals: float, away_goals: float) -> None:
    match = _match_dict("1900-01-01", "Italy", "France", 1, 0)
    match["home_goals"], match["away_goals"] = home_goals, away_goals
    with pytest.raises(ValueError, match="goals"):
        intl_data.compute_elo_history([match])


def test_elo_rejects_bad_teams_and_flags() -> None:
    with pytest.raises(ValueError, match="plays itself"):
        intl_data.compute_elo_history(
            [_match_dict("1900-01-01", "Italy", "Italy", 1, 0)]
        )
    match = _match_dict("1900-01-01", "Italy", "France", 1, 0)
    match["neutral"] = "TRUE"  # wire string, not a bool
    with pytest.raises(ValueError, match="neutral"):
        intl_data.compute_elo_history([match])
    match = _match_dict("1900-01-01", "Italy", "France", 1, 0)
    match["tournament"] = ""
    with pytest.raises(ValueError, match="tournament"):
        intl_data.compute_elo_history([match])


def test_elo_determinism_and_monotone_checkpoints() -> None:
    # deterministic 8-team round-robin slices over increasing dates
    teams = [f"T{index}" for index in range(8)]
    matches: list[dict] = []
    day = 0
    for round_index in range(3):
        for first in range(8):
            for second in range(first + 1, 8):
                day += 1
                matches.append(
                    _match_dict(
                        f"19{50 + round_index:02d}-0{(day % 9) + 1}-1{day % 9}",
                        teams[first], teams[second],
                        (first + round_index) % 4, second % 3,
                        tournament=(
                            "FIFA World Cup" if day % 5 == 0 else "Friendly"
                        ),
                        neutral=(day % 2 == 0),
                    )
                )
    matches.sort(key=lambda match: match["date"])
    first_run = intl_data.compute_elo_history(matches)
    second_run = intl_data.compute_elo_history(list(matches))
    assert first_run == second_run  # exact float equality: pure + no RNG
    dates = [checkpoint[0] for checkpoint in first_run]
    assert dates == sorted(dates)  # monotone (non-decreasing) checkpoints
    final = {team: elo for _date, team, elo in first_run}
    assert set(final) == set(teams)
    last_seen: dict[str, float] = {}
    for _date, team, elo in first_run:
        last_seen[team] = elo
    assert final == last_seen  # replay order => dict keeps last checkpoint


# --------------------------------------------------------------------------
# layer 2: build_snapshot on fixture slices (pure, fail-closed)
# --------------------------------------------------------------------------

def _fixture_rows() -> list[str]:
    return [
        _row("1900-01-01", "Italy", "France", 1, 0, "Friendly",
             "Milan", "Italy", "FALSE"),
        _row("1900-01-02", "Italy", "France", 0, 0, "Friendly",
             "Rome", "Italy", "TRUE"),
        _row("1900-01-03", "France", "Italy", 4, 0, "UEFA Nations League",
             "Paris", "France", "FALSE"),
        _row("1900-02-01", "Spain", "Portugal", 2, 2, "UEFA Euro",
             "", "Spain", "FALSE"),
        _row("1900-02-02", "Portugal", "Spain", 0, 1, "FIFA World Cup",
             "Lisbon", "Portugal", "FALSE"),
        _row("1900-03-01", "Brazil", "Argentina", 3, 1, "Copa América",
             "Rio de Janeiro", "Brazil", "FALSE"),
        _row("1900-03-02", "Argentina", "Brazil", 1, 1, "Friendly",
             "Buenos Aires", "Argentina", "TRUE"),
        _row("1900-04-01", "Germany", "Netherlands", 2, 0,
             "FIFA World Cup qualification", "Berlin", "Germany", "FALSE"),
        _row("1900-04-02", "Netherlands", "Germany", 3, 3, "Friendly",
             "Amsterdam", "Netherlands", "TRUE"),
        _row("1900-05-01", "England", "Scotland", 5, 0, "Friendly",
             "London", "England", "FALSE"),
    ]


def _build(tmp_path: Path, rows: list[str] | None = None, **kwargs):
    results = _write_results_csv(tmp_path, rows or _fixture_rows())
    world = _write_world_tsv(tmp_path)
    return intl_data.build_snapshot(
        results, world, min_teams=kwargs.pop("min_teams", 6), **kwargs
    )


def test_build_snapshot_fixture_content(tmp_path: Path) -> None:
    snapshot = intl_data.build_snapshot(
        _write_results_csv(tmp_path, _fixture_rows()),
        _write_world_tsv(tmp_path),
        min_teams=6,
    )
    assert set(snapshot) == {
        "generated_at", "source", "teams", "matches", "elo_history"
    }
    assert snapshot["source"] == "intl-martj42-eloratings"
    assert len(snapshot["matches"]) == 10
    assert set(snapshot["teams"]) == {
        "Italy", "France", "Spain", "Portugal", "Brazil", "Argentina",
        "Germany", "Netherlands", "England", "Scotland",
    }
    # spot-check wire->snapshot typing: neutral flag, empty city -> null venue
    first = snapshot["matches"][0]
    assert first["venue"] == "Milan" and first["neutral"] is False
    spain_draw = next(
        match for match in snapshot["matches"]
        if match["home"] == "Spain"
    )
    assert spain_draw["venue"] is None
    # self-Elo: hand-verified Italy/France tail + last-checkpoint invariant
    history_by_team: dict[str, float] = {}
    for entry in snapshot["elo_history"]:
        history_by_team[entry["team"]] = entry["elo"]
    assert history_by_team["Italy"] == pytest.approx(M3_ITALY)
    assert history_by_team["France"] == pytest.approx(M3_FRANCE)
    for name, block in snapshot["teams"].items():
        assert block["elo"] == history_by_team[name]
    # 2 checkpoints per match
    assert len(snapshot["elo_history"]) == 2 * len(snapshot["matches"])
    intl_data._validate_snapshot(snapshot, min_teams=6)  # passes as built


def test_build_snapshot_rejects_header_and_field_drift(tmp_path: Path) -> None:
    results = _write_results_csv(
        tmp_path, _fixture_rows(), header="date,home,away,home_score,away_score,tournament,city,country,neutral"
    )
    with pytest.raises(intl_data.IntlDataSchemaError, match="header"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path), min_teams=6)
    short = [
        _row("1900-01-01", "Italy", "France", 1, 0) + ",extra",
    ]
    results = _write_results_csv(tmp_path, short)
    with pytest.raises(intl_data.IntlDataSchemaError, match="fields"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path), min_teams=6)


def test_build_snapshot_duplicate_policy(tmp_path: Path) -> None:
    rows = _fixture_rows()
    # a duplicated ROW (same date + pair + score) is corruption: rejected
    rows.append(_row("1900-05-01", "England", "Scotland", 5, 0))
    results = _write_results_csv(tmp_path, rows)
    with pytest.raises(intl_data.IntlDataSchemaError, match="duplicate"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path), min_teams=6)
    # a genuine same-day double-header with a DIFFERENT score passes
    # (real corpus precedent: 1974-02-17 Tahiti v New Caledonia, 2-1 & 1-2)
    rows[-1] = _row("1900-05-01", "England", "Scotland", 2, 2)
    results = _write_results_csv(tmp_path, rows)
    snapshot = intl_data.build_snapshot(
        results, _write_world_tsv(tmp_path), min_teams=6
    )
    assert len(snapshot["matches"]) == 11
    same_day = [
        match for match in snapshot["matches"]
        if match["date"] == "1900-05-01" and match["home"] == "England"
    ]
    assert sorted(
        (match["home_goals"], match["away_goals"]) for match in same_day
    ) == [(2, 2), (5, 0)]


def test_build_snapshot_rejects_unordered_dates(tmp_path: Path) -> None:
    rows = [_row("1900-02-01", "Spain", "Portugal", 1, 1),
            _row("1900-01-31", "Spain", "Portugal", 2, 1)]
    results = _write_results_csv(tmp_path, rows)
    with pytest.raises(intl_data.IntlDataSchemaError, match="unordered"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path), min_teams=2)


@pytest.mark.parametrize("home_goals,away_goals", [("-1", "0"), ("nan", "1"), ("2.5", "1")])
def test_build_snapshot_rejects_bad_goals(tmp_path: Path, home_goals: str, away_goals: str) -> None:
    rows = [_row("1900-01-01", "Italy", "France", home_goals, away_goals)]
    results = _write_results_csv(tmp_path, rows)
    with pytest.raises(intl_data.IntlDataSchemaError, match="goals"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path), min_teams=2)


def test_build_snapshot_rejects_bad_rows(tmp_path: Path) -> None:
    self_play = [_row("1900-01-01", "Italy", "Italy", 1, 0)]
    with pytest.raises(intl_data.IntlDataSchemaError, match="plays itself"):
        intl_data.build_snapshot(
            _write_results_csv(tmp_path, self_play), _write_world_tsv(tmp_path), min_teams=2
        )
    bad_neutral = [_row("1900-01-01", "Italy", "France", 1, 0, neutral="maybe")]
    with pytest.raises(intl_data.IntlDataSchemaError, match="neutral"):
        intl_data.build_snapshot(
            _write_results_csv(tmp_path, bad_neutral), _write_world_tsv(tmp_path), min_teams=2
        )
    bad_date = [_row("1900-13-01", "Italy", "France", 1, 0)]
    with pytest.raises(intl_data.IntlDataSchemaError, match="date"):
        intl_data.build_snapshot(
            _write_results_csv(tmp_path, bad_date), _write_world_tsv(tmp_path), min_teams=2
        )


def test_build_snapshot_team_and_world_floors(tmp_path: Path) -> None:
    rows = [_row("1900-01-01", "Italy", "France", 1, 0)]
    results = _write_results_csv(tmp_path, rows)
    # corpus floor
    with pytest.raises(intl_data.IntlDataSchemaError, match="team"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path), min_teams=3)
    # World.tsv floor: too few teams
    with pytest.raises(intl_data.IntlDataSchemaError, match="World.tsv"):
        intl_data.build_snapshot(results, _write_world_tsv(tmp_path, "1\t1\tIT\t1900\t1\t1900\n"), min_teams=2)
    # World.tsv ratings: full-size table with one poisoned rating
    def _poisoned(rating: str) -> str:
        lines = _world_tsv(150).splitlines()
        lines[0] = f"1\t1\tT01\t{rating}\t1\t1501"
        return "\n".join(lines) + "\n"

    for bad in ("nan", "inf", "-5"):
        path = _write_world_tsv(tmp_path, _poisoned(bad))
        with pytest.raises(intl_data.IntlDataSchemaError, match="rating"):
            intl_data.build_snapshot(results, path, min_teams=2)
    ratings = intl_data.parse_world_tsv(_write_world_tsv(tmp_path))
    assert len(ratings) == 150 and ratings["T01"] == 1501


# --------------------------------------------------------------------------
# layer 3: load/write round-trips and the frozen contract on load
# --------------------------------------------------------------------------

def _fixture_snapshot(tmp_path: Path) -> dict:
    return intl_data.build_snapshot(
        _write_results_csv(tmp_path, _fixture_rows()),
        _write_world_tsv(tmp_path),
        min_teams=6,
    )


def test_write_load_roundtrip_deterministic_bytes(tmp_path: Path) -> None:
    snapshot = _fixture_snapshot(tmp_path)
    target = intl_data.write_snapshot(snapshot, tmp_path / "snap.json", min_teams=6)
    reloaded = intl_data.load_intl_snapshot(str(target), min_teams=6)
    assert reloaded == snapshot
    first_bytes = target.read_bytes()
    intl_data.write_snapshot(snapshot, tmp_path / "snap2.json", min_teams=6)
    assert (tmp_path / "snap2.json").read_bytes() == first_bytes  # deterministic
    # default 100-team floor rejects the 10-team fixture (fail-closed default)
    with pytest.raises(ValueError, match="floor"):
        intl_data.load_intl_snapshot(str(target))


def test_load_rejects_drift_matrix(tmp_path: Path) -> None:
    base = _fixture_snapshot(tmp_path)
    target = tmp_path / "snap.json"
    intl_data.write_snapshot(base, target, min_teams=6)

    def mutate(**changes):
        payload = json.loads(target.read_text())
        for key, value in changes.items():
            if value is ...:
                payload.pop(key, None)
            else:
                payload[key] = value
        drifted = tmp_path / "drift.json"
        # bypass write_snapshot (it would reject): write raw JSON text
        text = json.dumps(payload)
        drifted.write_text(text, encoding="utf-8")
        return drifted

    cases = {
        "wrong source": {"source": "someone-else"},
        "missing key": {"elo_history": ...},
        "extra key": {"unexpected": 1},
        "nan elo": {"teams": {**base["teams"], "Italy": {"elo": float("nan")}}},
        "infinity elo": {"teams": {**base["teams"], "Italy": {"elo": float("inf")}}},
        "bool goals": {"matches": [
            dict(base["matches"][0], home_goals=True), *base["matches"][1:]
        ]},
        "float goals": {"matches": [
            dict(base["matches"][0], home_goals=1.0), *base["matches"][1:]
        ]},
        "neutral not bool": {"matches": [
            dict(base["matches"][0], neutral=1), *base["matches"][1:]
        ]},
        "venue not str/null": {"matches": [
            dict(base["matches"][0], venue=7), *base["matches"][1:]
        ]},
        "unknown match team": {"matches": [
            dict(base["matches"][0], away="Atlantis"), *base["matches"][1:]
        ]},
        "unordered matches": {"matches": [
            *base["matches"][1:], base["matches"][0],
        ]},
        "duplicated match row": {"matches": [
            *base["matches"], base["matches"][-1],
        ]},
        "history teams mismatch": {"elo_history": [
            {"team": "Atlantis", "date": "1900-01-01", "elo": 1500.0},
            *base["elo_history"],
        ]},
        "history unordered": {"elo_history": [
            *base["elo_history"][2:], *base["elo_history"][:2],
        ]},
        "teams/history elo mismatch": {"teams": {
            **base["teams"], "Italy": {"elo": 1234.0},
        }},
    }
    for label, changes in cases.items():
        drifted = mutate(**changes)
        with pytest.raises(ValueError):
            intl_data.load_intl_snapshot(str(drifted), min_teams=6)


def test_nan_literal_rejected_on_load(tmp_path: Path) -> None:
    import re

    base = _fixture_snapshot(tmp_path)
    target = tmp_path / "snap.json"
    intl_data.write_snapshot(base, target, min_teams=6)
    text = target.read_text()
    # surgically swap ONLY Italy's elo number for a bare NaN literal
    # (write_snapshot would refuse; a hand-edited wire might not)
    poisoned, count = re.subn(
        r'("Italy":\{"elo":)[-0-9.eE]+\}', r"\1NaN}", text,
    )
    assert count == 1
    poisoned_path = tmp_path / "poisoned.json"
    poisoned_path.write_text(poisoned, encoding="utf-8")
    with pytest.raises(ValueError, match="finite"):
        intl_data.load_intl_snapshot(str(poisoned_path), min_teams=6)


# --------------------------------------------------------------------------
# layer 4: fetch/cache (mocked urllib, no network)
# --------------------------------------------------------------------------

class _Response:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _ControlledClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def time(self) -> float:
        return time.time()


def _install_urlopen(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[bytes],
    *,
    request_times: list[float] | None = None,
):
    calls: list[str] = []

    def _fake_urlopen(request, timeout):  # noqa: ANN001, ANN202
        calls.append(request.full_url)
        if request_times is not None:
            request_times.append(intl_data.time.monotonic())
        if not responses:
            raise AssertionError("unexpected extra network call")
        body = responses.pop(0)
        if isinstance(body, urllib.error.URLError):
            raise body
        return _Response(body)

    monkeypatch.setattr(intl_data.urllib.request, "urlopen", _fake_urlopen)
    return calls


def _no_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(intl_data, "_last_fetch_monotonic", None)
    monkeypatch.setattr(intl_data.time, "sleep", lambda seconds: None)


RESULTS_CSV_BYTES = (
    (RESULTS_HEADER_LINE + "\n"
     + _row("1900-01-01", "Italy", "France", 1, 0)
     + "\n").encode("utf-8")
)
WORLD_TSV_BYTES = _world_tsv(120).encode("utf-8")
LATEST_TSV_BYTES = (
    "2026\t11\t11\tBD\tLK\t4\t0\tSFF\t\t23\t946\t853\t+4\t-1\t193\t205\n"
).encode("utf-8")


def test_fetch_results_cache_and_sniff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_spacing(monkeypatch)
    calls = _install_urlopen(
        monkeypatch, [RESULTS_CSV_BYTES, RESULTS_CSV_BYTES]
    )
    path = intl_data.fetch_intl_results(cache_dir=tmp_path)
    assert path == tmp_path / "results.csv"
    assert path.read_bytes() == RESULTS_CSV_BYTES  # verbatim raw payload
    assert calls == [intl_data.RESULTS_URL]
    # cache hit: no second network call, stale window respected
    fresh = intl_data.fetch_intl_results(
        cache_dir=tmp_path, max_age_s=3600.0
    )
    assert fresh == path and len(calls) == 1
    time_machine = path.with_suffix(".moved")
    path.rename(time_machine)
    # NOTE: the responses list below already holds a second copy for the
    # expired-refetch network call.
    refetched = intl_data.fetch_intl_results(cache_dir=tmp_path, max_age_s=0.0)
    assert refetched == path and len(calls) == 2  # expired -> refetch
    # header drift fails closed and never lands in the cache
    html = b"<html>login page</html>"
    calls = _install_urlopen(monkeypatch, [html])
    with pytest.raises(intl_data.IntlDataSchemaError, match="header"):
        intl_data.fetch_intl_results(cache_dir=tmp_path / "sniff")
    assert not (tmp_path / "sniff" / "results.csv").exists()


def test_fetch_eloratings_current_caches_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_spacing(monkeypatch)
    calls = _install_urlopen(
        monkeypatch, [WORLD_TSV_BYTES, LATEST_TSV_BYTES]
    )
    paths = intl_data.fetch_eloratings_current(cache_dir=tmp_path)
    assert paths["world"] == tmp_path / "world.tsv"
    assert paths["world"].read_bytes() == WORLD_TSV_BYTES
    assert paths["latest"] == tmp_path / "latest.tsv"
    assert calls == [intl_data.WORLD_URL, intl_data.LATEST_URL]
    # second call fully cached
    intl_data.fetch_eloratings_current(cache_dir=tmp_path)
    assert len(calls) == 2
    # corrupt latest.tsv fails the sniff and is not cached
    calls = _install_urlopen(monkeypatch, [b"404 not found\n"])
    with pytest.raises(intl_data.IntlDataSchemaError):
        intl_data.fetch_eloratings_current(cache_dir=tmp_path / "bad")


def test_fetch_eloratings_current_politeness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _ControlledClock()
    monkeypatch.setattr(intl_data, "time", clock)
    monkeypatch.setattr(intl_data, "_last_fetch_monotonic", None)
    request_times: list[float] = []
    calls = _install_urlopen(
        monkeypatch, [WORLD_TSV_BYTES, LATEST_TSV_BYTES],
        request_times=request_times,
    )
    paths = intl_data.fetch_eloratings_current(cache_dir=tmp_path)
    assert paths["world"] == tmp_path / "world.tsv"
    assert paths["world"].read_bytes() == WORLD_TSV_BYTES
    assert paths["latest"] == tmp_path / "latest.tsv"
    assert paths["latest"].read_bytes() == LATEST_TSV_BYTES
    assert calls == [intl_data.WORLD_URL, intl_data.LATEST_URL]
    assert len(request_times) == 2
    assert request_times[1] - request_times[0] == intl_data.SLEEP_S
    assert clock.sleeps == [intl_data.SLEEP_S]


def test_fetch_politeness_and_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clock = _ControlledClock()
    monkeypatch.setattr(intl_data, "time", clock)
    monkeypatch.setattr(intl_data, "_last_fetch_monotonic", None)
    request_times: list[float] = []
    responses: list[object] = [
        urllib.error.URLError("boom"),  # attempt 1 fails
        RESULTS_CSV_BYTES,              # attempt 2 succeeds
    ]
    calls = _install_urlopen(monkeypatch, responses, request_times=request_times)
    path = intl_data.fetch_intl_results(cache_dir=tmp_path)
    assert calls == [intl_data.RESULTS_URL, intl_data.RESULTS_URL]
    assert path.read_bytes() == RESULTS_CSV_BYTES
    # The retry backoff already provides the minimum request spacing.
    assert len(request_times) == 2
    assert request_times[1] - request_times[0] >= intl_data.SLEEP_S
    assert request_times[1] - request_times[0] == 5.0
    assert clock.sleeps == [5.0]
    # transport gives up after FETCH_ATTEMPTS
    monkeypatch.setattr(intl_data, "_last_fetch_monotonic", None)
    failed_calls = _install_urlopen(
        monkeypatch,
        [urllib.error.URLError("down")] * intl_data.FETCH_ATTEMPTS,
    )
    with pytest.raises(intl_data.IntlDataError, match="giving up"):
        intl_data.fetch_intl_results(cache_dir=tmp_path / "dead")
    assert failed_calls == [intl_data.RESULTS_URL] * intl_data.FETCH_ATTEMPTS
