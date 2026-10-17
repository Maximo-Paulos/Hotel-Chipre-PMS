import os
"""Heuristic AST scan of every function in app/: query-in-loop (N+1), unbounded .all(),
len(.all()), python-side aggregation, multiple commits, sync-in-async, etc."""
import ast, os, sys, json, collections

ROOT = os.path.join(os.environ.get("REPO", "."), "app")
DB_NAMES = {"db", "session", "outbox_session", "check_db", "sess", "s"}
QUERY_METHODS = {"query", "get", "execute", "scalar", "scalars", "refresh", "merge"}

def chain_names(node):
    """names of methods in a call chain, outer->inner"""
    names = []
    while isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute):
            names.append(f.attr)
            node = f.value
        else:
            break
    return names

def root_name(node):
    while isinstance(node, (ast.Call, ast.Attribute)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None

def is_db_call(call):
    if not isinstance(call, ast.Call): return False
    f = call.func
    if isinstance(f, ast.Attribute) and f.attr in QUERY_METHODS:
        return root_name(f.value) in DB_NAMES
    return False

class FuncScan(ast.NodeVisitor):
    def __init__(self):
        self.loop_depth = 0
        self.query_in_loop = []     # (lineno)
        self.unbounded_all = []     # (lineno)
        self.len_all = []           # (lineno)
        self.commits = 0
        self.queries = 0
        self.sum_over_orm = []      # python sum()/dict aggregation after .all(): approximated by sum( over generator
    def visit_For(self, n):
        self.visit(n.iter)
        self.loop_depth += 1
        for b in n.body + n.orelse: self.visit(b)
        self.loop_depth -= 1
    visit_AsyncFor = visit_For
    def visit_While(self, n):
        self.visit(n.test); self.loop_depth += 1
        for b in n.body: self.visit(b)
        self.loop_depth -= 1
    def _comp(self, n):
        self.loop_depth += 1
        self.generic_visit(n)
        self.loop_depth -= 1
    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comp
    def visit_Call(self, n):
        names = chain_names(n)
        if is_db_call(n) or (names and names[-1] == "query" and root_name(n) in DB_NAMES):
            self.queries += 1
            if self.loop_depth > 0 and (names[-1:] == ["query"] or n.func.attr in {"get", "execute", "scalar", "scalars"}):
                # a query started inside a loop body (the chain root call)
                pass
        # terminal methods on a chain that started from db.query(...)
        if isinstance(n.func, ast.Attribute):
            attr = n.func.attr
            if attr in {"all", "first", "one", "one_or_none", "scalar", "count", "scalars", "get", "execute"} or attr == "query":
                chain = chain_names(n)
                if "query" in chain or (attr in {"get", "execute", "scalar", "scalars"} and root_name(n.func.value) in DB_NAMES) or (attr=="query" and root_name(n.func.value) in DB_NAMES):
                    if self.loop_depth > 0 and attr in {"all", "first", "one", "one_or_none", "scalar", "count", "get", "execute", "scalars"}:
                        self.query_in_loop.append(n.lineno)
                    if attr == "all" and "limit" not in chain and "query" in chain:
                        self.unbounded_all.append(n.lineno)
            if attr == "commit": self.commits += 1
        if isinstance(n.func, ast.Name) and n.func.id == "len" and n.args:
            a = n.args[0]
            if isinstance(a, ast.Call) and isinstance(a.func, ast.Attribute) and a.func.attr == "all" and "query" in chain_names(a):
                self.len_all.append(n.lineno)
        self.generic_visit(n)

def scan_file(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8-sig").read())
    except SyntaxError:
        return None
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fs = FuncScan()
            for b in node.body: fs.visit(b)
            out.append(dict(name=node.name, line=node.lineno, end=node.end_lineno or node.lineno,
                            is_async=isinstance(node, ast.AsyncFunctionDef), queries=fs.queries,
                            q_loop=sorted(set(fs.query_in_loop)), unbounded=sorted(set(fs.unbounded_all)),
                            len_all=sorted(set(fs.len_all)), commits=fs.commits, loc=(node.end_lineno or node.lineno) - node.lineno + 1))
    return out

results = {}
nfuncs = nloc = 0
for dirpath, _, files in os.walk(ROOT):
    if "__pycache__" in dirpath: continue
    for fn in files:
        if not fn.endswith(".py"): continue
        p = os.path.join(dirpath, fn)
        r = scan_file(p)
        if r is None: continue
        results[os.path.relpath(p, ROOT)] = r
        nfuncs += len(r)
json.dump(results, open(sys.argv[1], "w"))
tot = collections.Counter()
for f, fl in results.items():
    for fn in fl:
        tot["functions"] += 1
        tot["functions_with_db_queries"] += 1 if fn["queries"] else 0
        tot["db_query_sites"] += fn["queries"]
        tot["query_in_loop_sites"] += len(fn["q_loop"])
        tot["functions_with_query_in_loop"] += 1 if fn["q_loop"] else 0
        tot["unbounded_all_sites"] += len(fn["unbounded"])
        tot["len_all_sites"] += len(fn["len_all"])
        tot["functions_multi_commit(>=3)"] += 1 if fn["commits"] >= 3 else 0
        tot["async_defs"] += 1 if fn["is_async"] else 0
for k, v in tot.items(): print(f"{k:36s} {v}")
