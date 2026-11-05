"""Static import-graph analysis for polymarket_alpha_lab.

Usage: python -I importgraph.py <repo_root> <out_json>

Edges: `import x`, `from x import y` (absolute + relative, incl. submodule
imports via `from pkg import mod`), and any string literal that names a
module of the package (catches lazy importlib.import_module("...") calls).
"""
from __future__ import annotations

import ast
import json
import sys
from collections import deque
from pathlib import Path

PKG = "polymarket_alpha_lab"


def module_name(path: Path, src_root: Path) -> str:
    rel = path.relative_to(src_root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_relative(mod: str, is_pkg: bool, level: int, target: str | None) -> str:
    base = mod.split(".")
    if not is_pkg:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    out = ".".join(base)
    if target:
        out = f"{out}.{target}" if out else target
    return out


def collect(path: Path, mod: str, is_pkg: bool, known: set[str]):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        return set(), set(), f"syntax error: {exc}"
    static, lazy = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = resolve_relative(mod, is_pkg, node.level, node.module)
            else:
                base = node.module or ""
            static.add(base)
            for alias in node.names:
                cand = f"{base}.{alias.name}"
                if cand in known:
                    static.add(cand)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in known:
                lazy.add(node.value)
    return static, lazy, None


def build(src_root: Path, extra_files: list[Path]):
    files = sorted(src_root.rglob("*.py"))
    mods = {module_name(f, src_root): f for f in files}
    known = set(mods)
    graph: dict[str, set[str]] = {}
    lazy_graph: dict[str, set[str]] = {}
    for m, f in mods.items():
        static, lazy, err = collect(f, m, f.name == "__init__.py", known)
        graph[m] = {t for t in static if t in known}
        lazy_graph[m] = lazy - graph[m]
    extra_edges = {}
    for f in extra_files:
        static, lazy, _ = collect(f, f.stem, False, known)
        extra_edges[str(f)] = {t for t in (static | lazy) if t in known}
    return mods, graph, lazy_graph, extra_edges


def parents(m: str) -> list[str]:
    parts = m.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def reach(starts, graph, lazy_graph, include_pkg_init: bool, include_lazy: bool = True):
    seen, q = set(), deque(starts)
    while q:
        m = q.popleft()
        if m in seen or m not in graph:
            continue
        seen.add(m)
        nxt = set(graph[m])
        if include_lazy:
            nxt |= lazy_graph[m]
        if include_pkg_init:
            nxt |= {p for p in parents(m) if p in graph}
        q.extend(nxt - seen)
    return seen


def main() -> None:
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    src_root = root / "src"
    scripts = sorted((root / "scripts").glob("*.py"))
    tests = sorted((root / "tests").rglob("*.py"))
    mods, graph, lazy_graph, script_edges = build(src_root, scripts)
    _, _, _, test_edges = build(src_root, tests)

    entry = [
        f"{PKG}.cli", f"{PKG}.__main__", f"{PKG}.papersim.cli",
        f"{PKG}.project_postgres.cli", f"{PKG}.research_linux_relay",
        f"{PKG}.research_process_linux",
    ]
    entry = [e for e in entry if e in graph]
    script_targets = sorted(set().union(*script_edges.values()))

    # A: what actually gets loaded when the CLI runs (package __init__ included).
    loaded = reach(entry + script_targets, graph, lazy_graph, include_pkg_init=True)
    # B: what the CLI / scripts depend on through their own imports, NOT via the
    #    eager re-exports in polymarket_alpha_lab/__init__.py.
    graph_no_init = dict(graph)
    graph_no_init[PKG] = set()
    lazy_no_init = dict(lazy_graph)
    lazy_no_init[PKG] = set()
    used = reach(entry + script_targets, graph_no_init, lazy_no_init, include_pkg_init=False)
    init_exports = graph[PKG]

    test_imported = set().union(*test_edges.values())
    all_mods = set(graph)
    not_used = all_mods - used - {PKG}
    only_tests = {m for m in not_used if m in test_imported}
    orphan = not_used - test_imported

    # In-degree within src (who imports me), excluding the package __init__.
    indeg = {m: 0 for m in all_mods}
    for m, ts in graph.items():
        if m == PKG:
            continue
        for t in ts | lazy_graph[m]:
            indeg[t] += 1

    sizes = {m: mods[m].stat().st_size for m in mods}
    lines = {m: sum(1 for _ in mods[m].open(encoding="utf-8")) for m in mods}

    def agg(names):
        return {"modules": len(names), "lines": sum(lines[n] for n in names),
                "bytes": sum(sizes[n] for n in names)}

    report = {
        "total": agg(all_mods),
        "entry_points": entry,
        "script_targets_count": len(script_targets),
        "loaded_by_cli_incl_init": agg(loaded),
        "used_by_cli_excl_init": agg(used),
        "init_direct_exports": len(init_exports),
        "not_used_by_cli": agg(not_used),
        "not_used_but_tested": agg(only_tests),
        "orphans_no_src_no_tests": agg(orphan),
        "orphans_list": sorted(orphan)[:200],
        "zero_indegree_not_entry": sorted(
            m for m in all_mods if indeg[m] == 0 and m not in entry and m != PKG
            and m not in script_targets and not m.endswith("__init__")
        )[:50],
        "zero_indegree_count": sum(
            1 for m in all_mods if indeg[m] == 0 and m not in entry and m != PKG
            and m not in script_targets
        ),
        "cli_direct_imports": len(graph.get(f"{PKG}.cli", set())),
        "not_used_by_suffix": {},
    }
    by_suffix: dict[str, list[int]] = {}
    for m in not_used:
        suf = m.rsplit("_", 1)[-1]
        by_suffix.setdefault(suf, [0, 0])
        by_suffix[suf][0] += 1
        by_suffix[suf][1] += lines[m]
    report["not_used_by_suffix"] = dict(
        sorted(by_suffix.items(), key=lambda kv: -kv[1][1])[:15]
    )
    used_by_suffix: dict[str, int] = {}
    for m in used:
        suf = m.rsplit("_", 1)[-1]
        used_by_suffix[suf] = used_by_suffix.get(suf, 0) + 1
    report["used_by_suffix"] = dict(sorted(used_by_suffix.items(), key=lambda kv: -kv[1])[:15])
    report["_used_modules"] = sorted(used)
    report["_loaded_modules"] = sorted(loaded)
    # Test files that import at least one used module vs only unused modules.
    t_used = t_unused_only = t_none = 0
    for f, ts in test_edges.items():
        if ts & used:
            t_used += 1
        elif ts:
            t_unused_only += 1
        else:
            t_none += 1
    report["test_files_touching_used"] = t_used
    report["test_files_only_unused"] = t_unused_only
    report["test_files_no_pkg_import"] = t_none
    test_lines_unused_only = sum(
        sum(1 for _ in Path(f).open(encoding="utf-8")) for f, ts in test_edges.items() if ts and not (ts & used)
    )
    report["test_lines_only_unused"] = test_lines_unused_only
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    skip = ("orphans_list", "zero_indegree_not_entry", "_used_modules", "_loaded_modules")
    print(json.dumps({k: v for k, v in report.items() if k not in skip}, indent=2))


if __name__ == "__main__":
    main()
