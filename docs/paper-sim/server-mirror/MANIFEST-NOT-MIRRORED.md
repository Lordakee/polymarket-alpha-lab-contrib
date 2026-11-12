# Not-mirrored inventory — ~/paper-sim @ 2026-11-12 (FX-03, swimlane C1)

8258 files / ~9.646 GB were inventoried but NOT mirrored. They stay on the
server as run evidence. Breakdown by top-level directory (files, bytes):

| top-level | files | bytes | what it is |
| --- | ---: | ---: | --- |
| round2..round47 | 1457 | ~5,927,000,000 | per-round raw API snapshots (Gamma/CLOB/ESPN/FotMob JSON), scan outputs, candidates JSONs, logs — the round archives |
| fotmob_backfill | 5285 | 1,563,911,920 | FotMob per-match backfill JSON (cache-like bulk data) |
| nba | 203 | 192,726,219 | NBA research raw snapshots (tag/pubsearch JSON) |
| tools | 1246 | 374,135,826 | `tools/fotmob_cache/` HTTP cache + logs (code already mirrored) |
| review | 108 | 12,173,591 | audit/review workspace: V-6/V-7 run (`review/audit2026_v6_v7/`), WP-P4/P5 evidence, p2b rerun, fix backups — analysis products, not decision loop |
| soccer | 14 | 315,672,255 | early soccer research raw dumps |
| big5_20261108 | 8 | 6,218,088 | merged xG snapshot + validators' outputs |
| championship_20261108 | 5 | 599,536 | Championship xG refresh data |
| intl | 12 | 18,413,538 | WP-INTL validation raw data (code mirrored) |
| (root files) | 1 | 1,735 | `understat_latest_pointer.json` (pointer; target `understat_latest.json` is a symlink into `big5_20261108/`) |

By extension the not-mirrored set is dominated by `json` (8008 files,
9.54 GB), then `log` (114), `md` (40 — mostly per-round reports and
feasibility notes), `py` (22, all under `review/` or `__pycache__`), `pyc`
(18), `gz` (14), `txt`/`tsv`/`html`/`csv`/`bak` (rest).

Round archives (round2..round47) and all raw data remain the authoritative
run evidence on the server; `review/` products are cited where relevant by
the audit handoff (`docs/handoffs/2026-11-12-audit/`). Nothing in the
not-mirrored set was modified, moved or deleted.

## Appendix: server-address occurrences inside mirrored files (FX-24 follow-up)

Byte-faithful mirror keeps them; coordinator decides on redaction/aliasing:

- `round29/raw/write_scan.py:8` — `'server':'ubuntu@SERVER_HOST_REDACTED'`
- `round39/eredivisie_validate.py:848` — report header string
- `tools/fotmob_validate.py:681` — report header string
- `intl/wp_intl3/polymarket_alpha_lab/papersim/league_strength.py:204` — comment
