import ast, sys, json
from pathlib import Path
from collections import deque
root=Path(sys.argv[1]); src=root/'src'; PKG='polymarket_alpha_lab'
files=sorted(src.rglob('*.py'))
def mn(p):
    parts=list(p.relative_to(src).with_suffix('').parts)
    if parts[-1]=='__init__': parts=parts[:-1]
    return '.'.join(parts)
mods={mn(f):f for f in files}; known=set(mods)
def top_level_imports(path, mod, is_pkg):
    """Only imports executed at import time: module-level statements (incl. inside top-level if/try), not inside functions/classes bodies of functions."""
    tree=ast.parse(path.read_text(encoding='utf-8'))
    out=set()
    def visit(nodes):
        for n in nodes:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)): continue
            if isinstance(n,ast.ClassDef): visit(n.body); continue
            if isinstance(n,ast.Import):
                for a in n.names:
                    parts=a.name.split('.')
                    for i in range(1,len(parts)+1):
                        c='.'.join(parts[:i])
                        if c in known: out.add(c)
            elif isinstance(n,ast.ImportFrom):
                if n.level:
                    base=mod.split('.')
                    if not is_pkg: base=base[:-1]
                    if n.level>1: base=base[:len(base)-(n.level-1)]
                    b='.'.join(base)
                    if n.module: b=f'{b}.{n.module}' if b else n.module
                else: b=n.module or ''
                parts=b.split('.')
                for i in range(1,len(parts)+1):
                    c='.'.join(parts[:i])
                    if c in known: out.add(c)
                for a in n.names:
                    c=f'{b}.{a.name}'
                    if c in known: out.add(c)
            else:
                for fld in ('body','orelse','finalbody','handlers'):
                    v=getattr(n,fld,None)
                    if isinstance(v,list): visit(v)
        return out
    visit(tree.body)
    # if TYPE_CHECKING blocks are included (over-approximation) - acceptable
    return out
g={m:top_level_imports(f,m,f.name=='__init__.py') for m,f in mods.items()}
lines={m:sum(1 for _ in f.open(encoding='utf-8')) for m,f in mods.items()}
def reach(starts):
    seen=set(); q=deque(starts)
    while q:
        m=q.popleft()
        if m in seen or m not in g: continue
        seen.add(m)
        parts=m.split('.')
        nxt=set(g[m])|{'.'.join(parts[:i]) for i in range(1,len(parts))}
        q.extend(nxt-seen)
    return seen
for label,start in [('import polymarket_alpha_lab (root)',[PKG]),('papersim.cli',[PKG+'.papersim.cli']),('papersim.gates',[PKG+'.papersim.gates']),('project_postgres.cli',[PKG+'.project_postgres.cli']),('cli',[PKG+'.cli']),('research_dispatch_cli',[PKG+'.research_dispatch_cli'])]:
    r=reach(start)
    print(f"{label:38s} modules_loaded_at_import={len(r):4d} lines={sum(lines[m] for m in r):7d}")
