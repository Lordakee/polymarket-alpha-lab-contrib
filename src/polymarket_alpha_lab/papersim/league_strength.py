"""League-strength bridging for cross-league xG fixtures.

Single responsibility: hold the league -> kappa (log-strength) table
and compute the clamped multiplicative bridge factor that makes xG
multipliers from two different domestic leagues comparable. This is
the WP-P2a mechanism module: it consumes a kappa table (estimated and
anchored elsewhere, WP-P2b) and exposes no estimation of its own.

Motivation (review/FIXES.md sections 5-6, 2026-10-30): domestic xG
attack / defense multipliers are measured relative to their OWN
league's average and are not cross-league comparable. Combining them
raw produced the confirmed HOF-LYO favorite-flip structural defect
(model made Lyon the favorite while the market correctly had
Hoffenheim). ``xg.pair_lambdas`` therefore returns ``None`` for
cross-league fixtures unless an explicit bridge table is supplied;
this module defines what that bridge means.

Model (frozen mechanism, κ values are calibrated separately):

- ``kappa[league]`` is the league's log-strength: a team from league L
  carries absolute attack quality scaled by ``exp(kappa_L)`` and
  concedes scaled by ``exp(-kappa_L)``. Within one league the two
  effects cancel at the league average, which is exactly why domestic
  multipliers need no bridge and why the same-league path of
  ``pair_lambdas`` never consults this module.
- For a cross-league fixture (home league X, away league Y) the home
  rate is multiplied by ``f = exp(clamp(kappa_X - kappa_Y, +-ln 1.25))``
  and the away rate divided by the same ``f``: the team from the
  STRONGER league (larger κ) is boosted on both sides of the ball. The
  sign is load-bearing — with Bundesliga κ above Ligue 1 κ (UEFA
  country-coefficient order at the 2026 freeze), the bridge moves the
  HOF-LYO fixture toward Hoffenheim, the direction the market showed.
- The clamp bounds the bridge displacement to a factor of 1.25 per
  side (edge ratio at most ``1.25**2 = 1.5625``): until the κ table is
  calibrated by a passing UCL/UEL walk-forward backtest, no kappa
  error can displace a modeled favorite by more than that
  (DELIVERY_PLAN known-gap #1: cap the away-side edge until
  calibrated).

κ reference anchor: UEFA men's country coefficients
(:data:`UEFA_COEFFICIENT_REFERENCE_URL`) — higher coefficient means a
stronger league, so κ derived from it is monotone in league strength.
The anchor is documentation for the WP-P2b estimation pass; this
module never fetches it and performs no network access.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "BRIDGE_CLAMP_LOG",
    "BRIDGE_CLAMP_RATIO",
    "LeagueStrengthTable",
    "UEFA_COEFFICIENT_REFERENCE_URL",
    "bridge_factor",
    "load_kappa_report",
    "load_kappa_table",
]

#: Maximum multiplicative bridge displacement per side: the clamp
#: bounds ``f`` to ``[1 / 1.25, 1.25]`` (frozen WP-P2a policy value —
#: calibration-free headroom until the walk-forward backtest lands).
BRIDGE_CLAMP_RATIO = 1.25

#: The same clamp on the κ-difference scale: ``ln(1.25)``.
BRIDGE_CLAMP_LOG = math.log(BRIDGE_CLAMP_RATIO)

#: Documentation anchor for the κ estimation pass (WP-P2b): UEFA
#: men's country coefficients, where a HIGHER coefficient means a
#: STRONGER league and κ must be monotone in it. Reference only —
#: this module performs no network access and embeds no coefficient
#: values.
UEFA_COEFFICIENT_REFERENCE_URL = (
    "https://www.uefa.com/nationalassociations/uefarankings/"
)


@dataclass(frozen=True)
class LeagueStrengthTable:
    """Immutable league-key -> κ (log-strength) table.

    ``kappa`` maps Understat league keys (``"EPL"``, ``"bundesliga"``,
    ``"ligue_1"``, ...) to finite floats. Pass ``table.kappa`` where a
    ``Mapping[str, float]`` bridge is expected (``xg.pair_lambdas`` and
    the ``soccer_model`` threading).

    Deep immutability (codex review 2026-11-03, minor 4): the mapping
    is copied at construction and stored as a read-only
    :class:`types.MappingProxyType` view, so neither mutating the
    caller's source dict after construction nor writing through
    ``table.kappa`` can change the table. Item assignment on
    ``table.kappa`` raises ``TypeError``.
    """

    kappa: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kappa", MappingProxyType(dict(self.kappa)))


def _validated_kappa_entry(league: object, value: object) -> float:
    """Validate one ``league -> κ`` entry; the single shared rule.

    A κ must be a finite real number. ``bool`` is rejected explicitly
    even though ``bool`` subclasses ``int`` (``float(True) == 1.0``
    would silently pass a JSON ``true`` through as a strength), and
    NaN/Inf fail :func:`math.isfinite` — a NaN κ would otherwise
    propagate through the clamp (``max``/``min`` comparisons are False
    against NaN) to the positive clamp limit as a silently plausible
    1.25 factor (codex review 2026-11-03, major 1). Raises
    ``ValueError`` naming the offending league.
    """
    if isinstance(value, bool):
        raise ValueError(
            f"kappa for league {league!r} must be a finite number, got {value!r} (bool)"
        )
    try:
        entry = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"kappa for league {league!r} must be a number, got {value!r}"
        ) from exc
    if not math.isfinite(entry):
        raise ValueError(
            f"kappa for league {league!r} must be a finite number, got {value!r}"
        )
    return entry


def load_kappa_table(path: str) -> LeagueStrengthTable:
    """Load a κ table from a flat JSON object file ``{"<league>": kappa}``.

    Values must be finite numbers. Raises ``ValueError`` for a
    non-object root, non-numeric, boolean or non-finite κ values; the
    loader never touches the network.
    """
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("league kappa table root must be a JSON object")
    kappa: dict[str, float] = {}
    for league, value in payload.items():
        kappa[str(league)] = _validated_kappa_entry(league, value)
    return LeagueStrengthTable(kappa=kappa)


def load_kappa_report(path: str) -> LeagueStrengthTable:
    """Load a κ table from a WP-P2b nested estimation report.

    The estimation pass (WP-P2b) writes a JSON report object whose
    ``"kappa"`` member holds the league -> κ mapping, alongside its own
    metadata (backtest window, anchor, diagnostics), e.g.::

        {
          "generated_at": "2026-11-03T00:00:00Z",
          "anchor": "uefa_country_coefficients",
          "backtest": {"seasons": ["2023", "2024"], "status": "PASS"},
          "kappa": {"bundesliga": 0.05, "ligue_1": 0.0}
        }

    This loader extracts the ``"kappa"`` sub-object (the flat
    :func:`load_kappa_table` path stays available for a standalone
    flat config file). Raises ``ValueError`` when the root is not an
    object, the ``"kappa"`` member is missing or not an object, or any
    κ entry is non-numeric, boolean or non-finite. No network access.
    """
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("league kappa report root must be a JSON object")
    nested = payload.get("kappa")
    if not isinstance(nested, dict):
        raise ValueError(
            'league kappa report must contain a "kappa" JSON object, got '
            f"{type(nested).__name__}"
        )
    kappa: dict[str, float] = {}
    for league, value in nested.items():
        kappa[str(league)] = _validated_kappa_entry(league, value)
    return LeagueStrengthTable(kappa=kappa)


def bridge_factor(
    kappa: Mapping[str, float],
    home_league: str,
    away_league: str,
) -> float | None:
    """Clamped league-strength bridge ``f`` for one cross-league fixture.

    ``f = exp(clamp(kappa[home_league] - kappa[away_league], -ln 1.25, ln 1.25))``:
    the home rate is multiplied by ``f`` and the away rate divided by
    it, so the team from the stronger (larger-κ) league is boosted on
    both sides. Returns ``None`` when either league key is missing
    from ``kappa`` — an unknown league has no calibrated strength, and
    the caller must refuse the fixture rather than bridge through a
    default.

    Both selected κ values are validated (finite real numbers, no
    booleans) BEFORE any arithmetic: a NaN or infinite κ raises
    ``ValueError`` naming the offending league instead of leaking
    through the clamp — a NaN delta compares False against both clamp
    bounds, so it would otherwise surface as a silently plausible
    factor of exactly ``1.25`` (codex review 2026-11-03, major 1).
    """
    if home_league not in kappa or away_league not in kappa:
        return None
    kappa_home = _validated_kappa_entry(home_league, kappa[home_league])
    kappa_away = _validated_kappa_entry(away_league, kappa[away_league])
    delta = kappa_home - kappa_away
    clamped = max(-BRIDGE_CLAMP_LOG, min(BRIDGE_CLAMP_LOG, delta))
    return math.exp(clamped)
