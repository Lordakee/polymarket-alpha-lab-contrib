"""WP-P3 Phase 2 tests: FotMob adapter library module.

Four layers:

- Fixture-excerpt layer: the frozen excerpt
  ``tests/fixtures/papersim/fotmob_championship_excerpt.json`` (10
  teams present in both season blocks, first 20 head-to-head dates per
  season, histories filtered to those dates) loads through
  :func:`polymarket_alpha_lab.papersim.fotmob.load_fotmob_snapshot`
  with the Understat wire contract intact: team count, xG presence,
  dates/history consistency, finite nonnegative xG values.
- Modeling layer: the excerpt drives the STANDARD domestic path with
  no FotMob-specific branching — ``xg.league_goal_fit`` reproduces the
  frozen prior-season base rates, ``xg.pair_lambdas`` prices a
  Championship domestic pair (and still refuses cross-league), and
  ``soccer_model.fixture_variants`` runs the full ten-variant sweep
  with true per-variant spread.
- Transform layer (pure, synthetic payloads): ``fotmob_to_understat``
  reproduces the Phase 1 wire shape — playoff/cancelled/unfinished
  filters, xG string dates rows, float histories, npxG fallback — and
  fails closed on season drift, malformed rows, team-table mismatch,
  the xG skip-rate ceiling and malformed xG values (codex review #8,
  2026-11-07: non-numeric/non-finite/negative rejected at the adapter
  boundary; 0 is valid; accepted snapshots stay byte-identical).
- Fetch layer (mocked, no network): URL construction, shared polite
  spacing (1 req / 1.3 s) and retry/backoff via stubbed ``urllib``.

Frozen anchors were computed once from the excerpt at generation time
(2026-11-04); the full validated snapshot lives server-side at
``/home/ubuntu/paper-sim/round31/raw/xg_fotmob_championship.json``
(720 matches, WP-P3 Phase 1 gates A-D PASS, gate E FAIL on 1X2 — see
``docs/paper-sim/usage.md``).
"""

from __future__ import annotations

import email.message
import json
import re
import tempfile
import time
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim import fotmob, soccer_model, xg

FIXTURES = Path(__file__).parent / "fixtures" / "papersim"
EXCERPT = FIXTURES / "fotmob_championship_excerpt.json"

# Frozen anchors (excerpt, computed 2026-11-04, full float precision).
FIT_2025 = (1.0055, 1.293, 1.14925)          # home_rate, away_rate, league_avg
FIT_2026 = (1.3105, 1.502, 1.40625)
PAIR_HOME_AWAY = (1.770768544249, 1.028041895669)  # Birmingham v Blackburn, w=.5 p=8
O25_MEDIAN = 0.532505
O25_RANGE = (0.495921, 0.731552)


@pytest.fixture(autouse=True)
def _reset_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the module-wide polite-spacing timestamp between tests."""
    monkeypatch.setattr(fotmob, "_last_fetch_monotonic", None)


class _StubResponse:
    """Minimal ``urlopen`` context manager returning fixed bytes.

    m2 A4 test-input upgrade (original assertions unchanged): carries
    HTTP-shaped ``headers`` (Content-Length framing), an
    ``amt``-bounded ``read`` and ``geturl()`` so the bounded transport
    (``fotmob._http_get_json`` via ``public_http.read_public_body``)
    accepts it exactly like a real ``http.client`` response.
    """

    def __init__(self, body: bytes, *, final_url: str | None = None) -> None:
        self._body = body
        self._final_url = final_url
        self.headers = email.message.Message()
        self.headers["Content-Length"] = str(len(body))

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def geturl(self) -> str | None:
        return self._final_url

    def read(self, amt: int | None = None) -> bytes:
        if amt is None or amt < 0:
            return self._body
        return self._body[:amt]


# --------------------------------------------------------------------------
# fixture excerpt: loader + wire contract
# --------------------------------------------------------------------------

def test_league_constants() -> None:
    champ = fotmob.FotMobLeague.CHAMPIONSHIP
    assert (champ.league_id, champ.league_key, champ.max_round, champ.team_count) == (
        48, "Championship", 46, 24,
    )
    ered = fotmob.FotMobLeague.EREDIVISIE
    assert (ered.league_id, ered.league_key, ered.max_round, ered.team_count) == (
        57, "Eredivisie", 34, 18,
    )


def test_loader_validates_excerpt_format() -> None:
    snapshot = fotmob.load_fotmob_snapshot(str(EXCERPT))
    assert set(snapshot) == {"Championship_2025", "Championship_2026"}
    for key, block in snapshot.items():
        assert len(block["teams"]) == 10
        dates = block["dates"]
        assert len(dates) == 20
        assert [row["datetime"] for row in dates] == sorted(
            row["datetime"] for row in dates
        )
        for row in dates:
            assert row["isResult"] is True
            float(row["xG"]["h"])
            float(row["xG"]["a"])
            float(row["goals"]["h"])
        for team in block["teams"].values():
            assert team["history"], f"{key}: {team['title']} has no history"
            for entry in team["history"]:
                for field in ("xG", "xGA", "npxG", "npxGA"):
                    assert isinstance(entry[field], float)
                assert entry["h_a"] in ("h", "a")
                assert entry["result"] in ("w", "d", "l")


def test_loader_rejects_malformed_snapshots(tmp_path: Path) -> None:
    root = tmp_path / "root.json"
    root.write_text(json.dumps([1, 2]))
    with pytest.raises(ValueError, match="root must be a JSON object"):
        fotmob.load_fotmob_snapshot(str(root))

    no_teams = tmp_path / "no_teams.json"
    no_teams.write_text(json.dumps({"Championship_2026": {"dates": []}}))
    with pytest.raises(ValueError, match="no teams mapping"):
        fotmob.load_fotmob_snapshot(str(no_teams))

    no_xg = tmp_path / "no_xg.json"
    no_xg.write_text(json.dumps(
        {"Championship_2026": {"teams": {"1": {"title": "X", "history": []}},
                               "dates": [{"isResult": True}]}}
    ))
    with pytest.raises(ValueError, match="without xG.h/xG.a"):
        fotmob.load_fotmob_snapshot(str(no_xg))


def _mini_snapshot(xg_h: object = "1.50", hist_xg: object = 1.5) -> dict:
    """Minimal single-block snapshot: one team, one history, one date."""
    return {"Championship_2026": {
        "teams": {"t1": {"title": "Birmingham City", "history": [{
            "h_a": "h", "xG": hist_xg, "xGA": 0.5, "npxG": 1.0,
            "npxGA": 0.5, "scored": 1, "missed": 0, "result": "w",
            "date": "2026-08-08 19:45:00",
        }]}},
        "dates": [{"id": "m1", "isResult": True,
                   "h": {"id": "t1", "title": "Birmingham City",
                         "short_title": "Bir"},
                   "a": {"id": "t2", "title": "Blackburn Rovers",
                         "short_title": "Bla"},
                   "goals": {"h": "1", "a": "0"},
                   "xG": {"h": xg_h, "a": "0.50"},
                   "datetime": "2026-08-08 19:45:00"}],
    }}


def test_loader_rejects_malformed_xg_values(tmp_path: Path) -> None:
    """Regression (codex review #8, 2026-11-07): xG value validation.

    The loader previously checked only xG.h/xG.a PRESENCE; "NaN"/"inf"
    strings in dates rows — and NaN/Infinity floats inside histories,
    which json.load parses from bare JSON literals — flowed into team
    ratings ahead of the downstream gate finite check. Pre-fetched
    Phase 1 files predate the transform-side check, so the load
    boundary validates values too (reject-only: accepted payloads are
    returned unmodified, byte-identical).
    """
    for i, bad in enumerate(("NaN", "inf", "-inf", "-1", -0.5)):
        path = tmp_path / f"dates_{i}.json"
        path.write_text(json.dumps(_mini_snapshot(xg_h=bad)))
        with pytest.raises(ValueError, match=r"dates xG\.h"):
            fotmob.load_fotmob_snapshot(str(path))
    for i, bad in enumerate(("NaN", float("inf"), -0.25, None)):
        path = tmp_path / f"hist_{i}.json"
        path.write_text(json.dumps(_mini_snapshot(hist_xg=bad)))
        with pytest.raises(ValueError, match=r"history xG"):
            fotmob.load_fotmob_snapshot(str(path))
    # zero is real xG: "0"/"0.0" strings and 0.0 floats load unmodified
    good = _mini_snapshot(xg_h="0", hist_xg=0.0)
    good["Championship_2026"]["dates"][0]["xG"]["a"] = "0.0"
    path = tmp_path / "good.json"
    path.write_text(json.dumps(good))
    assert fotmob.load_fotmob_snapshot(str(path)) == good


# --------------------------------------------------------------------------
# modeling: standard domestic path on the Championship excerpt
# --------------------------------------------------------------------------

def test_league_goal_fit_reasonable_rates() -> None:
    snapshot = fotmob.load_fotmob_snapshot(str(EXCERPT))
    fit = xg.league_goal_fit(snapshot, "Championship", "2025")
    assert (fit.home_rate, fit.away_rate, fit.league_avg) == pytest.approx(
        FIT_2025, abs=1e-9
    )
    assert fit.league_avg == pytest.approx((fit.home_rate + fit.away_rate) / 2.0)
    fit_current = xg.league_goal_fit(snapshot, "Championship", "2026")
    assert (fit_current.home_rate, fit_current.away_rate) == pytest.approx(
        FIT_2026[:2], abs=1e-9
    )
    # Sanity band: Championship is a ~1.3-goal-per-side league; a 20-match
    # excerpt may wobble but never outside this window.
    for rate in (fit.home_rate, fit.away_rate, fit_current.home_rate,
                 fit_current.away_rate):
        assert 0.3 < rate < 2.5


def test_championship_is_a_known_domestic_league() -> None:
    assert "Championship" in xg.DOMESTIC_LEAGUES
    assert "Championship" not in xg.UNDERSTAT_LEAGUES
    assert xg.DOMESTIC_LEAGUES > xg.UNDERSTAT_LEAGUES
    snapshot = fotmob.load_fotmob_snapshot(str(EXCERPT))
    registry = xg.team_league_registry(snapshot, season="2026")
    assert registry["Birmingham City"] == frozenset({"Championship"})


def test_pair_lambdas_championship_domestic_pair() -> None:
    snapshot = fotmob.load_fotmob_snapshot(str(EXCERPT))
    lambdas = xg.pair_lambdas(
        snapshot, "Birmingham City", "Championship",
        "Blackburn Rovers", "Championship", last_weight=0.5, prior_games=8.0,
    )
    assert lambdas is not None
    assert lambdas == pytest.approx(PAIR_HOME_AWAY, abs=1e-9)
    assert all(rate > 0.0 for rate in lambdas)


def test_pair_lambdas_cross_league_guard_still_refuses_championship() -> None:
    snapshot = fotmob.load_fotmob_snapshot(str(EXCERPT))
    assert xg.pair_lambdas(
        snapshot, "Birmingham City", "Championship",
        "Chelsea", "EPL", last_weight=0.5, prior_games=8.0,
    ) is None


def test_standard_ten_variant_sweep_integration() -> None:
    snapshot = fotmob.load_fotmob_snapshot(str(EXCERPT))
    variants = soccer_model.fixture_variants(
        snapshot, "Birmingham City", "Championship",
        "Blackburn Rovers", "Championship",
    )
    assert variants is not None
    assert [v.spec.name for v in variants] == list(soccer_model.SWEEP_NAMES)
    for variant in variants:
        assert variant.lambdas[0] > 0.0 and variant.lambdas[1] > 0.0
        outputs = variant.outputs
        assert outputs.home_win + outputs.draw + outputs.away_win == pytest.approx(1.0)
        assert sum(outputs.totals) == pytest.approx(1.0)
    quotes = [soccer_model.over_probability(v.outputs, 2.5) for v in variants]
    assert soccer_model.median(quotes) == pytest.approx(O25_MEDIAN, abs=1e-6)
    assert min(quotes) == pytest.approx(O25_RANGE[0], abs=1e-6)
    assert max(quotes) == pytest.approx(O25_RANGE[1], abs=1e-6)
    # True sweep variance: the rating-blend/shrink dimensions re-derive
    # per-variant lambdas, so the quotes must NOT all coincide.
    assert len(set(quotes)) > 1

    candidate = soccer_model.candidate_from_variants(
        snapshot, "Birmingham City", "Championship",
        "Blackburn Rovers", "Championship", 2.5,
        "Birmingham City vs Blackburn Rovers", "m1", 0.5,
    )
    assert candidate is not None
    assert len(candidate.qs_variants) == 10
    assert candidate.model_median == pytest.approx(O25_MEDIAN, abs=1e-6)
    assert candidate.model_range == pytest.approx(O25_RANGE, abs=1e-6)


# --------------------------------------------------------------------------
# transform: synthetic payloads (pure)
# --------------------------------------------------------------------------

def _match(
    mid: str,
    round_no: str,
    home_id: str,
    away_id: str,
    utc: str,
    *,
    finished: bool = True,
    cancelled: bool = False,
    abandoned: bool = False,
) -> dict:
    status: dict = {"finished": finished, "utcTime": utc}
    if cancelled:
        status["reason"] = {"longKey": "matchCancelled", "shortKey": "CANC"}
    if abandoned:
        # Real cached shape (codex review #5, 2026-11-04): abandoned games
        # carry cancelled=true AND finished=true with longKey 'aborted',
        # e.g. Blackburn-Ipswich 4825094 alongside its replay 5008942.
        status["finished"] = True
        status["cancelled"] = True
        status["reason"] = {"longKey": "aborted", "shortKey": "ABD"}
    names = {"t1": "Birmingham City", "t2": "Blackburn Rovers"}
    return {
        "id": mid,
        "round": round_no,
        "status": status,
        "home": {"id": home_id, "name": names[home_id], "shortName": names[home_id][:3]},
        "away": {"id": away_id, "name": names[away_id], "shortName": names[away_id][:3]},
    }


def _details(score_h: int, score_a: int, xg_h: str, xg_a: str,
             npxg: tuple[str, str] | None = None) -> dict:
    rows = [{"title": "Expected goals (xG)", "stats": [xg_h, xg_a]}]
    if npxg is not None:
        rows.append({"title": "xG non-penalty", "stats": list(npxg)})
    return {
        "header": {"teams": [{"score": score_h}, {"score": score_a}]},
        "content": {"stats": {"Periods": {"All": {"stats": [{"stats": rows}]}}}},
    }


def _league_payload(matches: list, selected: str = "2026/2027") -> dict:
    return {"details": {"selectedSeason": selected},
            "fixtures": {"allMatches": matches}}


def _two_match_raw() -> dict:
    matches = [
        _match("m1", "1", "t1", "t2", "2026-08-08T19:45:00.000Z"),
        _match("m2", "10", "t2", "t1", "2026-10-02T14:00:00.000Z"),
        # excluded buckets: playoff round, unfinished, cancelled
        _match("m3", "1/2", "t1", "t2", "2026-05-10T19:45:00.000Z"),
        _match("m4", "2", "t1", "t2", "2026-08-15T11:00:00.000Z", finished=False),
        _match("m5", "3", "t2", "t1", "2026-08-22T11:00:00.000Z", cancelled=True),
    ]
    return {
        "fixtures": _league_payload(matches),
        "details": {
            "m1": _details(2, 1, "1.50", "0.75", npxg=("1.20", "0.60")),
            "m2": _details(0, 0, "0.90", "1.10"),  # no npxG row -> xG fallback
        },
    }


def test_transform_builds_understat_block() -> None:
    snapshot = fotmob.fotmob_to_understat(_two_match_raw(), "Championship", "2026")
    assert set(snapshot) == {"Championship_2026"}
    block = snapshot["Championship_2026"]
    assert set(block["teams"]) == {"t1", "t2"}
    assert [row["id"] for row in block["dates"]] == ["m1", "m2"]  # sorted, filtered

    first = block["dates"][0]
    assert first["isResult"] is True
    assert first["xG"] == {"h": "1.50", "a": "0.75"}
    assert first["goals"] == {"h": "2", "a": "1"}
    assert first["datetime"] == "2026-08-08 19:45:00"

    home_history = block["teams"]["t1"]["history"][0]
    assert home_history == {
        "h_a": "h", "xG": 1.5, "xGA": 0.75, "npxG": 1.2, "npxGA": 0.6,
        "scored": 2, "missed": 1, "result": "w", "date": "2026-08-08 19:45:00",
    }
    # away side of the same match: mirrored values, away result code
    away_history = block["teams"]["t2"]["history"][0]
    assert away_history["h_a"] == "a"
    assert away_history["xG"] == 0.75 and away_history["xGA"] == 1.5
    assert away_history["result"] == "l"
    # npxG fallback: match without the non-penalty row reuses the xG pair
    fallback = block["teams"]["t2"]["history"][1]
    assert fallback["npxG"] == fallback["xG"] == 0.9
    # the emitted block feeds the same wire loader as the real snapshot
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "block.json"
        path.write_text(json.dumps(snapshot))
        reloaded = fotmob.load_fotmob_snapshot(str(path))
    assert set(reloaded) == {"Championship_2026"}


def test_abandoned_flag_excluded_but_replay_kept() -> None:
    """Regression (codex review #5, 2026-11-04).

    Abandoned FotMob fixtures have ``status.cancelled=true`` with reason
    ``longKey='aborted'`` while ``finished`` is ALSO true. The pre-fix
    text-only ``'cancel'`` filter kept them, so an abandoned game and its
    replay both landed in the completed history (555 prior-season matches
    instead of 552; Blackburn on 48 games instead of 46). The abandoned
    original must be excluded and only the replay kept.
    """
    matches = [
        _match("m_abd", "5", "t1", "t2", "2026-09-12T19:45:00.000Z", abandoned=True),
        _match("m_replay", "5", "t1", "t2", "2026-10-01T19:45:00.000Z"),
    ]
    raw = {
        "fixtures": _league_payload(matches),
        "details": {
            # abandoned row deliberately has full details: the filter must
            # reject it on status flags alone, not on missing details.
            "m_abd": _details(1, 1, "0.80", "0.70"),
            "m_replay": _details(2, 1, "1.50", "0.75"),
        },
    }
    snapshot = fotmob.fotmob_to_understat(raw, "Championship", "2026")
    block = snapshot["Championship_2026"]
    assert [row["id"] for row in block["dates"]] == ["m_replay"]
    # exactly one completed game in the history, from the replay
    assert len(block["teams"]["t1"]["history"]) == 1
    assert block["teams"]["t1"]["history"][0]["scored"] == 2

    # the boolean flag alone (no reason block) must also exclude
    matches[0]["status"].pop("reason")
    snapshot2 = fotmob.fotmob_to_understat(
        {**raw, "fixtures": _league_payload(list(matches))}, "Championship", "2026"
    )
    assert [row["id"] for row in snapshot2["Championship_2026"]["dates"]] == ["m_replay"]

    # ...and the reason text alone ('aborted' longKey, no boolean) as well
    matches[0]["status"].pop("cancelled")
    matches[0]["status"]["reason"] = {"longKey": "aborted", "shortKey": "ABD"}
    snapshot3 = fotmob.fotmob_to_understat(
        {**raw, "fixtures": _league_payload(list(matches))}, "Championship", "2026"
    )
    assert [row["id"] for row in snapshot3["Championship_2026"]["dates"]] == ["m_replay"]


def test_transform_league_member_constants() -> None:
    # A FotMobLeague member threads its round/team constants in: the
    # 2-team synthetic table fails the Championship 24-team check.
    with pytest.raises(fotmob.FotMobSchemaError, match="expected 24 teams"):
        fotmob.fotmob_to_understat(
            _two_match_raw(), fotmob.FotMobLeague.CHAMPIONSHIP, "2026"
        )
    # Bare string key: no strict team-count check (Phase 1 default).
    snapshot = fotmob.fotmob_to_understat(_two_match_raw(), "Championship", "2026")
    assert len(snapshot["Championship_2026"]["teams"]) == 2


def test_transform_skip_accounting() -> None:
    raw = _two_match_raw()
    del raw["details"]["m2"]  # one of two kept matches now lacks details
    with pytest.raises(fotmob.FotMobSchemaError, match="fail-closed"):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")
    # A raised ceiling lets the single usable match through.
    snapshot = fotmob.fotmob_to_understat(
        raw, "Championship", "2026", max_skip_rate=0.5
    )
    assert [row["id"] for row in snapshot["Championship_2026"]["dates"]] == ["m1"]
    # Zero usable matches always fail closed, regardless of the ceiling.
    raw["details"] = {}
    with pytest.raises(fotmob.FotMobSchemaError):
        fotmob.fotmob_to_understat(
            raw, "Championship", "2026", max_skip_rate=1.0
        )


def test_transform_fail_closed_on_schema_drift() -> None:
    raw = _two_match_raw()
    raw["fixtures"]["details"]["selectedSeason"] = "1999/2000"
    with pytest.raises(fotmob.FotMobSchemaError, match="season drift"):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")

    raw = _two_match_raw()
    raw["fixtures"]["fixtures"]["allMatches"][0].pop("status")
    with pytest.raises(fotmob.FotMobSchemaError, match="malformed fixture row"):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")

    with pytest.raises(fotmob.FotMobSchemaError, match="integer year"):
        fotmob.fotmob_to_understat(_two_match_raw(), "Championship", "20x6")


@pytest.mark.parametrize("bad", ["NaN", "inf", "-inf", "-0.5", "-2"])
def test_transform_rejects_nonfinite_and_negative_xg(bad: str) -> None:
    """Regression (codex review #8, 2026-11-07): xG value validation.

    _build_block previously converted xG wire strings with a bare
    float(), so FotMob "NaN"/"inf" content entered team histories and
    ratings before the downstream gate finite check ever ran. Each bad
    home xG is rejected with FotMobSchemaError naming the match and
    the offending wire value; the valid m2 row does not rescue it.
    """
    raw = _two_match_raw()
    raw["details"]["m1"] = _details(2, 1, bad, "0.75")
    with pytest.raises(
        fotmob.FotMobSchemaError, match=rf"m1.*home xG.*{re.escape(bad)}"
    ):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")


def test_transform_bad_row_among_good_rows_fails_loudly() -> None:
    """Fail-closed policy choice for mixed payloads (codex review #8).

    One malformed xG row among good rows poisons the whole transform:
    it is treated like a malformed fixture ROW (immediate
    FotMobSchemaError, no block emitted), not like an xG-missing row
    (skip-counted under MAX_SKIP_RATE). A present-but-corrupt value
    signals upstream schema drift; skipping it would silently shrink
    the season and could still pass under the skip-rate ceiling.
    """
    raw = _two_match_raw()
    raw["details"]["m2"] = _details(0, 0, "NaN", "1.10")  # m1 stays valid
    with pytest.raises(fotmob.FotMobSchemaError, match="m2.*home xG"):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")


def test_transform_rejects_nonnumeric_xg_content() -> None:
    # Non-null but non-numeric strings (str(True), a bare minus sign)
    # reach the same boundary check through the not-numeric branch.
    for non_numeric in ("True", "", "-"):
        raw = _two_match_raw()
        raw["details"]["m1"] = _details(2, 1, "1.50", non_numeric)
        with pytest.raises(
            fotmob.FotMobSchemaError, match=rf"m1.*away xG.*not numeric"
        ):
            fotmob.fotmob_to_understat(raw, "Championship", "2026")


def test_transform_xg_check_covers_away_side_and_npxg() -> None:
    # the non-penalty row (and its xG fallback) is guarded too
    raw = _two_match_raw()
    raw["details"]["m1"] = _details(2, 1, "1.50", "0.75", npxg=("nan", "0.60"))
    with pytest.raises(fotmob.FotMobSchemaError, match="m1.*home npxG"):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")
    raw = _two_match_raw()
    raw["details"]["m2"] = _details(0, 0, "0.90", "Infinity")
    with pytest.raises(fotmob.FotMobSchemaError, match="m2.*away xG"):
        fotmob.fotmob_to_understat(raw, "Championship", "2026")


def test_transform_accepts_zero_and_exact_xg_strings() -> None:
    """0 / "0.0" are valid (a side can generate no expected goals);
    accepted values convert to exactly float(<wire string>) and the
    dates-row wire strings are preserved VERBATIM — valid snapshots
    stay byte-identical, the check only rejects malformed data."""
    raw = _two_match_raw()
    raw["details"]["m1"] = _details(2, 1, "0", "0.0", npxg=("0", "3"))
    raw["details"]["m2"] = _details(0, 0, "2.47", "1")
    snapshot = fotmob.fotmob_to_understat(raw, "Championship", "2026")
    block = snapshot["Championship_2026"]
    assert [row["id"] for row in block["dates"]] == ["m1", "m2"]
    # verbatim wire strings, no reformatting of accepted values
    assert block["dates"][0]["xG"] == {"h": "0", "a": "0.0"}
    assert block["dates"][1]["xG"] == {"h": "2.47", "a": "1"}
    home = block["teams"]["t1"]["history"][0]  # m1 home side
    assert (home["xG"], home["xGA"], home["npxG"], home["npxGA"]) == (
        0.0, 0.0, 0.0, 3.0,
    )
    later = block["teams"]["t2"]["history"][1]  # m2: t2 hosts t1
    assert later["xG"] == 2.47 and later["xGA"] == 1.0
    assert later["npxG"] == 2.47  # npxG fallback reuses the xG pair


# --------------------------------------------------------------------------
# fetch: mocked urllib, no network
# --------------------------------------------------------------------------

def _install_urlopen(monkeypatch: pytest.MonkeyPatch, responses: list) -> list:
    """Serve ``responses`` (bytes or Exception) per call, repeating the
    last item when the retry loop asks for more; record every request."""
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
        return _StubResponse(item, final_url=request.full_url)

    monkeypatch.setattr(fotmob.urllib.request, "urlopen", _fake_urlopen)
    return requests


def test_fetch_league_builds_url_and_returns_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fotmob.time, "sleep", lambda seconds: None)
    requests = _install_urlopen(monkeypatch, [b'{"details": {}, "fixtures": {}}'])
    payload = fotmob.fetch_fotmob_league(48, "2025/2026", allow_public_fetch=True)
    assert payload == {"details": {}, "fixtures": {}}
    assert requests[0].full_url == (
        "https://www.fotmob.com/api/data/leagues?id=48&season=2025%2F2026"
    )
    requests = _install_urlopen(monkeypatch, [b"{}"])
    fotmob.fetch_fotmob_league(
        fotmob.FotMobLeague.CHAMPIONSHIP, allow_public_fetch=True
    )
    assert requests[0].full_url == "https://www.fotmob.com/api/data/leagues?id=48"
    requests = _install_urlopen(monkeypatch, [b"{}"])
    fotmob.fetch_match_details("5836754", allow_public_fetch=True)
    assert requests[0].full_url == (
        "https://www.fotmob.com/api/data/matchDetails?matchId=5836754"
    )


def test_fetch_enforces_polite_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_urlopen(monkeypatch, [b"{}", b"{}"])
    sleeps: list[float] = []
    monkeypatch.setattr(fotmob.time, "sleep", sleeps.append)
    fotmob.fetch_match_details("1", allow_public_fetch=True)
    assert sleeps == []  # first request: nothing to space against
    fotmob._last_fetch_monotonic = time.monotonic()  # a request just left
    fotmob.fetch_match_details("2", allow_public_fetch=True)
    assert len(sleeps) == 1
    assert 0.0 < sleeps[0] <= fotmob.SLEEP_S


def test_fetch_retries_with_backoff_then_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_urlopen(
        monkeypatch, [OSError("boom"), OSError("boom"), b'{"ok": 1}']
    )
    sleeps: list[float] = []
    monkeypatch.setattr(fotmob.time, "sleep", sleeps.append)
    assert fotmob.fetch_match_details("1", allow_public_fetch=True) == {"ok": 1}
    # backoffs are exactly 5s then 10s; any polite-spacing sleeps are
    # bounded by SLEEP_S.
    assert 5.0 in sleeps and 10.0 in sleeps
    assert all(sleep <= fotmob.SLEEP_S or sleep in (5.0, 10.0, 15.0) for sleep in sleeps)


def test_fetch_gives_up_after_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    responses: list = [OSError("down")] * fotmob.FETCH_ATTEMPTS
    requests = _install_urlopen(monkeypatch, responses)
    sleeps: list[float] = []
    monkeypatch.setattr(fotmob.time, "sleep", sleeps.append)
    with pytest.raises(fotmob.FotMobError, match="giving up"):
        fotmob.fetch_match_details("1", allow_public_fetch=True)
    assert len(requests) == fotmob.FETCH_ATTEMPTS
    assert 15.0 in sleeps


def test_fetch_rejects_non_object_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fotmob.time, "sleep", lambda seconds: None)
    _install_urlopen(monkeypatch, [b"[1, 2]"])
    with pytest.raises(fotmob.FotMobSchemaError, match="not an object"):
        fotmob.fetch_match_details("1", allow_public_fetch=True)
    _install_urlopen(monkeypatch, [b"not json at all"])
    with pytest.raises(fotmob.FotMobError, match="non-JSON"):
        fotmob.fetch_match_details("1", allow_public_fetch=True)
