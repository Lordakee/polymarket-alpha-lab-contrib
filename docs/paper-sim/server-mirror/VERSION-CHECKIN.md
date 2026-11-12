# Version check-in — server decision-loop inventory (FX-03, swimlane C1)

Inventory date: 2026-11-12 (UTC). Host: `ubuntu@SERVER_HOST_REDACTED`
(`ser223321960800`). Tree inventoried: `/home/ubuntu/paper-sim` (8673 files,
9,649,071,091 bytes total). This check-in records WHAT code was running at
inventory time, per fix-list FX-03 step 6/8 and blueprint 8.4.

## Library code the server scripts execute against

The scan/model scripts under `~/paper-sim` import
`polymarket_alpha_lab.papersim.*` from the repo checkout at
`/home/ubuntu/polymarket-alpha-lab` (via `sys.path` insertion). At inventory
time (2026-11-12T13:04Z):

- `git rev-parse HEAD` = `9e761317131ab0e6197f0fc4f8e72c828eccd016`
  — identical to the audit-handoff baseline commit `9e761317` pushed by the
  coordinator. V-3 (does the server run the reviewed code?) answers YES for
  this instant.
- `git status --porcelain` = 0 lines (clean worktree).
- Server `python3` = 3.12.3 (release tuple pins 3.12.14; same minor, older
  patch — noted, not fixed here).
- One vendored copy of repo papersim modules exists INSIDE the mirrored tree:
  `intl/wp_intl3/polymarket_alpha_lab/papersim/` (intl_data, intl_model,
  league_strength, soccer_model, xg). It is mirrored byte-faithfully like
  everything else; it duplicates modules that main already carries (see
  commit `0d6cbc03`, WP-INTL).

## Scheduled jobs (crontab -l, ubuntu)

- `*/30 * * * * /usr/bin/python3 /home/ubuntu/paper-sim/tools/understat_refresh.py
  >> /home/ubuntu/paper-sim/round28/raw/understat_cron.log 2>&1
  # paper-sim-understat-round28-recovery` — the only paper-sim cron entry.
  (`tools/understat_recovery.cron` in the mirror records the same line.)
- One additional cron entry for an unrelated third-party tool exists and is
  out of scope; it embeds a live API key and is deliberately NOT reproduced
  here or anywhere in this mirror.

## Ledger database location (context for FX-02/OD-H, V-9)

The `paper_sim` database runs from a project-private native PostgreSQL
cluster at `~/pal-artifacts/paper-sim/pg` (data directory listing only;
nothing inside was read or modified), port 55432, password file
`~/pal-artifacts/paper-sim/.pgpw` (never printed). This is a separate
cluster from the V1 project database. No migration ledger manages it; view
state is documented in `../ledger-snapshots/2026-11-12/`.

## What is mirrored vs not

- Mirrored: 415 script files (.py/.sh/.cron plus `tools/scan_dispatch_template.md`),
  3,663,662 bytes, every file sha256-verified against the server after
  extraction. See `MANIFEST.sha256`.
- Not mirrored: 8258 data/report/log/cache files (round raw JSON archives,
  candidates JSONs, logs, `tools/fotmob_cache/`, `review/` audit workspace,
  `__pycache__`). Summarized in `MANIFEST-NOT-MIRRORED.md`.
- Excluded by rule: anything under `~/pal-artifacts` (credentials/cluster),
  `.pgpw`, `.env`-style files. A pre-mirror secret scan over all 415 files
  (PGPASSWORD literal, private keys, DSN-embedded passwords, api keys,
  bearer tokens, known key fragments) returned ZERO hits.
- Server-address scan: 4 mirrored files contain the literal host string
  `ubuntu@SERVER_HOST_REDACTED` in comments/report headers (recorded in
  `MANIFEST-NOT-MIRRORED.md` appendix). They are addresses, not credentials;
  mirror is byte-faithful, so they are left as-is for the coordinator to
  handle per FX-24.

## Version check-in rule going forward (FX-03 step 8)

From this date, every scan round must record at scan start: repo
`git rev-parse HEAD` + worktree-clean flag for the code the scan imports,
written into that round's output files (until ledger v2 lands, then into the
ledger per FX-09). The template for this exists in the mirrored
`tools/scan_dispatch_template.md`; the obligation is fix-list FX-03 item 8
and DELIVERY_PLAN section 75's pre-11-24 wiring evidence.
