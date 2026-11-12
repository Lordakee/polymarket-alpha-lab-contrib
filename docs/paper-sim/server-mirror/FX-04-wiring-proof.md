# FX-04 wiring proof — cross-league match_winner enforcement in the live server scan pipeline

Written 2026-11-12 (swimlane C2, deadline 2026-11-24). All file:line citations
are pinned to the mirrored, sha256-verified copies under
`docs/paper-sim/server-mirror/` (byte-identical to
`/home/ubuntu/paper-sim/...` on ubuntu@SERVER_HOST_REDACTED; see `MANIFEST.sha256`).
Library behavior cited from repo commit `9e761317131ab0e6197f0fc4f8e72c828eccd016`,
which is exactly what the server scripts import (verified:
`/home/ubuntu/polymarket-alpha-lab` HEAD = `9e761317...`, clean worktree, see
`VERSION-CHECKIN.md`).

## Verdict

**WIRED — with two stated caveats (never yet exercised on a live candidate;
bridge flag asserted by convention).** The latest soccer scan script
(`round44/raw/scan44.py`, sha256 `435a30a9...`, mtime 2026-11-09) calls
`gates.check_cross_league_mw` on every cross-league match_winner row AND
sizes via `risk_policy.CROSS_LEAGUE_ML_CLASS` BEFORE any entry can be
accepted, inline in the executed per-market loop — not an import-only
reference. Same block exists in scan40/41/43/43a. The queue may be marked
"已接线" on the status board, with the caveats below carried into the 11-24
resumption note.

## Call-path trace in the LATEST scan (`round44/raw/scan44.py`)

1. **Imports** — `:61-68`: `sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")`;
   `from polymarket_alpha_lab.papersim import fotmob, gates, league_strength,
   risk_policy, soccer_model, xg`. The enforcement functions are the repo's,
   not local copies.
2. **Bridge load** — `:910-913`: `table = league_strength.load_kappa_report(KAPPA_PATH);
   kappa = dict(table.kappa)`, printed as `bridge loaded:` (κ table present
   at scan start).
3. **Cross classification** — `:961-965`: `cross = True` iff both clubs
   resolve and `lgh != lga` (home/away leagues from the snapshot's
   `TITLE_LEAGUE`).
4. **Bridged model path** — `:1017-1020`: cross fixtures are modeled ONLY
   through `soccer_model.fixture_variants(snapshot, home, lgh, away, lga,
   bridge=kappa)`; `:1024-1028`: if it returns None the fixture is recorded
   `model-void (variants None)` and `continue`s — it never reaches the
   market loop. Repo side, `xg.py:608-633 pair_lambdas` returns None for
   `home_league != away_league` unless a bridge table is supplied, and None
   again when either league is missing from the κ table
   (`league_strength.py:305-335 bridge_factor` — "the caller must refuse the
   fixture"). So every cross row that reaches step 7 has a real calibrated
   bridge by construction.
5. **Per-row gates** — `:1114-1118` `gates.under_risk_check(...)`; `:1121-1123`
   `report = gates.evaluate_candidate(quote, book["asks"], gamma_liquidity=liq,
   under_risk=ur, fee_rate=gates.FEE_RATE_SPORTS)` — `report.worst_variant_edge`
   is the library-computed worst-variant margin AFTER fees/haircut pipeline of
   the frozen gates; `:1125` `lib_pol = gates.suspension_policy(kind,
   cross_league=cross)` (registry stays descriptive; it does not establish
   candidacy — `gates.py:531-536`).
6. **THE ENFORCEMENT BLOCK** — `:1168-1189`, executed inline for every
   cross-league match_winner row (quoting verbatim from the mirror):

   ```python
   # cross-league MW enforcement (DELIVERY_PLAN section 72)
   if cross and kind == "ml":
       wve = report.worst_variant_edge
       if wve is None or not (wve == wve) or abs(wve) == float("inf"):
           row["cross_league_mw_check"] = {
               "error": "non-finite worst_variant_edge"}
           row["passed_numeric"] = False
       else:
           dec = gates.check_cross_league_mw(
               "ml", worst_variant_edge=wve,
               cross_league=True, bridge_present=True)
           tier = risk_policy.sizing_tier(
               market_class=risk_policy.CROSS_LEAGUE_ML_CLASS)
           row["cross_league_mw_check"] = {
               "passed": dec.passed, "failed": list(dec.failed),
               "worst_variant_edge": round(wve, 4),
               "sizing_class": risk_policy.CROSS_LEAGUE_ML_CLASS,
               "sizing_tier": tier.tier,
               "sizing_notional": tier.max_notional,
               "sizing_reason": tier.reason}
           if not dec.passed:
               row["passed_numeric"] = False
   ```

   Repo semantics being invoked: `gates.py:517-548` — cross-league
   match_winner fails unless `bridge_present` AND
   `worst_variant_edge >= +5c − ε` (`cross_league_bridge` /
   `cross_league_worst_edge` failure reasons); `risk_policy.py:277-283` —
   `CROSS_LEAGUE_ML_CLASS` can ONLY produce the fixed $150 marginal tier
   ("never the full $250"), with candidacy enforced upstream by
   `check_cross_league_mw`.
7. **Sizing applied to the row** — `:1190-1196`: `stake = 250` default,
   `if kind == "ml": stake = 150` — matches `tier.max_notional` ($150).
8. **Load-bearing for entry** — `:1220-1224`: `row["enterable"] = bool(
   row["passed_numeric"] and pol_eligible and not any(f.startswith(("BANNED",
   "SPREADS", "HELD")) ...))`; `:1206` numeric-pass flag; `:1314`
   `pass_rows` filter. Since step 6 sets `passed_numeric = False` when
   `dec.passed` is False, a failed cross-league check makes the row
   un-enterable — the check gates entry, it is not advisory.

## Coverage: which scans carry the block

| script (mirror path) | sha256 (prefix) | call site | note |
| --- | --- | --- | --- |
| `round40/raw/scan40.py` | `b664e517` | `:777-780` | docstring `:9-12` declares the wiring obligation |
| `round41/raw/scan41.py` | `cf28b479` | `:880-883` | docstring `:11-14` |
| `round43/raw/scan43.py` | `d26643a8` | `:894-897` | docstring `:15-18` |
| `round43/raw/scan43a.py` | `70b45e46` | `:1108-1111` | same lineage |
| `round44/raw/scan44.py` | `435a30a9` | `:1176-1180` | LATEST soccer scan (2026-11-09) |
| `round42/raw/finalize42.py` `:168-174`, `round42/raw/write_candidates42.py` `:52,:103-104` | — | — | round42 (Eredivisie, domestic) recorded "wiring armed ... NEVER TRIGGERED: no cross-league rows" |
| `round29-31/raw/soccer_scan*.py`, `round33-38` | — | — | OLDER lineage: only `suspension_policy(cross_league=...)` descriptive flag, NO `check_cross_league_mw` call — superseded by the scan40+ lineage |
| `round44/raw/scan44c.py` | — | — | horizon-probe assembler (international break): zero fixtures, zero candidates; no block, nothing to enforce |

**Future scans**: `tools/scan_dispatch_template.md` Block 3 mandates copying
the newest round's scripts for every new scan round; a post-break soccer
scan copied from `scan44.py` therefore inherits the block. Caveat: the
template has NO block that names `check_cross_league_mw` explicitly (Block 1
= crypto math imports, Block 2 = understat pointer, Block 3 = copying
rules) — coverage is by inheritance, not by an explicit template
obligation. Structural guarantee arrives only with FX-08 `decide_entry`.

## Caveats (state these on the status board next to "已接线")

1. **Never exercised on live data.** No scan output JSON anywhere under
   `~/paper-sim` contains a `cross_league_mw_check` row (searched all
   `roundNN/**.json`, 2026-11-12): rounds 40-44 had zero cross-league
   match_winner candidates in their windows (round42's finalize says
   "NEVER TRIGGERED"). First runtime proof will be the
   `cross_league_mw_check` key appearing in a future scan output; until
   then the evidence is code-path, not runtime.
2. **`bridge_present=True` is asserted, not re-derived** at the call site
   (`:1178`). It is justified by the model path (step 4: unbridged cross
   fixtures die as model-void before reaching the block), but nothing at
   the call site re-checks the κ pair. FX-08's `decide_entry` makes this
   invariant structural (bridge parameter explicit in the entrypoint).

## Reproduction

Mirror + repo at `9e761317`: `grep -n "check_cross_league_mw\|CROSS_LEAGUE_ML_CLASS"
docs/paper-sim/server-mirror/round4*/raw/scan4*.py` reproduces the table;
`sed -n '1168,1189p' docs/paper-sim/server-mirror/round44/raw/scan44.py`
reproduces the quoted block; hashes in `MANIFEST.sha256` tie both to the
server bytes.
