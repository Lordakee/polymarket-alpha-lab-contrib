"""Classify test files by whether they exercise entry-reachable modules.
Resolves `from polymarket_alpha_lab import NAME` through the root __init__ re-export map."""
import ast, json, sys
from pathlib import Path
root=Path(sys.argv[1]); static=json.load(open(sys.argv[2]))
used=set(static['_used']); lines=static['_lines']; known=set(lines)
PKG='polymarket_alpha_lab'
init=ast.parse((root/'src'/PKG/'__init__.py').read_text(encoding='utf-8'))
export={}
for n in init.body:
    if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith(PKG):
        for a in n.names: export[a.asname or a.name]=n.module
tot=dict(files=0,lines=0)
cls={'touches_reachable':[0,0],'only_unreachable':[0,0],'no_package_import':[0,0],'root_attr_unresolved':[0,0]}
only_unreach_mods=set()
for f in sorted((root/'tests').rglob('*.py')):
    text=f.read_text(encoding='utf-8'); n=text.count('\n')+ (0 if text.endswith('\n') or not text else 1)
    try: tree=ast.parse(text)
    except SyntaxError: continue
    deps=set(); unresolved=False; root_alias=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for a in node.names:
                if a.name in known and a.name!=PKG: deps.add(a.name)
                elif a.name==PKG: root_alias.add(a.asname or PKG)
        elif isinstance(node,ast.ImportFrom) and node.module and not node.level:
            if node.module==PKG:
                for a in node.names:
                    c=f'{PKG}.{a.name}'
                    if c in known: deps.add(c)
                    elif a.name in export: deps.add(export[a.name])
                    else: unresolved=True
            elif node.module in known:
                deps.add(node.module)
                for a in node.names:
                    c=f'{node.module}.{a.name}'
                    if c in known: deps.add(c)
        elif isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in known and node.value!=PKG:
            deps.add(node.value)
    if root_alias:
        for node in ast.walk(tree):
            if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id in root_alias:
                c=f'{PKG}.{node.attr}'
                if c in known: deps.add(c)
                elif node.attr in export: deps.add(export[node.attr])
    tot['files']+=1; tot['lines']+=n
    if deps & used: k='touches_reachable'
    elif deps: k='only_unreachable'; only_unreach_mods|=deps
    elif unresolved or root_alias: k='root_attr_unresolved'
    else: k='no_package_import'
    cls[k][0]+=1; cls[k][1]+=n
print(tot)
for k,v in cls.items(): print(k, v)
print('root exports mapped:',len(export))
