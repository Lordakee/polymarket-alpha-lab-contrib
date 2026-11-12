#!/usr/bin/env python3
"""Independent static audit of polymarket-alpha-lab.

Reads every file as DATA (ast.parse / text). Never imports or executes repo code.
Usage: python3 -I audit_static.py <repo_root> <out_json>
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

PKG = "polymarket_alpha_lab"
BRANCH = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler,
          ast.With, ast.AsyncWith, ast.Assert, ast.comprehension, ast.match_case)


def modname(path: Path, src_root: Path) -> str:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def resolve_rel(mod: str, is_pkg: bool, level: int, target):
    base = mod.split(".")
    if not is_pkg:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    out = ".".join(base)
    if target:
        out = f"{out}.{target}" if out else target
    return out


def cc(fn) -> int:
    c = 1
    for n in ast.walk(fn):
        if isinstance(n, BRANCH):
            c += 1
            if isinstance(n, ast.comprehension):
                c += len(n.ifs)
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
    return c


def norm(node) -> str:
    """Structure-only fingerprint: identifiers / attrs / literal values erased."""
    if isinstance(node, ast.AST):
        if isinstance(node, ast.Name):
            return "N"
        if isinstance(node, ast.arg):
            return "a"
        if isinstance(node, ast.Constant):
            return "C" + type(node.value).__name__
        out = [type(node).__name__, "("]
        for name, value in ast.iter_fields(node):
            if name in ("ctx", "type_comment", "kind"):
                continue
            if isinstance(value, str):
                out.append("_")
            else:
                out.append(norm(value))
            out.append(",")
        out.append(")")
        return "".join(out)
    if isinstance(node, list):
        return "[" + ",".join(norm(x) for x in node) + "]"
    if node is None:
        return "0"
    return "_" if isinstance(node, str) else repr(node)


def strip_doc(body):
    body = list(body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return body


def imports_of(tree, mod, is_pkg, known):
    static, lazy = set(), set()
    has_main = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                static.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_rel(mod, is_pkg, node.level, node.module) if node.level else (node.module or "")
            static.add(base)
            for a in node.names:
                cand = f"{base}.{a.name}"
                if cand in known:
                    static.add(cand)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in known:
                lazy.add(node.value)
        elif isinstance(node, ast.If):
            t = node.test
            if isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) and t.left.id == "__name__":
                has_main = True
    return {s for s in static if s in known}, lazy, has_main


def main() -> None:
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    src_root = root / "src"
    files = sorted(src_root.rglob("*.py"))
    mods = {modname(f, src_root): f for f in files}
    known = set(mods)

    graph, lazyg, has_main = {}, {}, {}
    lines, size = {}, {}
    funcs = []            # (mod, name, nlines, cc)
    exact = defaultdict(list)
    struct = defaultdict(list)
    hyg = defaultdict(Counter)   # mod -> Counter
    nclass = Counter()
    ndataclass = Counter()
    toplevel_defs = Counter()

    for m, f in mods.items():
        text = f.read_text(encoding="utf-8")
        size[m] = len(text.encode("utf-8"))
        tl = text.splitlines()
        lines[m] = len(tl)
        tree = ast.parse(text)
        st, lz, hm = imports_of(tree, m, f.name == "__init__.py", known)
        graph[m] = st - {m}
        lazyg[m] = lz - st - {m}
        has_main[m] = hm
        h = hyg[m]
        h["todo"] += sum(1 for l in tl if "TODO" in l or "FIXME" in l or "XXX" in l)
        toplevel_defs[m] = sum(1 for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
                if broad:
                    h["broad_except"] += 1
                    if node.type is None:
                        h["bare_except"] += 1
                    body = node.body
                    if len(body) == 1 and isinstance(body[0], ast.Pass):
                        h["broad_except_pass"] += 1
                    if not any(isinstance(x, ast.Raise) for b in body for x in ast.walk(b)):
                        h["broad_except_no_reraise"] += 1
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                h["print"] += 1
            elif isinstance(node, ast.Raise) and node.cause is not None and isinstance(node.cause, ast.Constant) and node.cause.value is None:
                h["raise_from_none"] += 1
            elif isinstance(node, ast.ClassDef):
                nclass[m] += 1
                for d in node.decorator_list:
                    s = ast.unparse(d)
                    if "dataclass" in s:
                        ndataclass[m] += 1
                        break
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                n = node.end_lineno - node.lineno + 1
                funcs.append((m, node.name, n, cc(node)))
                body = strip_doc(node.body)
                if body and n >= 6:
                    seg = "\n".join(l.strip() for l in tl[body[0].lineno - 1: node.end_lineno])
                    exact[hashlib.sha1(seg.encode()).hexdigest()].append((m, node.name, n))
                    struct[hashlib.sha1(norm(body).encode()).hexdigest()].append((m, node.name, n))

    # ---- entry points -------------------------------------------------
    def ext_edges(paths):
        res = {}
        for f in paths:
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:
                res[str(f.relative_to(root))] = set()
                continue
            st, lz, _ = imports_of(tree, f.stem, False, known)
            res[str(f.relative_to(root))] = st | lz
        return res

    script_edges = ext_edges(sorted((root / "scripts").glob("*.py")))
    tool_edges = ext_edges(sorted((root / "tools").rglob("*.py")))
    test_files = sorted((root / "tests").rglob("*.py"))
    test_edges = ext_edges(test_files)
    test_lines = {str(f.relative_to(root)): sum(1 for _ in f.open(encoding="utf-8")) for f in test_files}

    console = [f"{PKG}.cli", f"{PKG}.__main__"]
    main_guard = sorted(m for m, v in has_main.items() if v)
    script_targets = set().union(*script_edges.values()) if script_edges else set()
    tool_targets = set().union(*tool_edges.values()) if tool_edges else set()

    def reach(starts, use_init: bool):
        seen, q = set(), deque(starts)
        while q:
            m = q.popleft()
            if m in seen or m not in graph:
                continue
            seen.add(m)
            if m == PKG and not use_init:
                continue
            nxt = graph[m] | lazyg[m]
            if use_init:
                parts = m.split(".")
                nxt = nxt | {".".join(parts[:i]) for i in range(1, len(parts))}
            q.extend(nxt - seen)
        return seen

    entries_all = set(console) | set(main_guard) | script_targets | tool_targets
    used = reach(entries_all, use_init=False) - {PKG}
    loaded = reach(entries_all, use_init=True)

    # per-entry-group reach (excl init)
    groups = {
        "console_cli": reach(console, False) - {PKG},
        "scripts": reach(script_targets, False) - {PKG},
        "tools": reach(tool_targets, False) - {PKG},
        "main_guard_modules": reach(main_guard, False) - {PKG},
        "papersim_cli": reach([f"{PKG}.papersim.cli"], False) - {PKG},
        "project_postgres_cli": reach([f"{PKG}.project_postgres.cli"], False) - {PKG},
    }

    all_mods = set(graph) - {PKG}
    not_used = all_mods - used
    test_imported = set().union(*test_edges.values()) if test_edges else set()

    def agg(names):
        names = list(names)
        return {"modules": len(names), "lines": sum(lines[n] for n in names), "bytes": sum(size[n] for n in names)}

    # in-degree among src modules (excluding root __init__)
    indeg = Counter()
    for m, ts in graph.items():
        if m == PKG:
            continue
        for t in ts | lazyg[m]:
            indeg[t] += 1

    # ---- families ------------------------------------------------------
    def family(m: str) -> str:
        short = m[len(PKG) + 1:] if m.startswith(PKG + ".") else m
        if "." in short:
            return "pkg:" + short.split(".")[0]
        toks = short.split("_")
        return toks[0] if len(toks) == 1 else toks[0] + "_" + toks[1]

    fam = defaultdict(lambda: {"modules": 0, "lines": 0, "used_modules": 0, "used_lines": 0})
    fam1 = defaultdict(lambda: {"modules": 0, "lines": 0, "used_modules": 0, "used_lines": 0})
    for m in all_mods:
        for table, key in ((fam, family(m)), (fam1, family(m).split("_")[0])):
            d = table[key]
            d["modules"] += 1
            d["lines"] += lines[m]
            if m in used:
                d["used_modules"] += 1
                d["used_lines"] += lines[m]

    suffix = defaultdict(lambda: {"modules": 0, "lines": 0, "used_modules": 0, "used_lines": 0})
    for m in all_mods:
        short = m.rsplit(".", 1)[-1]
        suf = short.rsplit("_", 1)[-1] if "_" in short else short
        if re.fullmatch(r"v\d+", suf):
            suf = "v<N>"
        d = suffix[suf]
        d["modules"] += 1
        d["lines"] += lines[m]
        if m in used:
            d["used_modules"] += 1
            d["used_lines"] += lines[m]

    # ---- duplicates ------------------------------------------------------
    def dup(groups_, used_set):
        dg = [g for g in groups_.values() if len(g) > 1]
        red = sum(sum(x[2] for x in g) - max(x[2] for x in g) for g in dg)
        cross = [g for g in dg if len({x[0] for x in g}) > 1]
        used_groups = [g for g in dg if any(x[0] in used_set for x in g)]
        big = sorted(dg, key=lambda g: -len(g))[:15]
        return {
            "candidate_functions": sum(len(g) for g in groups_.values()),
            "dup_groups": len(dg),
            "functions_in_dup_groups": sum(len(g) for g in dg),
            "lines_in_dup_groups": sum(sum(x[2] for x in g) for g in dg),
            "redundant_lines_if_deduped": red,
            "cross_module_groups": len(cross),
            "functions_in_cross_module_groups": sum(len(g) for g in cross),
            "groups_touching_used": len(used_groups),
            "used_functions_in_dup_groups": sum(1 for g in dg for x in g if x[0] in used_set),
            "used_lines_in_dup_groups": sum(x[2] for g in dg for x in g if x[0] in used_set),
            "largest": [{"size": len(g), "lines_each": g[0][2], "modules": len({x[0] for x in g}),
                         "names": Counter(x[1] for x in g).most_common(3),
                         "example": f"{g[0][0]}.{g[0][1]}"} for g in big],
        }

    def fstats(sel):
        sel = list(sel)
        if not sel:
            return {}
        ln = sorted(f[2] for f in sel)
        c = sorted(f[3] for f in sel)
        return {"functions": len(sel), "median_lines": ln[len(ln) // 2], "p95_lines": ln[int(len(ln) * .95)],
                "over_100_lines": sum(1 for x in ln if x > 100), "over_300_lines": sum(1 for x in ln if x > 300),
                "median_cc": c[len(c) // 2], "p95_cc": c[int(len(c) * .95)],
                "cc_over_20": sum(1 for x in c if x > 20), "cc_over_50": sum(1 for x in c if x > 50)}

    def hsum(sel):
        tot = Counter()
        for m in sel:
            tot.update(hyg[m])
        return dict(tot)

    # ---- tests ---------------------------------------------------------
    t_used = t_unused_only = t_none = 0
    tl_used = tl_unused_only = tl_none = 0
    for f, ts in test_edges.items():
        ts = ts - {PKG}
        n = test_lines[f]
        if ts & used:
            t_used += 1; tl_used += n
        elif ts:
            t_unused_only += 1; tl_unused_only += n
        else:
            t_none += 1; tl_none += n

    used_untested = sorted(m for m in used if m not in test_imported)

    report = {
        "total": agg(all_mods),
        "root_init_lines": lines[PKG],
        "root_init_direct_imports": len(graph[PKG]),
        "entry": {
            "console": console,
            "main_guard_modules": main_guard,
            "script_files": len(script_edges),
            "script_targets": len(script_targets),
            "tool_files": len(tool_edges),
            "tool_targets": sorted(tool_targets),
        },
        "used_excl_init": agg(used),
        "loaded_incl_init": agg(loaded - {PKG}),
        "not_used": agg(not_used),
        "not_used_but_test_imported": agg(not_used & test_imported),
        "not_used_no_tests": agg(not_used - test_imported),
        "not_used_no_tests_list": sorted(not_used - test_imported)[:100],
        "group_reach": {k: agg(v) for k, v in groups.items()},
        "used_only_via_main_guard": agg(groups["main_guard_modules"] - groups["console_cli"] - groups["scripts"] - groups["tools"]),
        "used_untested_count": len(used_untested),
        "used_untested": used_untested[:60],
        "zero_indegree_not_used": agg([m for m in not_used if indeg[m] == 0]),
        "families_top": dict(sorted(fam.items(), key=lambda kv: -kv[1]["lines"])[:45]),
        "families_first_token": dict(sorted(fam1.items(), key=lambda kv: -kv[1]["lines"])[:30]),
        "suffix_top": dict(sorted(suffix.items(), key=lambda kv: -kv[1]["lines"])[:30]),
        "functions_all": fstats(funcs),
        "functions_used": fstats(f for f in funcs if f[0] in used),
        "functions_not_used": fstats(f for f in funcs if f[0] not in used),
        "worst_cc": [f"{m}.{n} cc={c} lines={l} used={m in used}" for m, n, l, c in sorted(funcs, key=lambda f: -f[3])[:20]],
        "longest": [f"{m}.{n} lines={l} cc={c} used={m in used}" for m, n, l, c in sorted(funcs, key=lambda f: -f[2])[:20]],
        "worst_cc_used": [f"{m}.{n} cc={c} lines={l}" for m, n, l, c in sorted((f for f in funcs if f[0] in used), key=lambda f: -f[3])[:25]],
        "exact_dups": dup(exact, used),
        "struct_dups": dup(struct, used),
        "hygiene_all": hsum(all_mods | {PKG}),
        "hygiene_used": hsum(used),
        "hygiene_not_used": hsum(not_used),
        "classes": {"all": sum(nclass.values()), "dataclasses": sum(ndataclass.values()),
                    "used": sum(v for k, v in nclass.items() if k in used)},
        "tests": {
            "files": len(test_edges), "lines": sum(test_lines.values()),
            "touching_used": {"files": t_used, "lines": tl_used},
            "only_unused": {"files": t_unused_only, "lines": tl_unused_only},
            "no_pkg_import": {"files": t_none, "lines": tl_none},
        },
        "biggest_used_modules": sorted(((lines[m], m) for m in used), reverse=True)[:40],
        "_used": sorted(used),
        "_not_used": sorted(not_used),
        "_lines": lines,
        "_graph_cli_direct": sorted(graph.get(f"{PKG}.cli", set()) | lazyg.get(f"{PKG}.cli", set())),
        "_hyg_by_mod": {m: dict(c) for m, c in hyg.items() if c},
    }
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    skip = {k for k in report if k.startswith("_")} | {"not_used_no_tests_list", "used_untested"}
    print(json.dumps({k: v for k, v in report.items() if k not in skip}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
