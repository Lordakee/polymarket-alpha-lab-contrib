#!/usr/bin/env python3
"""Independent recomputation for the 2026-11-13 M0 execution review.

Reviewer's own code. It reads only the exported data files passed as
arguments and imports nothing from the reviewed repository.

Usage (from the repository root, any commit that has both inputs):
  python3 -I recompute_ledger_and_views.py \
      docs/paper-sim/ledger-snapshots/2026-11-12 \
      docs/paper-sim/review-2026-10-30/settled_ledger.json

What it prints
  A. per-entry first-principles performance of the current ledger export,
     with fees under the executor's team rule (crypto_* 7%, others 5%) and a
     sensitivity under an official-category guess; entry-only and
     entry+exit net returns; bootstrap interval; largest-market share.
  B. model_performance recomputed under the fix-migration logic and under
     the pre-fix logic, compared with the exported live view rows.
  C. the 2026-10-30 review snapshot: as published, per-entry recomputed, and
     with every entry settled by the snapshot time.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

NATURAL = ("YES", "NO", "YES-basket")


def team_rule_rate(team: str) -> float:
    """The executor's scan-lineage rule: crypto_* teams 7%, everything else 5%."""
    return 0.07 if team.lower().startswith("crypto_") else 0.05


def official_guess_rate(team: str, market_type: str) -> float:
    """Reviewer's alternative mapping to the official category table (sensitivity only)."""
    t = team.lower()
    if t.startswith("crypto_"):
        return 0.07
    if t.startswith("sports_"):
        return 0.05
    if market_type == "geopolitics":
        return 0.0
    if t == "politics":
        return 0.04
    if t in ("equity_indices", "commodities_gold"):
        return 0.04  # finance
    if t == "ent_tech":
        return 0.04  # tech
    return 0.05  # economics / other


def natural_hit(side: str, outcome: str) -> bool:
    return (
        (side in ("YES", "YES-basket") and outcome == side)
        or (side == "NO" and outcome == "NO")
        or (side == "NO-basket" and outcome == "NO")
    )


def entry_rows(dec, res):
    """Per-entry first-principles rows for resolved, non-voided decisions."""
    per_market = defaultdict(list)
    for d in dec:
        per_market[d["market_id"]].append(d)
    rows, voided, unresolved = [], 0, 0
    for d in dec:
        r = res.get(d["market_id"])
        if r is None:
            unresolved += 1
            continue
        outcome = r["outcome"]
        if outcome == "VOIDED":
            voided += 1
            continue
        stake, price = float(d["stake"]), float(d["price"])
        shares = stake / price
        exit_price = None
        if outcome in NATURAL:
            gross = shares - stake if natural_hit(d["side"], outcome) else -stake
        elif outcome == "win":
            gross = shares - stake
        elif outcome == "loss":
            gross = -stake
        elif outcome == "EXITED":
            assert len(per_market[d["market_id"]]) == 1, "multi-entry exit"
            gross = float(r["pnl"])
            exit_price = (gross + stake) / shares
        else:
            raise ValueError(outcome)
        rows.append(
            dict(id=int(d["id"]), market_id=d["market_id"], team=d["team"], market_type=d["market_type"],
                 stake=stake, price=price, shares=shares, gross=gross, exit_price=exit_price,
                 outcome=outcome, res_ts=r["ts"], dec_ts=d["ts"])
        )
    return rows, voided, unresolved


def _rate(row, rate_fn):
    return rate_fn(row["team"]) if rate_fn is team_rule_rate else rate_fn(row["team"], row["market_type"])


def exit_fees(row, rate_fn):
    if row["exit_price"] is None:
        return 0.0
    return row["shares"] * _rate(row, rate_fn) * row["exit_price"] * (1.0 - row["exit_price"])


def fees(row, rate_fn):
    """Entry fee plus (for exits) the sell fee at the reconstructed exit price."""
    return row["stake"] * _rate(row, rate_fn) * (1.0 - row["price"]) + exit_fees(row, rate_fn)


def summarize(label, rows, rate_fn=team_rule_rate, boot=True):
    stake = sum(r["stake"] for r in rows)
    gross = sum(r["gross"] for r in rows)
    fee = sum(fees(r, rate_fn) for r in rows)
    exit_fee = sum(exit_fees(r, rate_fn) for r in rows)
    entry_fee = fee - exit_fee
    net = gross - fee
    print(f"[{label}] entries={len(rows)} stake={stake:.2f} gross={gross:.2f} "
          f"entry_fees={entry_fee:.2f} exit_fees={exit_fee:.2f} net={net:.2f}")
    print(f"    gross_roi={gross / stake * 100:.2f}%  net_roi(entry fees only)={(gross - entry_fee) / stake * 100:.2f}%  "
          f"net_roi(entry+exit fees)={net / stake * 100:.2f}%")
    if boot:
        rng = random.Random(20261113)
        nets = [(r["gross"] - fees(r, rate_fn), r["stake"]) for r in rows]
        sims = []
        for _ in range(20000):
            sample = [nets[rng.randrange(len(nets))] for _ in nets]
            sims.append(sum(x for x, _ in sample) / sum(s for _, s in sample) * 100)
        sims.sort()
        print(f"    bootstrap over entries (20000 resamples, entry+exit net ROI) 95% interval: {sims[int(0.025 * len(sims))]:.1f} .. {sims[int(0.975 * len(sims))]:.1f}")
        by_market = defaultdict(float)
        for r in rows:
            by_market[r["market_id"]] += r["gross"] - fees(r, rate_fn)
        top = max(by_market.items(), key=lambda kv: kv[1])
        print(f"    top market {top[0]} net={top[1]:.2f} share_of_net={top[1] / net * 100:.1f}%  "
              f"net ROI without it: {(net - top[1]) / (stake - sum(r['stake'] for r in rows if r['market_id'] == top[0])) * 100:.2f}%")
    return stake, gross, fee, net


def q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def view_logic(dec, res):
    """model_performance total_pnl per market_type under both view logics (exact decimals)."""
    market_shares = defaultdict(Decimal)
    for d in dec:
        market_shares[d["market_id"]] += Decimal(d["shares"])
    fix, prefix, counts = defaultdict(Decimal), defaultdict(Decimal), defaultdict(lambda: [0, 0, 0, 0])
    for d in dec:
        r = res.get(d["market_id"])
        if r is None:
            continue
        mt = d["market_type"]
        pnl = Decimal(r["pnl"])
        prefix[mt] += pnl
        fix[mt] += pnl * Decimal(d["shares"]) / market_shares[d["market_id"]]
        c = counts[mt]
        c[0] += 1
        if r["outcome"] in NATURAL and pnl > 0:
            c[1] += 1
        if r["outcome"] in NATURAL and pnl <= 0:
            c[2] += 1
        if r["outcome"] == "EXITED":
            c[3] += 1
    return fix, prefix, counts


def main() -> None:
    snap, old_json = Path(sys.argv[1]), Path(sys.argv[2])
    dec = list(csv.DictReader(open(snap / "decisions.csv", encoding="utf-8", newline="")))
    res = {r["market_id"]: r for r in csv.DictReader(open(snap / "resolutions.csv", encoding="utf-8", newline=""))}

    print("=== A. current ledger (2026-11-12 snapshot), per-entry first principles ===")
    rows, voided, unresolved = entry_rows(dec, res)
    print(f"decisions={len(dec)} resolved_markets={len(res)} voided_entries={voided} unresolved_entries={unresolved}")
    summarize("team-rule fees", rows)
    summarize("official-category guess (sensitivity)", rows, official_guess_rate, boot=False)
    recorded_total = sum(Decimal(r["pnl"]) for r in res.values())
    print(f"recorded market-level pnl total (all resolutions): {recorded_total}")
    by_type = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for r in rows:
        b = by_type[r["market_type"]]
        b[0] += 1; b[1] += r["stake"]; b[2] += r["gross"]; b[3] += fees(r, team_rule_rate)
    print("per queue: type entries stake gross fees net gross_roi% net_roi%")
    for mt, (n, st, g, f) in sorted(by_type.items()):
        print(f"   {mt:16s} {n:3d} {st:9.2f} {g:9.2f} {f:7.2f} {g - f:9.2f} {g / st * 100:7.1f} {(g - f) / st * 100:7.1f}")

    print("\n=== B. view logic over the exported base tables vs exported live view rows ===")
    fix, prefix, counts = view_logic(dec, res)
    live = {r["market_type"]: r for r in csv.DictReader(open(snap / "model_performance_view.csv", encoding="utf-8", newline=""))}
    match_fix = match_prefix = count_ok = 0
    for mt in sorted(live):
        lv = Decimal(live[mt]["total_pnl"])
        f, p = q2(fix[mt]), q2(prefix[mt])
        c = counts[mt]
        cok = [int(live[mt][k]) for k in ("total_settled", "wins", "losses", "exits")] == c
        match_fix += lv == f; match_prefix += lv == p; count_ok += cok
        flag = "" if f == p else "   <-- discriminating row"
        print(f"   {mt:16s} live={lv:>9} fix={f:>9} prefix={p:>9} counts_ok={cok}{flag}")
    print(f"rows={len(live)} match_fix={match_fix} match_prefix={match_prefix} counts_ok={count_ok} "
          f"types_only_in_recompute={sorted(set(fix) - set(live))}")
    print(f"totals: live={sum(Decimal(live[m]['total_pnl']) for m in live)} fix={q2(sum(fix.values()))} prefix={q2(sum(prefix.values()))}")

    print("\n=== C. the 2026-10-30 review snapshot (40 rows) ===")
    old = json.load(open(old_json, encoding="utf-8"))
    st = sum(float(r["stake"]) for r in old); pn = sum(float(r["pnl"]) for r in old)
    fee = xfee = 0.0
    for r in old:
        stake, price = float(r["stake"]), float(r["price"])
        rate = team_rule_rate(r["team"])
        fee += stake * rate * (1 - price)
        if r["outcome"] == "EXITED":
            shares = stake / price
            xp = (float(r["pnl"]) + stake) / shares
            xfee += shares * rate * xp * (1 - xp)
    fee += xfee
    print(f"[as published, recorded pnl] rows={len(old)} stake={st:.2f} pnl={pn:.2f} "
          f"entry_fees={fee - xfee:.2f} exit_fees={xfee:.2f}")
    print(f"    gross_roi={pn / st * 100:.2f}%  net_roi(entry fees only)={(pn - fee + xfee) / st * 100:.2f}%  "
          f"net_roi(entry+exit fees)={(pn - fee) / st * 100:.2f}%")
    ids_old = {int(r["id"]) for r in old}
    dec_by_id = {int(d["id"]): d for d in dec}
    # rows whose recorded pnl disagrees with first principles
    for r in old:
        stake, price = float(r["stake"]), float(r["price"])
        if r["outcome"] in NATURAL:
            fp = stake / price - stake if natural_hit(r["side"], r["outcome"]) else -stake
            if abs(fp - float(r["pnl"])) > 1.0:
                print(f"   row id={r['id']} recorded pnl={r['pnl']} first-principles={fp:.2f} (stake {stake}, price {price})")
    # entries settled by the snapshot time according to the current ledger
    cutoff = "2026-10-30 04:17"
    settled_then = [r for r in rows if r["res_ts"] < cutoff]
    ids_then = {r["id"] for r in settled_then}
    print(f"current-ledger entries with resolution ts < {cutoff}Z (non-voided): {len(settled_then)}; "
          f"in old snapshot but not in that set: {sorted(ids_old - ids_then)}; in that set but not in old snapshot: {sorted(ids_then - ids_old)}")
    summarize("40 snapshot ids, per-entry first principles", [r for r in rows if r["id"] in ids_old], boot=False)
    summarize("all entries settled by the snapshot time (incl. missing ones)", settled_then, boot=False)


if __name__ == "__main__":
    main()
