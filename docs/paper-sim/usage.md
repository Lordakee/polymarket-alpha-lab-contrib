# Paper-sim core library usage (WP-P1)

`polymarket_alpha_lab.papersim` is the migrated, tested core of the
paper-sim system (soccer lineage `r5c -> r15 -> r23`, crypto lineage
`r19`). Everything in it is **paper-only / report-only / readonly**: it
models probabilities, gates paper entries, and builds reports. It never
authenticates accounts, touches credentials, or signs/submits orders.

## CLI

Run inside the project virtualenv from the repository root:

```bash
.venv/bin/python -m polymarket_alpha_lab.papersim.cli selfcheck
.venv/bin/python -m polymarket_alpha_lab.papersim.cli schema
.venv/bin/python -m polymarket_alpha_lab.papersim.cli validate-dsn
```

- **selfcheck** — the invariant suite. Imports the package surface and
  recomputes every frozen regression anchor through the real
  implementations: the three r19 crypto touch anchors (ETH-2000 /
  ETH-2250 / BTC-65k), the four r23 soccer anchors over the ten sweep
  variants (BRE-FOR / HUL-IPS / CHE-MUN / BOU-LEE), the banned
  cross-league path (HOF-LYO must yield `None`), and the #48
  gate-arithmetic record. Prints one `[PASS]`/`[FAIL]` line per check
  and exits 0 only when all ten pass. No network, no database.
  Run it after any change to the package or its fixtures.
- **schema** — prints the ledger migration DDL verbatim (byte-identical
  to `supabase/migrations/20261101000000_papersim_ledger.sql`).
  Descriptive evidence only; applying migrations is the exclusive job of
  the transactional native-Postgres migration ledger, never this
  command.
- **validate-dsn** — report-only validation of `PAPERSIM_PG_DSN`
  through the single audited `validate_local_postgres_dsn`. It never
  opens a connection, never reads the password file, and never prints
  the DSN value.

## How round scripts adopt the library incrementally

The library replaces the per-round bespoke scripts one function at a
time; a round script can migrate one stage per round without big-bang
rewrites:

1. **Load xG data**: `xg.load_xg_snapshot(path)` reads a pre-fetched
   Understat snapshot (no network access inside the library; fetching
   stays with the external research tooling).
2. **Price a soccer fixture**: `soccer_model.fixture_variants(snapshot,
   home, home_league, away, away_league)` evaluates all ten sweep
   variants (or returns `None` when the fixture is refused — see the
   guard below); `soccer_model.candidate_from_variants(...)` builds a
   candidate quote; `xg.recent_form(...)` adds form context. For a
   cross-league fixture (UCL/UEL style), pass the explicit
   `bridge=` κ table — see "The cross-league bridge path" below.
3. **Price a crypto barrier**: `crypto_model.realized_vol_windows(
   closes)` builds the 7/30/60/87d vol table from complete 6h bars,
   then `crypto_model.touch_probability(...)` /
   `terminal_probability(...)` give the A/B convention pair and
   `conservative_edges(...)` the per-side conservative fair values.
4. **Gate candidates**: `gates.walk_book(levels, "ask")` walks the $250
   VWAP, `gates.evaluate_candidate(quote, book, ...)` applies the full
   frozen gate set (spread/worst/exec/liq/fill/entry-window/news),
   `gates.suspension_policy(kind, cross_league=...)` answers market-kind
   eligibility, `gates.rank_candidates(...)` orders the survivors.
5. **Size and settle**: `risk_policy.sizing_tier(...)` /
   `paper_stake(...)`, `team_cap_status(...)`,
   `held_fixture_add_allowed(...)`; `ledger.settle_natural(...)` /
   `settle_exit(...)` realize outcomes, `bankroll_identity(...)`
   checks the cash identity.

**The cross-league guard is relaxable ONLY via the explicit bridge
parameter**: `match_lambdas` / `fixture_variants` /
`candidate_from_variants` return `None` whenever the two clubs' xG
ratings come from different leagues AND no `bridge=` κ table was
passed. The HOF-LYO favorite-flip came from bespoke scripts bypassing
exactly this guard (`review/FIXES.md`, 2026-10-30). Round scripts must
treat `None` as "not modelable", never re-derive cross-league lambdas
themselves. There is no other relaxation path: no config flag, no
environment variable, no default bridge.

Note: cross-league **match_winner (1X2) markets remain BANNED**
regardless of the bridge — `gates.suspension_policy` still suspends
them until a league-strength-bridged UCL/UEL walk-forward backtest
passes. The bridge below only re-enables the totals/BTTS-style
channels through the guarded modeling path.

## The cross-league bridge path (WP-P2a)

Domestic xG multipliers are measured relative to their OWN league's
average and are not cross-league comparable. Combining them raw is
what produced the HOF-LYO favorite flip. The sanctioned path threads
an explicit league-strength κ table through the modeling calls:

```python
from polymarket_alpha_lab.papersim import league_strength, soccer_model

# Path 1 — flat JSON config file: {"bundesliga": 0.05, "ligue_1": 0.0}
table = league_strength.load_kappa_table("kappa.json")

# Path 2 — WP-P2b nested estimation report: the κ mapping lives under
# the report's "kappa" member, next to its own metadata; the loader
# extracts exactly that sub-object.
table = league_strength.load_kappa_report("kappa_report.json")

# Thread it: every soccer-modeling entry point takes bridge=.
variants = soccer_model.fixture_variants(
    snapshot, home, home_league, away, away_league, bridge=table.kappa
)
candidate = soccer_model.candidate_from_variants(
    snapshot, home, home_league, away, away_league, 2.5,
    "HOF vs LYO", "m1", 0.5, bridge=table.kappa,
)
```

What the bridge does: each side keeps its OWN league's base rates and
multipliers, and the pair is tilted by the clamped factor
`f = exp(clamp(kappa_home_league - kappa_away_league, ±ln 1.25))` —
home rate `* f`, away rate `/ f` — so the team from the stronger
(larger-κ) league is boosted on both sides of the ball. The clamp
bounds any κ error to a 1.25x displacement per side (edge ratio at
most `1.25² = 1.5625`) until the κ table is calibrated by a passing
UCL/UEL walk-forward backtest (WP-P2b; κ must be monotone in the UEFA
country-coefficient anchor). Behavior details:

- Same-league fixtures are byte-identical with and without a bridge:
  the argument is never consulted when `home_league == away_league`.
- A league missing from the bridge still yields `None` (refuse the
  fixture; there is no default κ).
- κ values must be finite numbers; NaN/Inf/boolean κ raise
  `ValueError` (a NaN would otherwise leak through the clamp as a
  plausible 1.25 factor). The loaded table is deeply immutable
  (read-only mapping; mutation raises `TypeError`).
- κ estimation is WP-P2b and not yet run; until its report exists,
  round scripts keep using same-league fixtures only.

## DSN and password-file conventions

- Ledger persistence targets the project-private native PostgreSQL
  cluster only. `PAPERSIM_PG_DSN` (example documented default:
  `postgresql://paper_sim@127.0.0.1:55432/paper_sim`) is validated
  through the single audited `validate_local_postgres_dsn`; hosted
  hosts, sqlite and JSONL fallbacks are rejected. `ledger.papersim_dsn()`
  is the only sanctioned resolution path.
- The SCRAM password is **never** part of the DSN. It is supplied
  out-of-band via `PAPERSIM_PG_PASSWORD_FILE` — an environment variable
  holding the path of a one-line password file owned by the operator.
  There is no default path; the library never reads, logs or commits
  that file; only a connection adapter explicitly asked to connect may
  read it at connect time.

## What stays server-side

- Raw data fetching (Understat pages, Binance/Coinbase prints, CLOB
  books) stays in the external research tooling; the library itself
  performs zero network access and consumes local snapshot files only.
- The live `/home/ubuntu/paper-sim` round records remain the book of
  record for past rounds; the library is the canonical implementation
  new rounds copy from, not a retro-edit of history (r12/r13 boundary
  warnings included in the module docstrings).
- The live loopback `paper_sim` cluster (127.0.0.1:55432), its password
  file and any migration application stay with the server-side
  migration ledger; `schema` only mirrors the DDL as evidence.

Two ledger functions (`record_entry`, `mark_to_market`) remain frozen
stubs by design until the store-adapter commit lands; everything else
in the package surface is implemented and regression-anchored.

**Gate-safe candidate construction:** build gateable soccer candidates with `soccer_model.candidate_from_variants(...)` (snapshot-driven, carries the true ten-variant quotes). The pair-level `over_under_quote(...)` collapses sweep variance for O/U >= 2.0 and is NOT gate-safe — see its docstring warning.
