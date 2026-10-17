import ast, sys, pathlib
AUD={"safe_create_audit_log","create_audit_log","queue_audit_log","record_hotel_audit_event"}
root=pathlib.Path("/home/user/Hotel-Chipre-PMS/app")
res=[]
for p in sorted(root.rglob("*.py")):
    try: tree=ast.parse(p.read_text(encoding="utf-8"))
    except Exception: continue
    for fn in ast.walk(tree):
        if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        commits=[];audits=[]
        for n in ast.walk(fn):
            if isinstance(n,ast.Call):
                f=n.func
                name=f.attr if isinstance(f,ast.Attribute) else (f.id if isinstance(f,ast.Name) else None)
                if name=="commit": commits.append(n.lineno)
                if name in AUD: audits.append((n.lineno,name))
        for ln,name in audits:
            before=[c for c in commits if c<ln]; after=[c for c in commits if c>ln]
            if before and not after:
                res.append((str(p.relative_to(root.parent)),fn.name,ln,name))
for r in res: print("%s:%d  %s -> %s"%(r[0],r[2],r[1],r[3]))
print(len(res),"sites")
