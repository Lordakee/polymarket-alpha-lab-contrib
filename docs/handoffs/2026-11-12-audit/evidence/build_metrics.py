#!/usr/bin/env python3
"""Assemble the published evidence files from audit_static.py output plus git creation dates.

Audit evidence tooling for docs/handoffs/2026-11-12-audit. Reads two input
files and writes three output files; it imports and executes nothing from the
audited repository.

Inputs
  1. <static.json>   the full output of:  python3 -I audit_static.py <repo_root> <static.json>
  2. <added_src.txt> first-commit dates of every source file, produced in the repo by:
       git log --diff-filter=A --name-only --format='@@%ad' --date=short -- 'src/*.py' > added_src.txt
     (needs the complete history of the audited branch; a tree-only fetch is enough)

Outputs (written into <out_dir>)
  metrics.json             headline numbers + by-creation-month table + method notes
  reachable_modules.txt    one reachable module per line
  unreachable_modules.tsv  module, lines, created (YYYY-MM-DD), family

Usage: python3 -I build_metrics.py <static.json> <added_src.txt> <out_dir> <baseline_commit>
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

PKG = "polymarket_alpha_lab"
KEEP = [
    "total", "root_init_lines", "root_init_direct_imports", "entry", "used_excl_init", "loaded_incl_init",
    "not_used", "not_used_but_test_imported", "not_used_no_tests", "not_used_no_tests_list", "group_reach",
    "zero_indegree_not_used", "families_first_token", "suffix_top", "functions_all", "functions_used",
    "functions_not_used", "worst_cc", "longest", "exact_dups", "struct_dups", "hygiene_all", "hygiene_used",
    "hygiene_not_used", "classes", "tests",
]


def creation_dates(path: Path) -> dict[str, str]:
    """Earliest add date per module (git log lists newest first, so the last hit wins)."""
    created: dict[str, str] = {}
    date = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("@@"):
            date = line[2:]
            continue
        if line.startswith("src/") and line.endswith(".py") and date:
            module = line[4:-3].replace("/", ".")
            if module.endswith(".__init__"):
                module = module[: -len(".__init__")]
            created[module] = date
    return created


def main() -> None:
    static_path, added_path, out_dir, baseline = sys.argv[1:5]
    report = json.loads(Path(static_path).read_text(encoding="utf-8"))
    created = creation_dates(Path(added_path))
    lines = report["_lines"]
    used = set(report["_used"])
    out = {key: report[key] for key in KEEP}

    per_month = collections.defaultdict(
        lambda: {"modules": 0, "lines": 0, "reachable_modules": 0, "reachable_lines": 0})
    for module, count in lines.items():
        if module == PKG:
            continue
        cell = per_month[created[module][:7]]
        cell["modules"] += 1
        cell["lines"] += count
        if module in used:
            cell["reachable_modules"] += 1
            cell["reachable_lines"] += count
    out["by_creation_month"] = dict(sorted(per_month.items()))

    burst = [m for m in lines
             if m != PKG and m not in used and "2026-07-03" <= created[m] <= "2026-07-16"]
    out["unreachable_created_2026_07_03_to_07_16"] = {
        "modules": len(burst), "lines": sum(lines[m] for m in burst)}
    out["method"] = {
        "baseline_commit": baseline,
        "tool": "evidence/audit_static.py (AST only; no repository code is imported or executed); "
                "this file is assembled from its output by evidence/build_metrics.py",
        "entry_points": "console script polymarket_alpha_lab.cli, polymarket_alpha_lab.__main__, every src "
                        "module with an if __name__ == \"__main__\" guard, every package module imported by "
                        "scripts/*.py and tools/**/*.py",
        "edges": "import / from-import (absolute and relative) plus string literals equal to a package "
                 "module name",
        "root_init": "edges out of polymarket_alpha_lab/__init__.py are excluded for the reachable set "
                     "(used_excl_init); loaded_incl_init includes them",
        "creation_dates": "git log --diff-filter=A --name-only --format='@@%ad' --date=short -- 'src/*.py' "
                          "(first commit that added each file; full history of main)",
    }

    target = Path(out_dir)
    (target / "metrics.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "reachable_modules.txt").write_text("\n".join(sorted(used)) + "\n", encoding="utf-8")
    rows = ["module\tlines\tcreated\tfamily"]
    for module in sorted(report["_not_used"]):
        short = module[len(PKG) + 1:]
        family = short.split(".")[0] if "." in short else short.split("_")[0]
        rows.append(f"{module}\t{lines[module]}\t{created[module]}\t{family}")
    (target / "unreachable_modules.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("reachable", len(used), "unreachable", len(report["_not_used"]))


if __name__ == "__main__":
    main()
