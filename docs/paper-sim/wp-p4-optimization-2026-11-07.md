# WP-P4 historical optimization delivery — SHADOW ONLY

Implementation and historical validation are complete. The evidence does **not** establish an overall improvement over frozen production and does **not** authorize promotion. Production numerics, entry behavior, thresholds and paper-only/report-only/readonly boundaries are unchanged.

Base: `0dab0bd53d351396a1844ad9c9748b3d7d2774a1`. Branch: `codex/wp-p4-optimize`. Implementation tip before this report: `664beb131415dd8dcfda1d0ff1214201a6d782ae`. The final delivery commit is the commit containing this report and its companion integrity manifest; the final response supplies its full SHA. This task explicitly prohibits remote pushes, so delivery is local rather than GitHub-published.

## Implemented work

- T1 / P4-0a: new migration `20261107000000_papersim_perf_view_fix.sql` allocates each market resolution PnL in proportion to decision shares before grouping by market type. The synthetic 3866000 regression reproduces **2,795.00 -> 1,489.80**. No migration was applied. Old migration text and `ledger.ddl()` remain immutable history; consumers must separately review the new migration. Invalid share allocation makes the affected total NULL. Counts remain decision-level. Rounding happens per final category; displayed category totals can differ by cents from the unrounded unique-market grand total.
- T2 / P4-1: opt-in `papersim.recalib` estimates exponentially weighted, opponent-adjusted team xG attack/defence, actual-score league home/away levels, league/global priors, and actual-score Dixon–Coles rho. Completed-round and timestamp contracts are explicit. The module returns probabilities, parameters, fallback sources and convergence status. No production facade imports it.
- T3: literal official-round expanding windows; nested training-only half-life `{60,120,240}` and team-prior `{4,8,16}` selection; frozen production ten-variant medians; league-average-xG Poisson lambda baseline; per-fixture 1X2 and totals losses; 2,000-replicate paired matchweek intervals; source manifests and exclusions; optional descriptive market MAD.
- T4 / P4-2: nested sparse-team k selection over `{0,4,8,12,16,inf}`, with other settings fixed at 120-day half-life and ordinary-team prior 8. A shared 1,000-iteration numerical budget yields 114/114 converged fits. The study does not alter `xg.py`.

## Fair comparison on identical fixtures

There are **639 shadow forecasts in 65 folds**, of which **360 fixtures in 36 folds** have an actual complete prior season for production replay. The other 279 forecasts are historical 2025 Eredivisie/Championship observations; no 2024 production prior exists. They are excluded from every production-paired comparison.

Every cell below is **production / recalibrated / league-average lambda**, scored on the same fixtures. Lower is better. 1X2 Brier is the sum of the three squared class errors. Natural-log loss is used. Totals loss is the equally weighted mean of O1.5, O2.5 and O3.5 binary losses per fixture: 1,080 line observations for the paired cohort.

| League | Paired fixtures | 1X2 Brier: P / R / L | 1X2 log-loss: P / R / L | Totals log-loss: P / R / L |
|---|---:|---|---|---|
| EPL | 70 | 0.642145 / 0.639292 / 0.675239 | 1.064653 / 1.058552 / 1.111097 | 0.637012 / 0.616226 / 0.644456 |
| La Liga | 30 | 0.567310 / 0.582827 / 0.621977 | 0.956052 / 0.979537 / 1.033501 | 0.550050 / 0.579185 / 0.609202 |
| Serie A | 80 | 0.556542 / 0.564781 / 0.627918 | 0.947039 / 0.959662 / 1.040130 | 0.550718 / 0.595242 / 0.570736 |
| Bundesliga | 54 | 0.607450 / 0.613742 / 0.640861 | 1.013890 / 1.022219 / 1.061342 | 0.601798 / 0.598094 / 0.617982 |
| Championship | 72 | 0.609890 / 0.611920 / 0.639702 | 1.017493 / 1.020316 / 1.059818 | 0.608668 / 0.609601 / 0.633622 |
| Eredivisie | 54 | 0.629322 / 0.613211 / 0.657363 | 1.044990 / 1.021129 / 1.086186 | 0.602114 / 0.594341 / 0.605965 |
| Ligue 1 | 0 | unavailable | unavailable | unavailable |
| All paired | 360 | 0.603307 / 0.604810 / 0.645339 | 1.009471 / 1.011281 / 1.067405 | 0.594403 / 0.601149 / 0.613225 |

The raw production coordinate medians are retained exactly. Their sums range from **0.98773027 to 1.00533593**; only categorical scoring renormalizes them into a proper three-class vector. Raw-median Brier and log-loss sensitivity are also retained in JSON. Market MAD uses raw medians, without normalization.

| League | Recalibrated minus production 1X2 LL | Paired 95% matchweek interval | Blocks |
|---|---:|---|---:|
| EPL | -0.006100 | [-0.022608, +0.009659] | 7 |
| La Liga | +0.023486 | [+0.013503, +0.041788] | 3 |
| Serie A | +0.012623 | [-0.003222, +0.026916] | 8 |
| Bundesliga | +0.008328 | [-0.016580, +0.033107] | 6 |
| Championship | +0.002823 | [-0.009864, +0.015635] | 6 |
| Eredivisie | -0.023862 | [-0.053978, +0.008095] | 6 |
| All paired | +0.001811 | [-0.007597, +0.010589] | 36 |

EPL and Eredivisie improve on production by point estimate; their intervals include zero. La Liga deteriorates on only three blocks, so the apparently separated interval must not be treated as strong inference. The other leagues deteriorate by point estimate. Aggregate recalibrated-minus-production deltas are Brier **+0.001502** (95% interval **[-0.005020,+0.007648]**), 1X2 LL **+0.001811** (**[-0.007597,+0.010589]**) and totals LL **+0.006746** (**[-0.006769,+0.019351]**).

Against the simple league-average lambda baseline on all 639 fixtures, recalibration reduces 1X2 LL by **0.055288**, with interval **[-0.075029,-0.036306]**. Beating that simple model does not demonstrate improvement over the existing production ensemble. Few seasons, shared teams, serial dependence, changing league mix and multiple comparisons limit all reported bootstrap intervals. They are descriptive intervals, not promotion gates.

## Source audit and unsupported claims

- Six domestic leagues support strict current-season evaluation. Ligue 1 has zero eligible strict-prefix predictions: source result 31948 reverses PSG/Rennes home and away versus the retained official schedule. The raw match-detail files needed to resolve it are absent. The row is quarantined; missing round 1 blocks subsequent complete-prefix folds.
- Championship 2025 contained three abandoned fixtures as well as their replays. IDs 4825094, 4825251 and 4825249 are excluded, leaving 552 valid prior-season games. There are 3,326 clean source matches after these three exclusions and the Ligue 1 exclusion.
- Postponed matches block affected prefixes. Six provider timestamp discrepancies are disclosed; the earlier time controls the prediction cutoff and the later time plus three hours controls the completion assumption. Neither is represented as observed xG publication time.
- Prior-season official round maps exist only for Championship and Eredivisie. Complete Big-5 2025 seasons are warmup priors, not fabricated matchweek histories. No 2024 xG season is fabricated.
- This is retrospective event-time replay of retained final snapshots, with a three-hour completion assumption. Original xG availability/revision times and historical fixture-announcement times are unavailable. It cannot stand in for prospective shadow logging.
- The referenced Euro 835-match fit set supplies scores/dates but not the required historical xG snapshots. The earlier future-information bridge concern is not certified or closed by this domestic study; P4-0b remains outstanding.

## Archived market MAD

The archive contains 78 distinct mapped fixtures; 69 qualify for the paired descriptive study, with 207 outcome quotes. The earliest usable scan is selected per fixture. The shadow configuration here is fixed at 120 days / 8 matches and is distinct from T3’s adaptive selection. Scan-report times span 2026-11-04T11:09:48Z to 2026-11-07T07:38:55Z. Exact quote acquisition timestamps were discarded, so **formal Gate E is unavailable**, regardless of a point estimate falling below 6c.

| League | Fixtures | Frozen midpoint MAD (c) | Fixed shadow midpoint MAD (c) |
|---|---:|---:|---:|
| Bundesliga | 9 | 5.3486 | 6.6824 |
| Championship | 13 | 5.5281 | 5.5132 |
| EPL | 10 | 7.5670 | 7.1752 |
| Eredivisie | 8 | 6.5041 | 6.0028 |
| La Liga | 10 | 6.7661 | 7.4688 |
| Ligue 1 | 9 | 7.8904 | 7.7874 |
| Serie A | 10 | 4.8526 | 4.3680 |
| All paired | 69 | 6.3030 | 6.3774 |

Aggregate ask-price MAD is **6.3576c production / 6.3756c shadow**. Both definitions are slightly worse in aggregate. Eredivisie midpoint shadow MAD is **6.002826c**, still above 6c; its ask-based 5.971433c cannot be substituted to declare Gate E passed. There is no historical 2025 market-price series or prospective Gate-E certification here. No closing-line-value claim is made.

## Sparse-team k study

75 earlier sparse fixtures form inner warmup; 93 outer fixtures involve either a team missing from the observed previous-league roster or a team with fewer than eight observed current-season matches. A missing 2024 season is not proof of promotion. Each outer cohort has six matchweek blocks. Every choice uses only earlier candidate predictions whose outcomes are in that outer training set.

| League | Outer fixtures | Final training-only k | Descriptive holdout grid winner | Nested policy LL |
|---|---:|---:|---:|---:|
| Championship | 58 | 12 | 4 | 1.057256 |
| Eredivisie | 35 | 0 | 0 | 0.955994 |

The pooled descriptive fixed-grid winner is k=0: outer LL **1.006526**, versus k=8 **1.029013**. Its paired difference is **-0.022488**, interval **[-0.061995,+0.015909]**, so the winner is noisy. The nested policy has pooled LL **1.019146**; Championship’s nested policy is worse than fixed k=8. The companion shrinkage report gives every candidate’s loss and interval. **k=8 is not established**, and neither the retrospective pooled winner nor the final league selections are a production promotion decision.

## Validation, review and first-attempt failures

- Required first commands ran successfully: clean `git status --short`; Python **3.12.3**. Base HEAD matched the requested revision.
- Original papersim baseline: **308 passed / 1 skipped**, without modifying existing tests. Final focused surface: **399 passed / 9 skipped**. The nine skips are eight opt-in SQL fixture cases plus the original opt-in ledger integration case.
- T1 SQL checks: **9 passed** using a connection-start read-only transaction and the migration SELECT over inline VALUES. No real table reads, temp tables, DDL, migration application or database writes occurred. Default unit runs do not open database connections.
- Selfcheck: **10/10**, full stdout **1,623 bytes**, SHA256 `91dfe5eeb72ed01aa6f3401040e61d41b75865c64c441ad7a65abbca87897d06`, byte-identical before/after. All pre-existing papersim source, frozen fixtures and existing test files remain byte-identical to base.
- Full existing repository suite: **41,076 passed / 102 skipped / 6 failed**. It is not green. Two newly exposed static assertions in `test_project_postgres.py::test_all_69_migrations_have_checked_in_receipts` and `test_research_dispatch.py::test_migration_tail_hashes_and_no_lease_or_destructive_ddl` pin 69 migrations; the authorized additive migration makes 70. Four backup tests encounter an occupied local port. A separate exact-base archive reproduced those four failures and passed the two count assertions (**4 failed / 2 passed**). Existing tests and host services were not changed to conceal these failures. The coordinator must resolve these broader merge gates.
- Independent read-only T1 review: **VERDICT: PASS**, with the nonblocking category-rounding limitation documented above.
- Independent T2 review initially **FAIL**: zero-weight old low-score rows could qualify a flat rho likelihood and spuriously choose its lower bound. Three new regression cases failed first, then passed after `026c1bfd`. Fresh final review: **VERDICT: PASS**; 36 estimator tests. Sixty-three ordinary positive-weight configurations had identical predictions before/after.
- Independent historical-tools review initially found two P2 issues: postponed older-round market targets could abort the archive, and the shrinkage CLI could overwrite its inputs or reuse an output path. Both were fixed with regressions. Final **VERDICT: PASS** independently checked folds, losses, nested choices, source hashes and actual market metrics.
- The first full T3 direct-script attempt computed folds but failed importing optional market support before writing outputs. After the entry-path fix, module and direct executions produced byte-identical reports. The final JSON remains SHA256 `51d7da0e6dd09176b8c6141ba1fd99dc7e63e0995ea4a354f6b5fc1c41ce7899`.
- The first k study reached the 80-iteration cap in three early inner k=0 fits. All candidates then received the same 1,000-iteration budget: 114/114 converged. Inner losses changed by up to 0.008313; final inner selections and all outer nested losses were unchanged. Both attempts are distinguished here.

## Prospective path — recommendation only

Keep this module isolated. The historical evidence does not justify production promotion. Freeze a version and a sample definition before observing future outcomes; retain the production comparator and all candidates, including rejected entries. Preserve the existing full-range variant screen.

Using retained official schedules and a conservative start after 2026-11-07 UTC, the first two wholly future rounds are **Eredivisie 13–14 (November 21–29)** and **Championship 16–17 (November 21–25)**. Those are the earliest proposed two-round shadow cohorts; a coordinator must recheck postponements and record every prediction before the first kickoff of each round. Rounds already partially played cannot be retroactively called prospective.

Other earliest proposed pairs are EPL 11–12, La Liga 13–14, Serie A 12–13, Bundesliga 10–11, and Ligue 1 11–12. Ligue 1’s source discrepancy must be repaired independently before claiming validated historical support. For the calibration priorities, a defensible proposed fixed sample is the first **108** eligible fixtures each: Eredivisie rounds 13–24 and Championship rounds 16–24, subject to complete-round and postponement handling declared before launch. This is a proposed research sample, not a newly activated gate or policy.

DELIVERY_PLAN section73 remains binding: at least two complete prospective matchweeks **and** a predeclared out-of-time sample, Gate E passing at the unchanged bar, and no A–D regression before any acceptance or sizing change. Eredivisie/Championship stay totals-only; cross-league MW remains ELIGIBLE_DEPRIORITIZED at $150; net edge>=5c, worst>=4c, spread<=6c and liquidity>=$5k remain frozen. Promotion belongs to the coordinator/owner. Nothing here authorizes real trading.

## Directly forwardable coordinator handoff

You are ZCode, independently reviewing local branch `codex/wp-p4-optimize` in `/home/ubuntu/polymarket-alpha-lab`. Review T1–T4 and the final report against base `0dab0bd53d351396a1844ad9c9748b3d7d2774a1`. The requested implementation and historical runs are already complete; do not redesign the grid after seeing these results, rediscover credentials, replay the old migration, or claim prospective validation. Implementation commits are `303d0837` (view), `fa794a07` (estimator), `026c1bfd` (rho review fix), `5fcc640e` (history/harness/market), and `664beb13` (nested k study), followed by this report commit. The response supplies the full final commit SHA.

This handoff is already on the local branch; no download, remote fetch or push was performed by this worker. GitHub-first publication is superseded for this task by the explicit no-push instruction. Use your separate owner authorization for any later merge/push. Do not touch the live PostgreSQL cluster during reproduction. Review the new view migration separately; its application remains a coordinator operation after review. Do not weaken safety flags, frozen numerics or acceptance thresholds.

Run these blocks in order in one Bash session. The first block performs read-only branch/base preflight; verify delivery integrity before executing project code. Stop on an integrity mismatch, changed input manifest, unexpected branch/base, nonfinite predictions, chronology failure, changed frozen files or new focused-test failure. Treat the documented broader suite failures as unresolved merge gates, not passing checks.

```bash
set -euo pipefail
cd /home/ubuntu/polymarket-alpha-lab
test "$(git branch --show-current)" = codex/wp-p4-optimize
test -z "$(git status --porcelain)"
git merge-base --is-ancestor 0dab0bd53d351396a1844ad9c9748b3d7d2774a1 HEAD
git merge-base --is-ancestor 664beb131415dd8dcfda1d0ff1214201a6d782ae HEAD
git log --oneline --reverse 0dab0bd53d351396a1844ad9c9748b3d7d2774a1..HEAD
.venv/bin/python -V
```

Verify the local delivery bytes before running the supplied tools:

```bash
.venv/bin/python - <<'PYVERIFY'
from pathlib import Path
import hashlib, json
m = json.loads(Path('docs/paper-sim/wp-p4-evidence-manifest.json').read_text())
for item in m['files']:
    data = Path(item['path']).read_bytes()
    assert len(data) == item['bytes'], item['path']
    assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
print('delivery integrity verified:', len(m['files']), 'files')
PYVERIFY
```

After the integrity check exits 0, verify the frozen behavior and focused tests:

```bash
.venv/bin/python -m polymarket_alpha_lab.papersim.cli selfcheck
env -u PAPERSIM_PG_DSN -u WP_P4_READONLY_PG .venv/bin/python -m pytest -q tests/test_papersim*.py tests/test_wp_p4*.py
git diff --check 0dab0bd53d351396a1844ad9c9748b3d7d2774a1..HEAD
```

Reproduce only into explicit output paths outside the read-only source archive:

```bash
mkdir -p /tmp/wp-p4-coordinator
.venv/bin/python -m tools.wp_p4_walkforward --input-root /home/ubuntu/paper-sim --json-out /tmp/wp-p4-coordinator/walkforward.json --md-out /tmp/wp-p4-coordinator/walkforward.md --include-market
.venv/bin/python -m tools.wp_p4_shrinkage --paper-sim-root /home/ubuntu/paper-sim --output-json /tmp/wp-p4-coordinator/shrinkage.json --output-markdown /tmp/wp-p4-coordinator/shrinkage.md
```

Each command must exit0; T3 JSON is deterministic on the pinned inputs. T4 includes `generated_at`, so compare all other fields. Source manifests in the JSON contain SHA256 and byte sizes; unchanged published inputs are required for an exact replay. Do not use later source revisions to silently replace these historical results. Return the reviewed commit, explicit PASS/FAIL findings, original and rerun test results separately, source/delivery integrity results, and your decision on the two migration-count assertions and four host-port failures. Preserve all prospective and promotion blockers.
