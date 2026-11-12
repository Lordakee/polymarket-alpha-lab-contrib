# Scan dispatch template (mandatory blocks for every paper-sim scan round prompt)

Created 2026-11-04 by the codex-review FIX worker (findings #4 and #11).
Every dispatch that starts a new scan round (crypto, soccer, or mixed) MUST
include the blocks below verbatim. Copy-pasting model formulas or data paths
from earlier rounds without these blocks is how findings #4 and #11 happened.

---

## Block 1 — Crypto model math MUST be imported, never re-derived

The corrected, audited implementation lives in the library:

    /home/ubuntu/polymarket-alpha-lab/src/polymarket_alpha_lab/papersim/crypto_model.py

Scan scripts MUST import and call it:

```python
import sys
_LIB_SRC = '/home/ubuntu/polymarket-alpha-lab/src'
if _LIB_SRC not in sys.path:
    sys.path.insert(0, _LIB_SRC)
from polymarket_alpha_lab.papersim.crypto_model import (
    TouchProbability, conservative_edges, terminal_probability, touch_probability)
```

- Touch / terminal A/B probabilities: `touch_probability(...)` /
  `terminal_probability(...)` (A = zero log drift, B = mean-flat
  `mu_log = -sigma^2/2`).
- Edges: `conservative_edges(pair, yes_ask=..., no_ask=...)`, i.e.
  `edge_yes = min(pA, pB) - yes_ask`, `edge_no = (1 - max(pA, pB)) - no_ask`.
  NEVER price one side off a single convention (the round-29/33 bug) and
  NEVER use `max(pA,pB)` as the YES fair value (the round-12/13/15 bug).
- Reference implementation to copy: `round33/raw/scan_crypto_33.py`
  (fixed 2026-11-04; import-based). It keeps the r19 already-touched
  shortcuts (`kind == 'dn' and K >= S` -> 1.0) around the library calls.
- Historical round scripts (r5-r29) are archives of what ran; do not copy
  formulas from them and do not edit them retroactively (FIXES.md 3).

## Block 2 — Understat Big-5 snapshot resolves through the pointer

The validated-snapshot pointer is:

    ~/paper-sim/understat_latest.json          (symlink -> newest VALID snapshot)
    ~/paper-sim/understat_latest_pointer.json  (sidecar: target, sha256, counts)

- Maintained automatically by `tools/understat_refresh.py`: every successful
  validation (fresh recovery or idempotent `already_complete`) atomically
  re-points the symlink and refreshes the sidecar; failures never touch it.
- Scan scripts MUST load through `understat_latest.json` and echo the sidecar
  provenance into their output (reference: `round33/raw/soccer_scan33.py`,
  fixed 2026-11-04). NEVER hard-code `roundNN/raw/xg_understat_NN.json` —
  that is why recovery output (round28) never reached the scanner (round25).
- Freshness policy: read `fetched_at_utc` / `latest_match_date` from the
  sidecar and record it in the scan output. If the snapshot is stale (no
  league advances past the last known date), the scan must say so in its
  output (`xg_bases.big5`) and degrade conservatively — do not silently
  model on stale data as if fresh.

## Block 3 — Prior-round copying rules

- Copy the newest round's scripts, then apply the round's changes.
- Before running a scan, re-run the library selfcheck
  (`python3 -m polymarket_alpha_lab.papersim.cli selfcheck` style entry,
  as recorded in the round docstring) and record the result.
- Report-only / paper-only boundaries are unchanged: no live trading, no
  credentials, no order mutation.
