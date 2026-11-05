"""Static code-quality metrics without executing the analysed code.

Usage: python -I codequality.py <src_dir> <importgraph.json> <out_json>

* function length + cyclomatic complexity (McCabe-style branch count)
* duplicate functions: exact (same body text) and structural (identifiers,
  attribute names and literal values normalised away)
* a few hygiene counters (broad except, print, TODO)
Splits every metric by whether the module is reachable from an entry point
(the "used" set from importgraph.py).
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler,
                ast.With, ast.AsyncWith, ast.Assert, ast.comprehension, ast.match_case)


def complexity(fn: ast.AST) -> int:
    c = 1
    for node in ast.walk(fn):
        if isinstance(node, BRANCH_NODES):
            c += 1
            if isinstance(node, ast.comprehension):
                c += len(node.ifs)
        elif isinstance(node, ast.BoolOp):
            c += len(node.values) - 1
    return c


class Normalise(ast.NodeTransformer):
    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_arg(self, node):
        return ast.copy_location(ast.arg(arg="_", annotation=None), node)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        node.attr = "_"
        return node

    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)

    def visit_keyword(self, node):
        self.generic_visit(node)
        node.arg = "_" if node.arg else None
        return node


def body_without_docstring(fn):
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return body


def main() -> None:
    src = Path(sys.argv[1])
    used = set(json.loads(Path(sys.argv[2]).read_text())["_used_modules"])
    out = Path(sys.argv[3])

    exact = defaultdict(list)
    struct = defaultdict(list)
    funcs = []  # (module, name, lines, cc, used)
    hygiene = Counter()
    hygiene_used = Counter()
    for path in sorted(src.rglob("*.py")):
        rel = path.relative_to(src.parent).with_suffix("")
        mod = ".".join(p for p in rel.parts if p != "__init__")
        is_used = mod in used
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        lines = text.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
                if broad:
                    hygiene["broad_except"] += 1
                    hygiene_used["broad_except"] += is_used
                    if node.type is None:
                        hygiene["bare_except"] += 1
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                hygiene["print_calls"] += 1
                hygiene_used["print_calls"] += is_used
            elif isinstance(node, ast.Raise) and node.cause is not None and isinstance(node.cause, ast.Constant) and node.cause.value is None:
                hygiene["raise_from_none"] += 1
                hygiene_used["raise_from_none"] += is_used
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                n_lines = node.end_lineno - node.lineno + 1
                cc = complexity(node)
                funcs.append((mod, node.name, n_lines, cc, is_used))
                body = body_without_docstring(node)
                if not body:
                    continue
                seg = "\n".join(l.strip() for l in lines[body[0].lineno - 1: node.end_lineno])
                if n_lines >= 6:
                    exact[hashlib.sha1(seg.encode()).hexdigest()].append((mod, node.name, n_lines, is_used))
                    mod_ast = ast.Module(body=[Normalise().visit(ast.parse(ast.unparse(b))) for b in body], type_ignores=[])
                    struct[hashlib.sha1(ast.dump(mod_ast).encode()).hexdigest()].append((mod, node.name, n_lines, is_used))
        for i, l in enumerate(lines):
            if "TODO" in l or "FIXME" in l or "XXX" in l:
                hygiene["todo_fixme"] += 1

    def dup_stats(groups):
        dup_groups = [g for g in groups.values() if len(g) > 1]
        dup_funcs = sum(len(g) for g in dup_groups)
        dup_lines = sum(sum(x[2] for x in g) for g in dup_groups)
        redundant_lines = sum(sum(x[2] for x in g) - g[0][2] for g in dup_groups)
        biggest = sorted(dup_groups, key=lambda g: -len(g))[:10]
        return {
            "candidate_functions": sum(len(g) for g in groups.values()),
            "dup_groups": len(dup_groups),
            "functions_in_dup_groups": dup_funcs,
            "lines_in_dup_groups": dup_lines,
            "redundant_lines_if_deduped": redundant_lines,
            "largest_groups": [
                {"size": len(g), "lines_each": g[0][2], "example": f"{g[0][0]}.{g[0][1]}",
                 "names": Counter(x[1] for x in g).most_common(3)} for g in biggest
            ],
        }

    def fn_stats(sel):
        sel = list(sel)
        if not sel:
            return {}
        lens = sorted(f[2] for f in sel)
        ccs = sorted(f[3] for f in sel)
        return {
            "functions": len(sel),
            "median_lines": lens[len(lens) // 2],
            "p95_lines": lens[int(len(lens) * 0.95)],
            "over_100_lines": sum(1 for x in lens if x > 100),
            "over_300_lines": sum(1 for x in lens if x > 300),
            "median_cc": ccs[len(ccs) // 2],
            "p95_cc": ccs[int(len(ccs) * 0.95)],
            "cc_over_20": sum(1 for x in ccs if x > 20),
            "cc_over_50": sum(1 for x in ccs if x > 50),
        }

    worst = sorted(funcs, key=lambda f: -f[3])[:15]
    longest = sorted(funcs, key=lambda f: -f[2])[:15]
    report = {
        "functions_all": fn_stats(funcs),
        "functions_used": fn_stats(f for f in funcs if f[4]),
        "functions_unused": fn_stats(f for f in funcs if not f[4]),
        "worst_complexity": [f"{m}.{n} cc={cc} lines={l} used={u}" for m, n, l, cc, u in worst],
        "longest": [f"{m}.{n} lines={l} cc={cc} used={u}" for m, n, l, cc, u in longest],
        "exact_duplicates": dup_stats(exact),
        "structural_duplicates": dup_stats(struct),
        "hygiene_all": dict(hygiene),
        "hygiene_in_used_modules": dict(hygiene_used),
    }
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
