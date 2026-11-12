# FX-02 read-only segment — live view state, ledger snapshot, and view-diff (2026-11-12)

Swimlane C3, paper-only, read-only. DB: host `127.0.0.1:55432`, database
`paper_sim`, user `paper_sim`, on the project-private
native cluster under `~/pal-artifacts/paper-sim/pg` on
`ubuntu@SERVER_HOST_REDACTED` (PostgreSQL 18.6). Password read from
`~/pal-artifacts/paper-sim/.pgpw` into an env var and never printed. All DB
access was `pg_get_viewdef` + `\copy ... csv header` (SELECT-only). Nothing
on the server or in the DB was modified. This complements — does not repeat —
the V-6/V-7 run at `~/paper-sim/review/audit2026_v6_v7/` (read first; its
per-entry, from-first-principles recomputation stands).

## Headline (this is the V-2 answer, and it CORRECTS audit P-3's assumption)

**Both performance views on the live cluster are ALREADY the fixed
versions.** The premise of FX-02's replacement segment — "replace the two
views (needs OD-H ①)" — is already satisfied in effect on the live database
by an earlier operator action; what remains is bookkeeping, not SQL.

1. `public.model_performance` — live `pg_get_viewdef`
   (`model_performance_viewdef.sql` in this directory) is the
   **share-proportional allocation** version, structurally the same query as
   `supabase/migrations/20261107000000_papersim_perf_view_fix.sql`
   (`weighted_decisions` window over `partition by market_id`,
   `valid_shares` guard, `allocated_pnl = r.pnl * d.shares / market_shares`,
   `total_pnl` NULL unless every allocation is computable, round only the
   final aggregate). **Empirical proof**: applying the migration's logic in
   Python over the exported `decisions.csv` × `resolutions.csv` (no DB)
   reproduces all 16 live view rows to the cent, including count columns
   (16/16 `total_pnl` matches, 0 count mismatches) — see table below. The
   PRE-FIX (double-count) logic over today's same data would instead show
   `crypto_touch = 2,795.00` (exactly +1,305.20 higher), the number
   FX-02's acceptance text expected the fix to eliminate; the live view
   shows 1,489.80 today.
2. `public.forecast_calibration` — live `pg_get_viewdef`
   (`forecast_calibration_viewdef.sql`) carries **all three** hit clauses in
   BOTH `forecast_hits` and `avg_prob_of_realized` (YES/YES-basket matched to
   `r.outcome = d.side`, `NO`→NO, `NO-basket`→NO) plus the
   natural-outcomes-only `WHERE` filter — i.e. it matches the fixed text in
   `ledger.ddl()` / migration `20261101000000_papersim_ledger.sql`. The
   `ledger.py:302-305` OPERATIONAL NOTE ("live view still carries the
   one-clause-short avg_prob_of_realized predicate") is **stale** relative
   to today's live cluster and needs an appended correction (a docs change,
   not a DB change).

### Provenance of the fix (best available evidence)

- `~/pal-artifacts/paper-sim/pg.log` (cluster log since 2026-10-10 13:38Z)
  records exactly ONE view-DDL statement: a **FAILED**
  `CREATE OR REPLACE VIEW model_performance` on **2026-10-30 04:34:16Z**
  (error: `cannot change name of view column "win_rate_pct" to "exits"`).
  Successful statements are not logged (statement logging is off), so the
  successful replacement that produced today's definitions is unlogged.
- A backup table `public.pre_fixfix_backup_20261104` (117 rows;
  `src | row_id | market_id | bak_ts`) and `~/paper-sim/review/FIXES.md`
  (2026-11-04 14:31) evidence a fix campaign on **2026-11-04** — the
  replacement most plausibly dates from that campaign. The 10-30 snapshot
  (`review/settled_ledger.json`, 04:17Z, 17 minutes before the failed
  attempt) predates it and still contains the double-counted row, which is
  why the audit saw P-3 in the snapshot. `DELIVERY_PLAN.md` §73's
  "迁移未应用" statement (11-07) does not describe today's live state.
- V-9: this is a **standalone single-application cluster** (databases:
  `paper_sim`, `postgres`, `template0/1`), not the V1 project cluster, with
  **no migration ledger** (objects: `decisions`, `resolutions`, `bankroll`,
  `scope_events` (2 owner-directive rows), `pre_fixfix_backup_20261104`,
  views `model_performance`, `forecast_calibration`). Schema changes are
  operator-applied by hand. FX-09's ledger v2 therefore still needs its own
  managed-schema answer.

## Snapshot (full ledger CSVs, read-only `\copy`, 2026-11-12 ~13:45Z)

| file | rows | sha256 |
| --- | ---: | --- |
| `decisions.csv` | 71 | `33614121151bdcd27ab3aeec8fd581f1f3eaa479b118f726ba764fdf05db0526` |
| `resolutions.csv` | 65 | `2df24707459991421b6fc14dfe192e7c938ecbd85117d50580331a8bd116ea40` |
| `bankroll.csv` | 68 | `c39cbe29684752f3b086f2345ec1afdfeb6e499d9483ca88ac6a352e2e7873eb` |
| `model_performance_view.csv` | 16 | `4971161e10f1ffa477f8d2493c86ad30f7adeeb5ebc983d5705bfaa66be60795` |
| `forecast_calibration_view.csv` | 12 | `1768dca28c5f6af60a8b1c0c5fba4aba98da7e8c39c69083e71ccf961beafc6c` |
| `model_performance_viewdef.sql` | — | `0ed3a82d883d4afd37c6710b068743ad8362ced9584e9783f7410bdbce0aa0c7` |
| `forecast_calibration_viewdef.sql` | — | `d833e9d6dfcfd371c3f0ff21b6424b5e63c8bf24df083f066bd3338143c3aff8` |

Row counts identical to the V-6 export two hours earlier (71/65/68) — no new
settles between the runs; free-text fields (`question`, `reason`,
`evidence`, `note`) scanned for credentials/keys before entering the repo
(zero hits; same field scope as the 10-30 precedent).
`decisions` has 18 business columns; the live table still lacks the repo
DDL's `paper_only/report_only/readonly` columns (repo DDL ahead — unchanged
V-6 finding).

## The view-diff table (the OD-H decision input)

Per-queue `total_pnl`: LIVE view vs the two logics computed OUTSIDE the DB
over the same export (fix-migration allocation vs pre-fix double-count):

| market_type | n | live view | fix logic (allocation) | pre-fix logic (double count) | overstatement removed |
| --- | ---: | ---: | ---: | ---: | ---: |
| basket | 1 | 2.28 | 2.28 | 2.28 | 0.00 |
| btts | 7 | -454.68 | -454.68 | -454.68 | 0.00 |
| commodity_touch | 1 | -135.73 | -135.73 | -135.73 | 0.00 |
| crypto_daily | 1 | -200.00 | -200.00 | -200.00 | 0.00 |
| **crypto_touch** | 4 | **1,489.80** | **1,489.80** | **2,795.00** | **1,305.20** |
| election | 2 | 609.62 | 609.62 | 609.62 | 0.00 |
| geopolitics | 1 | 72.58 | 72.58 | 72.58 | 0.00 |
| macro | 1 | -60.70 | -60.70 | -60.70 | 0.00 |
| market_cap | 1 | -113.06 | -113.06 | -113.06 | 0.00 |
| match_winner | 9 | 137.26 | 137.26 | 137.26 | 0.00 |
| other | 1 | 171.30 | 171.30 | 171.30 | 0.00 |
| ou_over | 21 | 687.87 | 687.87 | 687.87 | 0.00 |
| ou_under | 3 | 340.13 | 340.13 | 340.13 | 0.00 |
| season_winner | 1 | -46.17 | -46.17 | -46.17 | 0.00 |
| spread | 1 | 837.00 | 837.00 | 837.00 | 0.00 |
| team_total | 11 | 430.83 | 430.83 | 430.83 | 0.00 |
| **TOTAL** | **66** | **3,768.33** | **3,768.33** | **5,073.53** | **1,305.20** |

- The only multi-entry settled market is **3866000** (2 decisions, shares
  1,456 + 1,099, resolution pnl +1,305.20): allocation splits it
  743.79 / 561.41, sum preserved in full — the migration's own acceptance
  case, now live.
- Count columns (`total_settled`, `wins`, `losses`, `exits`) recompute to
  the live values exactly (0 mismatches), as the migration intends (only PnL
  attribution changes). Nuance kept as-is from the frozen semantics:
  `win`/`loss` outcome labels (post-audit settlements) and `VOIDED` rows
  count in `total_settled` and PnL but not in wins/losses/exits.
- Cross-check vs V-6: V-6's from-first-principles per-entry gross is
  3,768.62 vs the view's 3,768.33 — the 0.29 gap is exactly the two known
  recording-rounding markets V-6 flagged (5314573, 5856548: 0.15/0.20).
  The two independent recomputations agree: the live view no longer double
  counts.

## What this means for OD-H (decision input, no action taken here)

- OD-H ① "replace the two views" is **already the de-facto state**; running
  the migration now would be a no-op semantically (it would only re-record
  the same definitions through a tracked file — worth doing for ledger
  hygiene, no longer risk-bearing).
- Remaining reconciliation work (repo-side, for the FX-05/plan owner):
  append a dated correction to DELIVERY_PLAN §73's "迁移未应用" and to
  `ledger.py:302-305`'s stale operational note; record the 2026-10-30
  failed attempt + 2026-11-04 fix-campaign provenance and the
  `pre_fixfix_backup_20261104` backup table in the plan record.
- Fees remain OUT of both view and migration (P-2/FX-01): every number
  above is still gross-of-fees; V-6's net figures (+20.70% net ROI
  full-current) remain the fee-adjusted reference.
