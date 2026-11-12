"""International-soccer snapshot adapter: martj42 results + eloratings TSVs.

Single responsibility: wrap the two GREEN sources of the round-47
feasibility study (``paper-sim/round47/nl_elo_feasibility.md``,
server-side, 2026-11-12) behind a polite, fail-closed fetch layer with
an on-disk raw cache, and transform them into the FROZEN international
snapshot consumed by the papersim national-team model. This is the
WP-INTL-1 data adapter, paper-only: no credentials, no database, no
writes outside its cache/output paths.

Sources (both verified GREEN from the ops host in the study's probe,
artifacts in ``round47/probe/``):

1. ``martj42/international_results`` results.csv via raw.githubusercontent
   (49,940 matches 1872-11-30 -> 2026-10-06; columns date, home_team,
   away_team, home_score, away_score, tournament, city, country,
   neutral; 337 federation-agnostic team names).
2. ``eloratings.net`` root TSVs — ``World.tsv`` (243 current team
   ratings; the old ``/World/Elo_Ratings`` HTML scheme is 404) and
   ``latest.tsv`` (recent results carrying PRE-match Elo per game,
   cached as the study's cross-check supplement; not consumed by the
   snapshot build).

House pattern: this module mirrors :mod:`polymarket_alpha_lab.papersim.
espn_nba` (stdlib-only, module-wide polite spacing, retry/backoff
transport, atomic raw cache, fail-closed schema validation with precise
errors, finite/nonnegative value discipline). Raw payloads are cached
verbatim on the ops host under ``~/paper-sim/intl/`` by :func:`main`
(the backfill CLI) — never inside tests, which run on fixture slices.

Snapshot contract (FROZEN — do not deviate; the model is built against
this exact JSON)::

    {"generated_at": "<iso8601>", "source": "intl-martj42-eloratings",
     "teams": {"<name, e.g. Italy>": {"elo": float}},
     "matches": [{"date": "YYYY-MM-DD", "home": str, "away": str,
                  "home_goals": int, "away_goals": int,
                  "tournament": str, "neutral": bool,
                  "venue": str|null}],
     "elo_history": [{"team": str, "date": "YYYY-MM-DD", "elo": float}]}

Design decisions (documented split):

- ``venue`` is the match CITY from martj42 (the venue city; ``null``
  when the column is empty) — the schema's single venue slot, not the
  ``country`` column (kept in the raw CSV, not the snapshot).
- ``teams[...]["elo"]`` and ``elo_history`` are the SELF-COMPUTED Elo of
  :func:`compute_elo_history` over the full corpus, not eloratings.net's
  current table. Rationale (study sections 2/#10 and 4): the study's
  model prices off self-Elo DIFFERENCES; World.tsv sits ~+62 points
  above self-Elo with a near-uniform offset, so mixing the two scales
  would corrupt differences; and World.tsv covers only 243 current
  teams while the corpus carries 337 (walk-forward needs them all).
  World.tsv is still a build INPUT: :func:`build_snapshot` parses and
  structurally validates it (>= :data:`MIN_WORLD_TEAMS` teams, finite
  nonnegative ratings, unique codes) so a truncated or wrong-column
  fetch fails closed. Keeping the two scales coherent is exactly why
  ``latest.tsv`` (pre-match Elo per game) is cached alongside for ops
  cross-checks but never merged into the snapshot.

Elo engine (probe-validated, Spearman rho=0.9961 vs eloratings.net
across 35 UEFA teams, ``round47/probe/elo_fit_out.txt``): classic
eloratings.net arithmetic — logistic expectation
``We = 1 / (10^(-dr/400) + 1)`` with ``dr`` including the full home
advantage for the home side when ``neutral`` is false, zero-sum update
``+/- K * G * (W - We)`` per match, goal-difference multiplier ``G``
of 1.0 (``|gd| <= 1``), 1.5 (``|gd| == 2``) or ``(11 + |gd|) / 8``
(``|gd| >= 3``), every team starting at 1500. K defaults follow the
study's rating-layer design — :data:`K_WORLD_CUP_FINALS` 60 ("FIFA
World Cup"), :data:`K_CONTINENTAL_FINALS` 50 (UEFA Euro, Copa América,
AFC Asian Cup, African Cup of Nations, Gold Cup, CONCACAF Championship,
Oceania Nations Cup), :data:`K_STANDARD` 40 (UEFA Nations League, every
qualifier and every other competitive tournament), :data:`K_FRIENDLY`
20 ("Friendly") — and home advantage defaults to
:data:`HOME_ADVANTAGE` 100. Both are configurable per call: ``k`` takes
a uniform float override, ``home_adv`` any float (the task sketch's
``k=40, home_adv=65.0`` reads work verbatim; the DEFAULTS are the
probe's constants because they are what reproduced rho=0.996).

Fail-closed contract: :func:`build_snapshot` refuses to emit a snapshot
on any structural drift — header change, wrong field count, malformed
or non-iso dates, non-monotone (unordered) dates, negative / NaN /
non-integral goals, a team playing itself, bad neutral flags, DUPLICATED
rows (same date + pair + score; genuine same-day double-headers with
different scores pass — the real corpus carries exactly one), fewer than
:data:`MIN_TEAMS` distinct
teams, or an eloratings World.tsv below :data:`MIN_WORLD_TEAMS` teams
with non-finite ratings. :func:`load_intl_snapshot` re-validates the
same frozen contract on load (including bare ``NaN`` / ``Infinity``
JSON literals, and the invariant that each team's snapshot Elo equals
its last ``elo_history`` checkpoint).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

__all__ = [
    "CONTINENTAL_FINALS",
    "DEFAULT_CACHE_DIR",
    "FETCH_ATTEMPTS",
    "FETCH_TIMEOUT_S",
    "HOME_ADVANTAGE",
    "INITIAL_ELO",
    "K_CONTINENTAL_FINALS",
    "K_FRIENDLY",
    "K_STANDARD",
    "K_WORLD_CUP_FINALS",
    "LATEST_URL",
    "MIN_TEAMS",
    "MIN_WORLD_TEAMS",
    "RESULTS_HEADER",
    "RESULTS_URL",
    "SLEEP_S",
    "SOURCE_KEY",
    "USER_AGENT",
    "WORLD_URL",
    "IntlDataError",
    "IntlDataSchemaError",
    "build_snapshot",
    "compute_elo_history",
    "fetch_eloratings_current",
    "fetch_intl_results",
    "load_intl_snapshot",
    "main",
    "parse_world_tsv",
    "read_intl_matches",
    "tournament_k",
    "write_snapshot",
]

#: martj42/international_results results.csv (raw, verbatim; the study
#: probe verified 49,940 matches through 2026-10-06, last upstream
#: commit 2026-10-31).
RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)

#: eloratings.net current world ratings TSV (243 teams; root TSV scheme
#: discovered in the study — the old ``/World/Elo_Ratings`` HTML is 404).
WORLD_URL = "https://www.eloratings.net/World.tsv"

#: eloratings.net recent-results TSV (~4 months, carries PRE-match Elo
#: per game; cached as the study's cross-check supplement).
LATEST_URL = "https://www.eloratings.net/latest.tsv"

#: Identified research UA (the study's eloratings.net politeness policy:
#: identified non-browser agent, <= 1 request / 2 s, single-digit total).
USER_AGENT = (
    "polymarket-alpha-lab-papersim-intl/1.0 "
    "(research adapter, paper-only; repo: polymarket-alpha-lab)"
)

#: Polite spacing between ANY two requests issued by this module (the
#: study committed to <= 1 request / 2 s against eloratings.net; the
#: single raw.githubusercontent request inherits the same discipline).
SLEEP_S = 2.0

#: Per-attempt HTTPS timeout for the fetch functions.
FETCH_TIMEOUT_S = 30.0

#: Fetch attempts (transport errors only) before giving up.
FETCH_ATTEMPTS = 4

#: Default on-disk cache location on the ops host (raw payloads
#: verbatim; created lazily on first write). The WP-INTL-1 task pins
#: this to ``~/paper-sim/intl`` — NOT the repo-local ``.papersim_cache``
#: used by the ESPN adapter — because the backfill runs standalone on
#: the Linux ops host next to the study artifacts.
DEFAULT_CACHE_DIR = Path.home() / "paper-sim" / "intl"

#: ``source`` field of every emitted snapshot (frozen contract).
SOURCE_KEY = "intl-martj42-eloratings"

#: Frozen martj42 results.csv column order (header must match exactly).
RESULTS_HEADER = [
    "date", "home_team", "away_team", "home_score", "away_score",
    "tournament", "city", "country", "neutral",
]

#: Frozen top-level / per-match / per-checkpoint snapshot key sets.
_SNAPSHOT_KEYS = frozenset(
    {"generated_at", "source", "teams", "matches", "elo_history"}
)
_MATCH_KEYS = frozenset({
    "date", "home", "away", "home_goals", "away_goals",
    "tournament", "neutral", "venue",
})
_HISTORY_KEYS = frozenset({"team", "date", "elo"})

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# --- Elo engine constants (study section 4, probe defaults) ---------------

#: Every team's starting rating (eloratings.net convention).
INITIAL_ELO = 1500.0

#: Home-advantage Elo points added to the HOME side's expectation when
#: ``neutral`` is false (probe default; the venue effect lives in the
#: martj42 ``neutral`` column, which correctly flags e.g. Belarus
#: "home" games played in Budapest).
HOME_ADVANTAGE = 100.0

#: Logistic denominator of the Elo expectation (fixed by convention).
_ELO_SCALE = 400.0

#: K for FIFA World Cup finals (probe: 60).
K_WORLD_CUP_FINALS = 60.0

#: K for continental championship finals (probe: 50).
K_CONTINENTAL_FINALS = 50.0

#: K for UEFA Nations League, all qualifiers and every other
#: competitive tournament (probe: 40).
K_STANDARD = 40.0

#: K for friendlies (probe: 20).
K_FRIENDLY = 20.0

#: Continental championship finals in the K=50 bucket (exact martj42
#: tournament spellings, verified against the 225-value vocabulary of
#: the 2026-11-12 corpus; regional cups — CECAFA, COSAFA, Gulf Cup,
#: AFF, ... — stay in the K=40 bucket with the study's "everything
#: else competitive" rule).
CONTINENTAL_FINALS = frozenset({
    "UEFA Euro", "Copa América", "AFC Asian Cup", "African Cup of Nations",
    "Gold Cup", "CONCACAF Championship", "Oceania Nations Cup",
})

# --- sanity floors ---------------------------------------------------------

#: Minimum distinct corpus teams for a buildable snapshot (the full
#: corpus carries 337; fixtures pass a smaller ``min_teams``).
MIN_TEAMS = 100

#: Minimum teams in a structurally valid eloratings World.tsv (the
#: current file carries 243).
MIN_WORLD_TEAMS = 100

#: Module-wide monotonic timestamp of the last request; enforces
#: :data:`SLEEP_S` spacing across ALL fetch functions. Tests reset it.
_last_fetch_monotonic: float | None = None


class IntlDataError(RuntimeError):
    """Fatal international-data fetch failure (transport gave up)."""


class IntlDataSchemaError(IntlDataError):
    """Fail-closed upstream schema drift; no snapshot is emitted."""


# ---------------------------------------------------------------------------
# polite spacing, transport, atomic raw cache
# ---------------------------------------------------------------------------

def _polite_pause() -> None:
    """Sleep the remainder of :data:`SLEEP_S` since the last request."""
    global _last_fetch_monotonic
    now = time.monotonic()
    if _last_fetch_monotonic is not None:
        remaining = SLEEP_S - (now - _last_fetch_monotonic)
        if remaining > 0.0:
            time.sleep(remaining)
    _last_fetch_monotonic = time.monotonic()


def _http_get_bytes(url: str, *, timeout: float) -> bytes:
    """One HTTPS GET returning the raw body (raises on transport errors)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _fetch_bytes(url: str, *, timeout: float) -> bytes:
    """Fetch with retry/backoff and polite spacing; fail via IntlDataError."""
    last_exc: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        _polite_pause()
        try:
            return _http_get_bytes(url, timeout=timeout)
        except (urllib.error.URLError, OSError) as exc:
            last_exc = exc
            if attempt < FETCH_ATTEMPTS - 1:
                time.sleep(5.0 * (attempt + 1))
    raise IntlDataError(
        f"giving up after {FETCH_ATTEMPTS} attempts: {url} ({last_exc})"
    )


def _atomic_write_bytes(path: Path, blob: bytes) -> None:
    """Replace ``path`` atomically with ``blob`` (raw payload verbatim)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=str(path.parent),
        prefix=path.name + ".", suffix=".tmp", delete=False,
    )
    try:
        with handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, payload: object) -> None:
    """Serialize with ``allow_nan=False`` and replace ``path`` atomically.

    Compact separators: the full snapshot carries ~50k matches and
    ~100k Elo checkpoints, so byte-determinism is kept (``sort_keys``)
    without the indent=2 bloat of the ESPN snapshots (~5 MB vs ~25 MB).
    """
    blob = json.dumps(
        payload, sort_keys=True, allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    _atomic_write_bytes(path, blob)


def _cache_fresh(path: Path, max_age_s: float | None) -> bool:
    """Cache-hit test; unreadable/absent/stale entries are misses."""
    if not path.is_file():
        return False
    if max_age_s is not None:
        try:
            if time.time() - path.stat().st_mtime > max_age_s:
                return False
        except OSError:
            return False
    return True


def _cached_fetch(
    url: str,
    cache_path: Path | None,
    max_age_s: float | None,
    *,
    timeout: float,
    sniff: Callable[[bytes], None] | None = None,
) -> bytes:
    """Read-through raw cache around :func:`_fetch_bytes` (hit = no net)."""
    if cache_path is not None and _cache_fresh(cache_path, max_age_s):
        blob = cache_path.read_bytes()
        if blob:
            return blob  # returned as-is on a hit; corrupt cache content is caught fail-closed by the downstream parsers, not at the cache boundary
    blob = _fetch_bytes(url, timeout=timeout)
    if not blob:
        raise IntlDataError(f"empty response body from {url}")
    if sniff is not None:
        sniff(blob)
    if cache_path is not None:
        _atomic_write_bytes(cache_path, blob)
    return blob


def _sniff_results(blob: bytes) -> None:
    """Fetch-boundary check: first line must be the frozen CSV header."""
    first = blob.split(b"\n", 1)[0].rstrip(b"\r")
    expected = ",".join(RESULTS_HEADER).encode("utf-8")
    if first != expected:
        raise IntlDataSchemaError(
            f"results.csv header drift: {first[:80]!r} != {expected!r}"
        )


def _sniff_world(blob: bytes) -> None:
    """Fetch-boundary check: first data row looks like rank/rank/code/rating."""
    first = blob.split(b"\n", 1)[0].rstrip(b"\r")
    fields = first.split(b"\t")
    if len(fields) < 4:
        raise IntlDataSchemaError(
            f"World.tsv first row has {len(fields)} tab fields, need >= 4"
        )
    try:
        float(fields[3])
    except ValueError as exc:
        raise IntlDataSchemaError(
            f"World.tsv rating column {fields[3]!r} is not numeric"
        ) from exc


def _sniff_latest(blob: bytes) -> None:
    """Fetch-boundary check: latest.tsv rows are wide tab-separated."""
    first = blob.split(b"\n", 1)[0].rstrip(b"\r")
    field_count = len(first.split(b"\t"))
    if field_count < 8:
        raise IntlDataSchemaError(
            f"latest.tsv first row has {field_count} tab fields, need >= 8"
        )


# ---------------------------------------------------------------------------
# fetch layer (NETWORK, rate-limited, cached)
# ---------------------------------------------------------------------------

def _scratch_path(prefix: str, blob: bytes) -> Path:
    """Persist ``blob`` to a unique temp path (the no-cache branch)."""
    handle, name = tempfile.mkstemp(prefix=prefix, suffix=".raw")
    with os.fdopen(handle, "wb") as stream:
        stream.write(blob)
    return Path(name)


def fetch_intl_results(
    *,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    max_age_s: float | None = None,
    timeout: float = FETCH_TIMEOUT_S,
) -> Path:
    """Fetch (or reuse) the martj42 results.csv, cached verbatim (NETWORK).

    Returns the path of the raw CSV in the cache dir (``~/paper-sim/intl``
    by default; ``cache_dir=None`` disables persistence and returns a
    unique temp path). The raw bytes are written atomically and never
    reinterpreted; the first line is checked against
    :data:`RESULTS_HEADER` at the fetch boundary so an HTML error page
    never lands in the cache.
    """
    cache_path = None if cache_dir is None else Path(cache_dir) / "results.csv"
    blob = _cached_fetch(
        RESULTS_URL, cache_path, max_age_s,
        timeout=timeout, sniff=_sniff_results,
    )
    if cache_path is not None:
        return cache_path
    return _scratch_path("papersim_intl_results_", blob)


def fetch_eloratings_current(
    *,
    cache_dir: Path | str | None = DEFAULT_CACHE_DIR,
    max_age_s: float | None = None,
    timeout: float = FETCH_TIMEOUT_S,
) -> dict[str, Path]:
    """Fetch (or reuse) World.tsv + latest.tsv, cached verbatim (NETWORK).

    Returns ``{"world": <World.tsv path>, "latest": <latest.tsv path>}``.
    Both files are cached alongside results.csv with the same polite
    spacing. World.tsv is the current-ratings input of
    :func:`build_snapshot`; latest.tsv (pre-match Elo per recent game)
    is the study's cross-check supplement, cached for ops use and
    intentionally NOT consumed by the snapshot build.
    """
    out: dict[str, Path] = {}
    for name, url, sniff in (
        ("world", WORLD_URL, _sniff_world),
        ("latest", LATEST_URL, _sniff_latest),
    ):
        cache_path = (
            None if cache_dir is None else Path(cache_dir) / f"{name}.tsv"
        )
        blob = _cached_fetch(
            url, cache_path, max_age_s, timeout=timeout, sniff=sniff,
        )
        if cache_path is not None:
            out[name] = cache_path
        else:
            out[name] = _scratch_path(f"papersim_intl_{name}_", blob)
    return out


# ---------------------------------------------------------------------------
# parsing (pure, fail-closed) + Elo engine
# ---------------------------------------------------------------------------

def _parse_iso_date(raw: object, where: str) -> str:
    """Validate a ``YYYY-MM-DD`` literal (returns it unchanged)."""
    if not isinstance(raw, str) or not _DATE_RE.match(raw):
        raise IntlDataSchemaError(f"{where}: malformed date {raw!r}")
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise IntlDataSchemaError(
            f"{where}: unparseable date {raw!r}"
        ) from exc
    return raw


def _parse_goals(raw: object, where: str) -> int:
    """Goals as a nonnegative whole number (int, never bool/NaN/fraction).

    Accepts ints and integral floats/numeric strings (the CSV wire
    carries strings; the snapshot carries ints); rejects negative,
    NaN/Infinity, booleans and non-integral values.
    """
    if isinstance(raw, bool):
        raise IntlDataSchemaError(f"{where}: boolean goals {raw!r}")
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise IntlDataSchemaError(
            f"{where}: goals {raw!r} is not numeric"
        ) from exc
    if not math.isfinite(value) or value < 0.0 or value != int(value):
        raise IntlDataSchemaError(
            f"{where}: goals {raw!r} is not a finite whole nonnegative number"
        )
    return int(value)


def _parse_neutral(raw: object, where: str) -> bool:
    """Neutral flag from the CSV wire (``TRUE``/``FALSE``) or a bool."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        if raw == "TRUE":
            return True
        if raw == "FALSE":
            return False
    raise IntlDataSchemaError(f"{where}: bad neutral flag {raw!r}")


def read_intl_matches(
    path: str | Path,
    *,
    header: tuple[str, ...] | list[str] = RESULTS_HEADER,
) -> list[dict]:
    """Read + validate a martj42 results.csv into snapshot match dicts.

    PURE (no network). Fail-closed: exact 9-column header, every row
    with exactly 9 fields, iso dates in NON-DECREASING file order (the
    upstream file ships date-ascending; unordered input is corruption),
    finite whole nonnegative goals, ``home != away``, non-empty
    team/tournament strings, ``TRUE``/``FALSE`` neutral flags, no
    DUPLICATED row (same date + pair + score), and at least one match.
    ``venue`` is the city (``null`` when empty); ``country`` stays in
    the raw CSV only.

    Duplicate policy (fail-closed, verified against the real corpus):
    a duplicated ``(date, home, away, home_goals, away_goals)`` tuple
    is data corruption and rejected. A same-day rematch of the same
    pair with a DIFFERENT score is a genuine double-header and passes
    — the real corpus carries exactly one such pair (1974-02-17 Tahiti
    v New Caledonia, 2-1 and 1-2, both in Papeete), which the study's
    probe replayed as two matches and which must survive the reader.
    """
    matches: list[dict] = []
    seen: set[tuple[str, str, str, int, int]] = set()
    previous_date: str | None = None
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            fieldnames = next(reader)
        except StopIteration as exc:
            raise IntlDataSchemaError("results.csv is empty") from exc
        if fieldnames != list(header):
            raise IntlDataSchemaError(
                f"results.csv header {fieldnames!r} != frozen "
                f"{list(header)!r}"
            )
        for lineno, row in enumerate(reader, start=2):
            where = f"results.csv line {lineno}"
            if not row or (len(row) == 1 and not row[0].strip()):
                continue  # tolerate trailing blank line
            if len(row) != len(header):
                raise IntlDataSchemaError(
                    f"{where}: {len(row)} fields, need {len(header)}"
                )
            (
                raw_date, home, away, home_score, away_score,
                tournament, city, _country, raw_neutral,
            ) = row
            match_date = _parse_iso_date(raw_date, where)
            if previous_date is not None and match_date < previous_date:
                raise IntlDataSchemaError(
                    f"{where}: date {match_date} is before previous "
                    f"{previous_date} (unordered input)"
                )
            previous_date = match_date
            for label, team in (("home", home), ("away", away)):
                if not team.strip():
                    raise IntlDataSchemaError(f"{where}: empty {label} team")
            if home == away:
                raise IntlDataSchemaError(
                    f"{where}: {home!r} plays itself"
                )
            if not tournament.strip():
                raise IntlDataSchemaError(f"{where}: empty tournament")
            venue = city.strip() or None
            row_match = {
                "date": match_date,
                "home": home,
                "away": away,
                "home_goals": _parse_goals(home_score, f"{where} home_goals"),
                "away_goals": _parse_goals(away_score, f"{where} away_goals"),
                "tournament": tournament,
                "neutral": _parse_neutral(raw_neutral, where),
                "venue": venue,
            }
            key = (
                row_match["date"], row_match["home"], row_match["away"],
                row_match["home_goals"], row_match["away_goals"],
            )
            if key in seen:
                raise IntlDataSchemaError(f"{where}: duplicate match row {key}")
            seen.add(key)
            matches.append(row_match)
    if not matches:
        raise IntlDataSchemaError("results.csv carries no match rows")
    return matches


def parse_world_tsv(
    path: str | Path,
    *,
    min_teams: int = MIN_WORLD_TEAMS,
) -> dict[str, float]:
    """Read eloratings World.tsv into ``{team code: current rating}``.

    PURE. Row layout (verified against the 2026-11-12 probe artifact):
    tab-separated ``rank, rank, code, rating, <history columns...>`` —
    the rating is field 4 (index 3); there is no header row. Fail-closed:
    >= ``min_teams`` teams, integer rank, >= 4 fields, unique codes,
    finite nonnegative ratings.
    """
    ratings: dict[str, float] = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.rstrip("\r\n")
            if not stripped.strip():
                continue
            fields = stripped.split("\t")
            where = f"World.tsv line {lineno}"
            if len(fields) < 4:
                raise IntlDataSchemaError(
                    f"{where}: {len(fields)} tab fields, need >= 4"
                )
            try:
                int(fields[0])
            except ValueError as exc:
                raise IntlDataSchemaError(
                    f"{where}: rank {fields[0]!r} is not an integer"
                ) from exc
            code = fields[2].strip()
            if not code:
                raise IntlDataSchemaError(f"{where}: empty team code")
            if code in ratings:
                raise IntlDataSchemaError(f"{where}: duplicate code {code!r}")
            try:
                rating = float(fields[3])
            except ValueError as exc:
                raise IntlDataSchemaError(
                    f"{where}: rating {fields[3]!r} is not numeric"
                ) from exc
            if not math.isfinite(rating) or rating < 0.0:
                raise IntlDataSchemaError(
                    f"{where}: rating {fields[3]!r} is not finite nonnegative"
                )
            ratings[code] = rating
    if len(ratings) < min_teams:
        raise IntlDataSchemaError(
            f"World.tsv carries {len(ratings)} teams, below the "
            f"{min_teams}-team floor"
        )
    return ratings


def tournament_k(tournament: str) -> float:
    """K factor for one martj42 tournament label (probe bucket rule).

    60 FIFA World Cup finals / 50 continental championship finals
    (:data:`CONTINENTAL_FINALS`) / 20 ``Friendly`` / 40 everything else
    competitive (UEFA Nations League, all qualifiers, regional cups).
    """
    if tournament == "FIFA World Cup":
        return K_WORLD_CUP_FINALS
    if tournament in CONTINENTAL_FINALS:
        return K_CONTINENTAL_FINALS
    if tournament == "Friendly":
        return K_FRIENDLY
    return K_STANDARD


def _goal_diff_multiplier(goal_diff: int) -> float:
    """eloratings.net G: 1.0 / 1.5 / (11+N)/8 by winning margin."""
    margin = abs(goal_diff)
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11.0 + margin) / 8.0


def compute_elo_history(
    matches: Iterable[Mapping[str, object]],
    *,
    home_adv: float = HOME_ADVANTAGE,
    k: float | None = None,
    initial_elo: float = INITIAL_ELO,
) -> list[tuple[str, str, float]]:
    """Replay matches into Elo checkpoints: ``[(date, team, elo), ...]``.

    PURE (no I/O, no RNG — byte-deterministic for a given input list).
    The probe-validated eloratings.net engine: logistic expectation
    ``We = 1 / (10^(-dr/400) + 1)`` where ``dr`` adds ``home_adv`` to
    the home side unless the match is neutral; zero-sum update
    ``elo_home += K * G * (W - We)`` / ``elo_away -= ...`` with ``G``
    the goal-difference multiplier; every team starts at
    ``initial_elo`` (1500).

    After EACH match two checkpoints are appended — the home side
    first, then the away side — carrying the post-match rating, so
    checkpoint dates are non-decreasing for ordered input. ``k=None``
    (default) selects the probe's per-competition table via
    :func:`tournament_k`; a float overrides it uniformly (the model
    envelope's K-variant sweep passes explicit values; the task
    sketch's ``k=40, home_adv=65.0`` reads work verbatim).

    Fail-closed on the same discipline as the reader: non-decreasing
    dates, finite whole nonnegative goals, boolean ``neutral``, and
    non-empty team labels; a ``ValueError`` names the offending match.
    """
    if not isinstance(home_adv, (int, float)) or isinstance(home_adv, bool):
        raise ValueError(f"home_adv must be numeric, got {home_adv!r}")
    if k is not None and (
        not isinstance(k, (int, float)) or isinstance(k, bool)
    ):
        raise ValueError(f"k must be numeric or None, got {k!r}")
    if not math.isfinite(float(home_adv)) or not math.isfinite(initial_elo):
        raise ValueError("home_adv/initial_elo must be finite")
    ratings: dict[str, float] = {}
    checkpoints: list[tuple[str, str, float]] = []
    previous_date: str | None = None
    for index, match in enumerate(matches):
        if not isinstance(match, Mapping):
            raise ValueError(f"match[{index}]: not a mapping")
        where = f"match[{index}] {match.get('date', '?')!r}"
        match_date = match.get("date")
        if not isinstance(match_date, str) or not _DATE_RE.match(match_date):
            raise ValueError(f"{where}: malformed date {match_date!r}")
        if previous_date is not None and match_date < previous_date:
            raise ValueError(
                f"{where}: date {match_date} is before previous "
                f"{previous_date} (unordered input)"
            )
        previous_date = match_date
        home = match.get("home")
        away = match.get("away")
        if not isinstance(home, str) or not home:
            raise ValueError(f"{where}: empty home team")
        if not isinstance(away, str) or not away:
            raise ValueError(f"{where}: empty away team")
        if home == away:
            raise ValueError(f"{where}: {home!r} plays itself")
        tournament = match.get("tournament")
        if not isinstance(tournament, str) or not tournament:
            raise ValueError(
                f"{where}: tournament must be a non-empty string, got "
                f"{tournament!r}"
            )
        neutral = match.get("neutral")
        if not isinstance(neutral, bool):
            raise ValueError(f"{where}: neutral must be a bool, got {neutral!r}")
        home_goals = _elo_goals(match.get("home_goals"), f"{where} home_goals")
        away_goals = _elo_goals(match.get("away_goals"), f"{where} away_goals")
        k_factor = float(k) if k is not None else tournament_k(tournament)
        elo_home = ratings.get(home, float(initial_elo))
        elo_away = ratings.get(away, float(initial_elo))
        dr = elo_home - elo_away + (0.0 if neutral else float(home_adv))
        expected_home = 1.0 / (10.0 ** (-dr / _ELO_SCALE) + 1.0)
        if home_goals > away_goals:
            outcome = 1.0
        elif home_goals < away_goals:
            outcome = 0.0
        else:
            outcome = 0.5
        multiplier = _goal_diff_multiplier(home_goals - away_goals)
        delta = k_factor * multiplier * (outcome - expected_home)
        elo_home += delta
        elo_away -= delta
        ratings[home] = elo_home
        ratings[away] = elo_away
        checkpoints.append((match_date, home, elo_home))
        checkpoints.append((match_date, away, elo_away))
    return checkpoints


def _elo_goals(raw: object, where: str) -> int:
    """Goals for the Elo engine (same discipline as :func:`_parse_goals`)."""
    if isinstance(raw, bool):
        raise ValueError(f"{where}: boolean goals {raw!r}")
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where}: goals {raw!r} is not numeric") from exc
    if not math.isfinite(value) or value < 0.0 or value != int(value):
        raise ValueError(
            f"{where}: goals {raw!r} is not a finite whole nonnegative number"
        )
    return int(value)


# ---------------------------------------------------------------------------
# snapshot build (pure, fail-closed) + load + write
# ---------------------------------------------------------------------------

def build_snapshot(
    matches_csv: str | Path,
    elo_tsv: str | Path,
    *,
    min_teams: int = MIN_TEAMS,
    home_adv: float = HOME_ADVANTAGE,
    k: float | None = None,
    initial_elo: float = INITIAL_ELO,
) -> dict:
    """Build the frozen international snapshot from the two raw files.

    PURE (no network). Reads the results CSV through
    :func:`read_intl_matches` (full fail-closed validation), parses and
    structurally validates the eloratings World.tsv through
    :func:`parse_world_tsv` (>= :data:`MIN_WORLD_TEAMS` finite
    nonnegative ratings; the snapshot's Elo values are the SELF-computed
    ones — see the module docstring's design split), replays the corpus
    through :func:`compute_elo_history` and emits::

        {"generated_at": now-iso, "source": "intl-martj42-eloratings",
         "teams": {name: {"elo": <final self-Elo>}},
         "matches": [...], "elo_history": [...]}

    Fail-closed: any reader/parse violation above, or fewer than
    ``min_teams`` distinct corpus teams (100 by default; fixtures pass
    smaller floors). Nothing is returned in that case; an
    :class:`IntlDataSchemaError` names the offending condition.
    """
    matches = read_intl_matches(matches_csv)
    teams_in_corpus: set[str] = set()
    for match in matches:
        teams_in_corpus.add(match["home"])
        teams_in_corpus.add(match["away"])
    if len(teams_in_corpus) < min_teams:
        raise IntlDataSchemaError(
            f"corpus carries {len(teams_in_corpus)} distinct teams, below "
            f"the {min_teams}-team floor"
        )
    parse_world_tsv(elo_tsv)  # structural validation of the supplement
    checkpoints = compute_elo_history(
        matches, home_adv=home_adv, k=k, initial_elo=initial_elo,
    )
    final_elo: dict[str, float] = {}
    for _date, team, elo in checkpoints:
        final_elo[team] = elo  # last checkpoint wins (chronological replay)
    missing = teams_in_corpus - set(final_elo)
    if missing:  # defensive: every corpus team plays >= 1 match
        raise IntlDataSchemaError(
            f"teams without an Elo checkpoint: {sorted(missing)}"
        )
    history = [
        {"team": team, "date": match_date, "elo": elo}
        for match_date, team, elo in checkpoints
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_KEY,
        "teams": {name: {"elo": elo} for name, elo in sorted(final_elo.items())},
        "matches": matches,
        "elo_history": history,
    }


def _validate_snapshot(
    snapshot: object, *, min_teams: int = MIN_TEAMS
) -> dict:
    """Shared structural validation for load/write (fail-closed)."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("intl snapshot root must be a JSON object")
    keys = set(snapshot)
    if keys != _SNAPSHOT_KEYS:
        raise ValueError(
            f"snapshot keys {sorted(keys)} != frozen contract "
            f"{sorted(_SNAPSHOT_KEYS)}"
        )
    if snapshot["source"] != SOURCE_KEY:
        raise ValueError(
            f"snapshot source {snapshot['source']!r} != {SOURCE_KEY!r}"
        )
    generated_at = snapshot["generated_at"]
    if not isinstance(generated_at, str) or not generated_at:
        raise ValueError("snapshot generated_at must be a non-empty string")
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"snapshot generated_at {generated_at!r} is not iso8601"
        ) from exc
    teams = snapshot["teams"]
    if not isinstance(teams, Mapping) or not teams:
        raise ValueError("snapshot teams must be a non-empty object")
    if len(teams) < min_teams:
        raise ValueError(
            f"snapshot carries {len(teams)} teams, below the "
            f"{min_teams}-team floor"
        )
    for name, block in teams.items():
        if not isinstance(name, str) or not name:
            raise ValueError("snapshot team names must be non-empty strings")
        if not isinstance(block, Mapping) or set(block) != {"elo"}:
            raise ValueError(f"team {name}: block keys must be exactly elo")
        elo = block["elo"]
        if isinstance(elo, bool) or not isinstance(elo, (int, float)):
            raise ValueError(f"team {name}: elo must be numeric")
        if not math.isfinite(float(elo)) or float(elo) < 0.0:
            raise ValueError(
                f"team {name}: elo {elo!r} is not finite nonnegative"
            )
    matches = snapshot["matches"]
    if not isinstance(matches, list) or not matches:
        raise ValueError("snapshot matches must be a non-empty list")
    seen: set[tuple[str, str, str, int, int]] = set()
    previous_date: str | None = None
    for index, match in enumerate(matches):
        where = f"match[{index}]"
        if not isinstance(match, Mapping) or set(match) != _MATCH_KEYS:
            raise ValueError(
                f"{where}: keys "
                f"{sorted(match) if isinstance(match, Mapping) else match!r} "
                f"!= frozen contract {sorted(_MATCH_KEYS)}"
            )
        match_date = match["date"]
        if not isinstance(match_date, str) or not _DATE_RE.match(match_date):
            raise ValueError(f"{where}: malformed date {match_date!r}")
        try:
            datetime.strptime(match_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(
                f"{where}: unparseable date {match_date!r}"
            ) from exc
        if previous_date is not None and match_date < previous_date:
            raise ValueError(
                f"{where}: date {match_date} is before previous "
                f"{previous_date} (unordered)"
            )
        previous_date = match_date
        home, away = match["home"], match["away"]
        for label, team in (("home", home), ("away", away)):
            if not isinstance(team, str) or not team:
                raise ValueError(f"{where}: empty {label} team")
            if team not in teams:
                raise ValueError(f"{where}: {label} team {team!r} not in teams")
        if home == away:
            raise ValueError(f"{where}: {home!r} plays itself")
        key = (
            match_date, home, away, match["home_goals"], match["away_goals"],
        )
        if key in seen:
            raise ValueError(f"{where}: duplicate match row {key}")
        seen.add(key)
        for field in ("home_goals", "away_goals"):
            goals = match[field]
            if isinstance(goals, bool) or type(goals) is not int or goals < 0:
                raise ValueError(
                    f"{where}: {field} must be a nonnegative int, got {goals!r}"
                )
        if type(match["neutral"]) is not bool:
            raise ValueError(f"{where}: neutral must be a bool")
        if match["tournament"] is None or not isinstance(
            match["tournament"], str
        ) or not match["tournament"]:
            raise ValueError(f"{where}: tournament must be a non-empty string")
        venue = match["venue"]
        if venue is not None and not isinstance(venue, str):
            raise ValueError(f"{where}: venue must be a string or null")
    history = snapshot["elo_history"]
    if not isinstance(history, list) or not history:
        raise ValueError("snapshot elo_history must be a non-empty list")
    last_elo: dict[str, float] = {}
    previous_date = None
    for index, entry in enumerate(history):
        where = f"elo_history[{index}]"
        if not isinstance(entry, Mapping) or set(entry) != _HISTORY_KEYS:
            raise ValueError(
                f"{where}: keys must be exactly team/date/elo"
            )
        team = entry["team"]
        if not isinstance(team, str) or not team:
            raise ValueError(f"{where}: empty team")
        if team not in teams:
            raise ValueError(f"{where}: team {team!r} not in teams")
        entry_date = entry["date"]
        if not isinstance(entry_date, str) or not _DATE_RE.match(entry_date):
            raise ValueError(f"{where}: malformed date {entry_date!r}")
        if previous_date is not None and entry_date < previous_date:
            raise ValueError(
                f"{where}: date {entry_date} is before previous "
                f"{previous_date} (unordered)"
            )
        previous_date = entry_date
        elo = entry["elo"]
        if isinstance(elo, bool) or not isinstance(elo, (int, float)):
            raise ValueError(f"{where}: elo must be numeric")
        if not math.isfinite(float(elo)) or float(elo) < 0.0:
            raise ValueError(f"{where}: elo {elo!r} is not finite nonnegative")
        last_elo[team] = float(elo)
    silent_teams = set(teams) - set(last_elo)
    if silent_teams:
        raise ValueError(
            f"teams without any elo_history checkpoint: {sorted(silent_teams)}"
        )
    for name, block in teams.items():
        if float(block["elo"]) != last_elo[name]:
            raise ValueError(
                f"team {name}: snapshot elo {block['elo']!r} != last "
                f"history checkpoint {last_elo[name]!r}"
            )
    return snapshot  # type: ignore[return-value]


def load_intl_snapshot(
    path: str,
    *,
    min_teams: int = MIN_TEAMS,
) -> dict:
    """Load and validate a frozen-contract intl snapshot (PURE, no network).

    Structural fail-closed validation mirroring the build boundary:
    exact frozen key sets, ``source == intl-martj42-eloratings``, >=
    ``min_teams`` teams (100 by default — fixtures pass smaller floors)
    with finite nonnegative Elo, non-empty matches with exact key
    sets, nonnegative int goals (bools and floats rejected), bool
    ``neutral``, string-or-null ``venue``, non-decreasing match dates,
    no duplicated rows (same date + pair + score; genuine same-day
    double-headers with different scores pass), every match team
    covered by the teams table, and an ``elo_history`` whose checkpoint
    dates are non-decreasing and whose LAST checkpoint per team equals the
    team's snapshot Elo. ``json.load`` accepts bare ``NaN`` /
    ``Infinity`` literals — those are rejected here (codex review #8
    discipline). Validation only rejects; accepted payloads are
    returned unmodified.
    """
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return _validate_snapshot(payload, min_teams=min_teams)


def write_snapshot(
    snapshot: Mapping[str, object],
    path: str | Path,
    *,
    min_teams: int = MIN_TEAMS,
) -> Path:
    """Validate, then atomically write a snapshot as deterministic JSON.

    ``allow_nan=False`` makes the write itself the last finite-value
    gate; ``sort_keys=True`` with compact separators gives
    byte-deterministic output at a sane size for the ~150k-record
    document (see :func:`_atomic_write_json`). ``min_teams`` mirrors
    :func:`load_intl_snapshot` (fixtures pass smaller floors).
    """
    _validate_snapshot(snapshot, min_teams=min_teams)
    target = Path(path)
    _atomic_write_json(target, snapshot)
    return target


# ---------------------------------------------------------------------------
# backfill entry point (WP-INTL-1 ops; writes OUTSIDE the repo)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI: fetch the raw sources once, build + write a snapshot file.

    ``python -m polymarket_alpha_lab.papersim.intl_data --out PATH
    [--cache-dir DIR]`` (the module is stdlib-only, so the same file
    runs standalone on the Linux ops host). Fetches results.csv,
    World.tsv and latest.tsv politely into the cache dir (``~/paper-
    sim/intl`` by default; existing fresh files are reused), builds the
    fail-closed snapshot, re-validates it through
    :func:`load_intl_snapshot`, writes it atomically and prints
    team/match/checkpoint counts plus the current top-10 Elo table as
    backfill evidence.
    """
    parser = argparse.ArgumentParser(
        description=(
            "International soccer snapshot backfill "
            "(paper-only, no credentials)"
        )
    )
    parser.add_argument("--out", required=True, help="snapshot output path")
    parser.add_argument(
        "--cache-dir", default=str(DEFAULT_CACHE_DIR),
        help="raw payload cache dir (empty string disables caching)",
    )
    parser.add_argument(
        "--max-age-s", type=float, default=None,
        help="cache freshness window in seconds (default: never expire)",
    )
    args = parser.parse_args(argv)
    cache_dir: Path | str | None = args.cache_dir
    if cache_dir == "":
        cache_dir = None
    results_path = fetch_intl_results(
        cache_dir=cache_dir, max_age_s=args.max_age_s
    )
    eloratings = fetch_eloratings_current(
        cache_dir=cache_dir, max_age_s=args.max_age_s
    )
    snapshot = build_snapshot(results_path, eloratings["world"])
    target = write_snapshot(snapshot, args.out)
    reloaded = load_intl_snapshot(str(target))
    team_count = len(reloaded["teams"])
    match_count = len(reloaded["matches"])
    checkpoint_count = len(reloaded["elo_history"])
    top10 = sorted(
        reloaded["teams"].items(), key=lambda item: (-item[1]["elo"], item[0])
    )[:10]
    table = "  ".join(
        f"{name} {block['elo']:.1f}" for name, block in top10
    )
    print(
        f"intl snapshot {target}: source={reloaded['source']} "
        f"teams={team_count} matches={match_count} "
        f"elo_checkpoints={checkpoint_count} "
        f"generated_at={reloaded['generated_at']}"
    )
    print(f"top-10 elo: {table}")
    print(
        f"raw cache: results={results_path} world={eloratings['world']} "
        f"latest={eloratings['latest']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI guard
    raise SystemExit(main())
