"""Paper-simulation core library migrated from ``/home/ubuntu/paper-sim``.

Semantics: everything in this package is **paper-only / report-only /
readonly**. It models probabilities, gates paper entries, records paper
positions and emits research reports. It never authenticates accounts,
handles credentials or private keys, signs or submits orders, or mutates
anything on an exchange. Durable evidence persistence, when wired in, goes
to the project-private native PostgreSQL cluster only (Project Iron Rule 1);
no file-backed journals are added.

Provenance map (canonical lineages):

- Soccer: ``r5c -> r15 -> r23``. The current head is the round-23
  10-variant xG-Poisson model (Understat per-league snapshots, shrinkage
  blend, match_winner suspended, spreads flagged-only, cross-league guard
  returns ``None``).
- Crypto: ``r19``. A/B GBM conventions (zero-log-drift vs median-flat),
  30-day realized-vol signature table, drifted first-passage touch
  probabilities.
- Superseded: ``r12``, ``r13`` and ``r15`` are superseded heads (r12/r13
  bespoke ad-hoc branches; r15 remains only as the canonical intermediate
  ancestor of r23). Do not migrate logic from them; migrate from the
  canonical heads above.

This module currently exports stub interfaces only (WP-P1 commit 1).
Implementations land in later commits of the work package.
"""

from polymarket_alpha_lab.papersim.cli import main as cli_main
from polymarket_alpha_lab.papersim.crypto_model import (
    TouchProbability,
    realized_vol_daily,
    touch_probability,
)
from polymarket_alpha_lab.papersim.gates import (
    GATES,
    GateDecision,
    NewsCheck,
    check_news,
    evaluate_gates,
)
from polymarket_alpha_lab.papersim.ledger import (
    PaperLedgerEntry,
    mark_to_market,
    record_entry,
)
from polymarket_alpha_lab.papersim.risk_policy import (
    PaperStake,
    bankroll_available,
    paper_stake,
)
from polymarket_alpha_lab.papersim.soccer_model import (
    SoccerCandidate,
    match_lambdas,
    over_under_quote,
)
from polymarket_alpha_lab.papersim.xg import (
    XgTeamRow,
    load_xg_snapshot,
    team_ratings,
)

__all__ = [
    "GATES",
    "GateDecision",
    "NewsCheck",
    "PaperLedgerEntry",
    "PaperStake",
    "SoccerCandidate",
    "TouchProbability",
    "XgTeamRow",
    "bankroll_available",
    "check_news",
    "cli_main",
    "evaluate_gates",
    "load_xg_snapshot",
    "mark_to_market",
    "match_lambdas",
    "over_under_quote",
    "paper_stake",
    "realized_vol_daily",
    "record_entry",
    "team_ratings",
    "touch_probability",
]
