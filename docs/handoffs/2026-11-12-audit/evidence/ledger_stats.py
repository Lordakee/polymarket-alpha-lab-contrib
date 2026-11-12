#!/usr/bin/env python3
"""Descriptive statistics for an exported paper-sim settled ledger (read-only).

Audit evidence tooling for docs/handoffs/2026-11-12-audit. It reads one JSON
export (a list of settled rows with the fields of
docs/paper-sim/review-2026-10-30/settled_ledger.json) and prints summary
statistics. It opens no database, performs no network access and writes nothing.

Usage: python3 -I ledger_stats.py <settled_ledger.json> [--seed 12345] [--boot 20000]

Fee estimate: the official Polymarket schedule read on 2026-11-12
(https://docs.polymarket.com/trading/fees): fee = C * feeRate * p * (1 - p),
C = shares, taker only. Only two rates are applied here (crypto 0.07 for
market types starting with "crypto", sports 0.05 for everything else), so the
fee total is an ESTIMATE, not an accounting figure; whether a fee was actually
in force for each historical market is not verified by this script.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random


def hit(row: dict) -> int:
    side, outcome = row["side"], row["outcome"]
    if side in ("YES", "YES-basket"):
        return 1 if outcome == side else 0
    return 1 if outcome == "NO" else 0


def fee_rate(row: dict) -> float:
    return 0.07 if str(row["market_type"]).startswith("crypto") else 0.05


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--boot", type=int, default=20000)
    args = parser.parse_args()
    rows = json.load(open(args.ledger, encoding="utf-8"))
    n = len(rows)
    stake = sum(float(r["stake"]) for r in rows)
    pnl = sum(float(r["pnl"]) for r in rows)
    print(f"rows={n} stake={stake:.2f} pnl={pnl:.2f} roi_pct={pnl / stake * 100:.2f}")
    print("settled_at", min(r["settled_at"] for r in rows)[:10], "..", max(r["settled_at"] for r in rows)[:10])
    print("outcomes", dict(collections.Counter(r["outcome"] for r in rows)))

    for key in ("market_type", "team"):
        table = collections.defaultdict(lambda: [0, 0.0, 0.0])
        for r in rows:
            cell = table[r[key]]
            cell[0] += 1
            cell[1] += float(r["stake"])
            cell[2] += float(r["pnl"])
        print(f"--- by {key} (n, stake, pnl)")
        for name, (count, st, p) in sorted(table.items(), key=lambda kv: -kv[1][2]):
            print(f"{name:18s} {count:3d} {st:9.2f} {p:9.2f}")

    ordered = sorted((float(r["pnl"]) for r in rows), reverse=True)
    print("top5_pnl", [round(x, 2) for x in ordered[:5]], "sum_top5", round(sum(ordered[:5]), 2),
          "sum_rest", round(sum(ordered[5:]), 2))
    print("top1_share_of_total_pnl_pct", round(ordered[0] / pnl * 100, 1))
    rest = [r for r in rows if float(r["pnl"]) != ordered[0]]
    rest_stake = sum(float(r["stake"]) for r in rest)
    rest_pnl = sum(float(r["pnl"]) for r in rest)
    print(f"excluding_top1 rows={len(rest)} pnl={rest_pnl:.2f} roi_pct={rest_pnl / rest_stake * 100:.2f}")

    rng = random.Random(args.seed)
    rois = []
    for _ in range(args.boot):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        rois.append(sum(float(r["pnl"]) for r in sample) / sum(float(r["stake"]) for r in sample))
    rois.sort()
    print("bootstrap_roi_95ci_pct", round(rois[int(0.025 * args.boot)] * 100, 1),
          round(rois[int(0.975 * args.boot)] * 100, 1),
          "p_roi_le_0", round(sum(1 for x in rois if x <= 0) / args.boot, 3))

    returns = [float(r["pnl"]) / float(r["stake"]) for r in rows]
    mean = sum(returns) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in returns) / (n - 1))
    print("per_bet_return mean", round(mean, 4), "sd", round(sd, 4), "t", round(mean / (sd / math.sqrt(n)), 3))

    natural = [r for r in rows if r["outcome"] != "EXITED"]
    brier_model = sum((float(r["model_prediction"]) - hit(r)) ** 2 for r in natural) / len(natural)
    brier_price = sum((float(r["price"]) - hit(r)) ** 2 for r in natural) / len(natural)
    print("natural_rows", len(natural), "hits", sum(hit(r) for r in natural),
          "brier_model", round(brier_model, 4), "brier_entry_price", round(brier_price, 4))
    diffs = [(float(r["model_prediction"]) - hit(r)) ** 2 - (float(r["price"]) - hit(r)) ** 2 for r in natural]
    boot = []
    for _ in range(args.boot):
        sample = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        boot.append(sum(sample) / len(sample))
    boot.sort()
    print("brier_diff_model_minus_price mean", round(sum(diffs) / len(diffs), 4), "95ci",
          round(boot[int(0.025 * args.boot)], 4), round(boot[int(0.975 * args.boot)], 4))

    gross_equal = 0
    for r in natural:
        st, price = float(r["stake"]), float(r["price"])
        gross = st / price - st if hit(r) else -st
        if abs(gross - float(r["pnl"])) < 0.02:
            gross_equal += 1
    print("natural_rows_where_recorded_pnl_equals_gross_payoff", gross_equal, "of", len(natural))
    fees = sum((float(r["stake"]) / float(r["price"])) * fee_rate(r) * float(r["price"]) * (1 - float(r["price"]))
               for r in rows)
    print("estimated_entry_taker_fees", round(fees, 2), "roi_pct_net_of_estimated_entry_fees",
          round((pnl - fees) / stake * 100, 2))


if __name__ == "__main__":
    main()
