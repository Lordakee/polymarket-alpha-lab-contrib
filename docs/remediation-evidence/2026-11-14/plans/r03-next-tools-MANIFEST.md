# R03 next diagnostic tools manifest (2026-11-14, scoped delta revision 3)

Phase: revision-3 fix applied and submitted for scoped delta re-review.
Experiment A already ran under revision 2 (CONTROL_EXPECTED_MATCH);
experiment B attempt 1 BLOCKED at preflight on the revision-2 header
parsing defect (tooling defect, preserved as attempt-1 evidence, not an
experiment result).  Experiment B may run only after this revision-3
delta re-review PASS, with the same invocation id and the fresh
`old-data-2`/`old-evidence-2` directories.

## Files (this directory, LF line endings, ASCII only)

| file | bytes | sha256 |
| --- | ---: | --- |
| `r03_next_driver.py` | 51532 | `24ae2af60f8d3eb48ab2e01da8463699133d951accabfbbd0c2bc7354a469a03` |
| `r03_next_observer.py` | 18563 | `5f33b3a8c8690066d2a9380bf4443120f3d57ded7964389027da98db59b102eb` |

Governing plan: `D:\Projects\pal-remediation-plans-20261113\r03-next-diagnostic-plan-20261114.md`
(19345 bytes, sha256 `027f877e8c7ce01779c046fd15891b0f4b092416563df86cc467e66c74bf55d5`,
plan review PASS with corrections P2-1/P2-2/P3 applied; the plan hash is
pinned in the driver and experiment B refuses a mismatched `--plan-sha256`).

## Scoped delta revision 2 (applied after fresh script review PASS, 0 P1)

Applied (reviewer-required):

- P2-1: explicit truncation check `len(raw) > PROC_READ_LIMIT - 1` (i.e.
  `> 65536`) now yields `UNAVAILABLE` in BOTH the bootstrap template
  `_proc_counts` and the parent-side `proc_counts`, matching the C3
  harness `_old_seed_tcp_counts` semantics (`len(raw) > 65536 or not
  endswith('\n')`).
- P2-2: experiment B preconditions cannot be omitted or bypassed.
  `--control-report`, `--invocation-id`, `--plan-sha256` and
  `--prefix-inventory-sha256` are argparse-required for `old-prefix`, and
  `run_old_prefix` re-checks them before creating any directory; a
  missing/empty value prints `BLOCKED missing required arguments` and
  exits 2, and `--plan-sha256` must equal the pinned plan hash exactly or
  the driver prints `BLOCKED plan sha256 mismatch` and exits 2.
- P2-3: exceeding the 1 MiB whitelisted-evidence budget now changes the
  outcome to `EVIDENCE_BUDGET_EXCEEDED` (execution failure, exit 1)
  instead of merely flagging and rewriting the report; `child_budget`
  enforces an independent 256 KiB failure line per child stream
  (stdout/stderr tracked separately), enforced at the harness `_run`
  boundary (subprocess.run), with returned bytes never truncated into
  assertions.

Applied (P3 low-cost suggestions):

- P3-1: `_chain` now traverses both `__cause__` and `__context__`
  (bounded breadth-first, at most 4 nodes, each entry marked
  `via: raised|cause|context`).
- P3-4: old-prefix preflight probes `/proc/net/tcp6` in addition to
  `/proc/net/tcp`; either being unparsable is BLOCKED before the fixture.
- P3-5: the control step now has ONE shared 15 s wall budget covering
  both scenarios (plan wording: one budget for the whole control step),
  replacing the previous per-scenario 15 s budget.
- P3-6: dead helper `state_count` removed.

Recorded, intentionally unchanged (per reviewer disposition): P3-2,
P3-3, P3-7.

## Scoped delta revision 3 (approved by coordinator after B attempt 1 BLOCKED)

Single-hunk fix in `verify_prefix` only: the pinned prefix inventory TSV
begins with exactly one fixed header row, which is now consumed and
validated verbatim (`path\tbytes\tsha256`; any deviation raises
PreflightBlocked `inventory header mismatch`), and only the data rows
are parsed afterwards.  All data-row parsing, messages, walk/hash
verification and version checks are byte-for-byte unchanged.  Old driver
hash `5f85ddff1f15e67d8fdb80b672c2f2f35d45c039b6d200de8732e2bf406c5088`
(51167 bytes); new `24ae2af60f8d3eb48ab2e01da8463699133d951accabfbbd0c2bc7354a469a03`
(51532 bytes); observer unchanged.  Revision-3 static validation:
compile PASS; `control --help`/`old-prefix --help` exit 0; synthetic
inventory test (header accepted with files=2/version=18.6 and matching
sha256; no-header and wrong-header rejected as `inventory header
mismatch`; malformed data row still `prefix inventory malformed entry`);
`load_events` self-test and dummy bootstrap build PASS.

## Static validation performed (revision 2; authoring only, no experiments)

- In-memory `compile()` of both files: PASS (observer 18563 bytes,
  driver 51167 bytes; no CR bytes; ASCII).
- `build_bootstrap()` dummy assembly compiles and visibly contains the
  P2-1 truncation check and the P3-1 cause/context traversal.
- `control --help` and `old-prefix --help` exit 0.
- Refusal path: wrong `--plan-sha256` prints `BLOCKED plan sha256
  mismatch`, exits 2, and creates no directories; missing required
  old-prefix arguments exit 2 via argparse.
- `load_events()` self-test with synthetic whitelisted input (including
  the new `via` field) and a missing-file case: PASS.
- No bootstrap execution, no socket use, no PG, no OLD source, no SSH.

## Transfer and launch (reference only; NOT executed here)

Copy both files byte-identical (LF) into a fresh Linux task tools
directory, e.g. `/home/ubuntu/pal-m0-startup-20261113-yx2fyoje/task-tools/r03-next-<unique>/`,
and verify the sha256 values above before use. Driver and observer must
stay in the same directory. Launch with the existing locked environment
interpreter under `-I -B` (never from an extracted archive directory),
filling the unique invocation id and fresh non-reusing data/evidence
directories:

    <environments/r03/bin/python> -I -B <tools>/r03_next_driver.py control \
        --repo <ROOT/checkout> --data <fresh tasktmp dir> \
        --evidence <fresh evidence dir> --invocation-id <unique-id> \
        --plan-sha256 027f877e8c7ce01779c046fd15891b0f4b092416563df86cc467e66c74bf55d5

    <environments/r03/bin/python> -I -B <tools>/r03_next_driver.py old-prefix \
        --repo <ROOT/checkout> --data <fresh tasktmp dir> \
        --evidence <fresh evidence dir> \
        --prefix <ROOT/environments/pg18-portable> \
        --prefix-inventory <ROOT/environments/pg18-portable.inventory.tsv> \
        --prefix-inventory-sha256 812d410a15f218b432c2ea3ed531a8e266509e92fd533ceeebc58e1f1af651e4 \
        --control-report <control run evidence>/report.json \
        --invocation-id <unique-id> \
        --plan-sha256 027f877e8c7ce01779c046fd15891b0f4b092416563df86cc467e66c74bf55d5

The old-prefix run refuses to start unless every precondition above is
supplied, the plan hash matches, the prefix inventory matches its
sha256, and the control report outcome is `CONTROL_EXPECTED_MATCH`
(plan: A failure or anomaly means B NOT_RUN).

## Exit codes

- control: 0 expected match; 2 preflight blocked; 3 completed but
  `CONTROL_UNEXPECTED`; 4 execution failure.
- old-prefix: 0 not reproduced and cleanup verified stopped; 1 otherwise
  (first failure preserved, see report.json outcome field; includes
  `EVIDENCE_BUDGET_EXCEEDED`); 2 preflight blocked or refused start; 5
  control precondition failed.

## Discipline summary enforced in code

Original `_OLD_ENTRY`/`_OLD_RUNNER`/`_SEED_PAYLOAD` texts are taken from
the pinned C3 module at runtime (sha256 recorded); the observer bootstrap
embeds them verbatim via `repr()` and changes no `sys.argv`, cwd,
environment or exit code. No monkeypatching of sockets or product
functions; `_psql`/`_control('status')` aggregate counters only; all
`/proc/net/tcp{,6}` reads capped at 65537 bytes with `UNAVAILABLE` on
truncation or any anomaly (never zero); whitelisted fields only (no
addresses, inodes, PIDs or foreign ports); observer failures become
`observer_unavailable` events and disable observation without touching
the business exception; first failure preserved; single attempt with no
retry/sleep/port replacement; cleanup only through the existing harness
helper; no sudo or privilege escalation anywhere.
