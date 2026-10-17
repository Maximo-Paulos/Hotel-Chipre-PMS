import os
"""Call every parameterless GET once warm; record SQL query count, time and bytes."""
import json, re, sys, time
import httpx

BASE = sys.argv[1]
OUT = sys.argv[2]
SP = os.environ.get("AUDIT_DIR", ".")  # dir containing openapi.json
spec = json.load(open(f"{SP}/openapi.json"))

c = httpx.Client(base_url=BASE, timeout=20)
r = c.post("/api/auth/login", json={"email": "owner@perf.test", "password": "PerfPass1234!"})
r.raise_for_status()
tok = r.json()["access_token"]
H = {"Authorization": f"Bearer {tok}", "X-Hotel-Id": "1", "Accept-Encoding": "gzip"}

today = time.strftime("%Y-%m-%d")
# sensible defaults for endpoints that insist on query params
DEFAULTS = {
    "date_from": "2026-01-01", "date_to": today, "start_date": "2026-10-01", "end_date": "2026-10-31",
    "from_date": "2026-01-01", "to_date": today, "check_in_date": "2026-11-01", "check_out_date": "2026-11-03",
    "date": today, "month": today[:7], "from": "2026-01-01", "to": today,
}

def parse_timing(hdrs):
    st = hdrs.get_list("server-timing")
    out = {"app": 0.0, "db": 0.0, "q": 0, "co": 0}
    for s in st:
        if s.startswith("app;"):
            out["app"] = float(re.search(r"dur=([\d.]+)", s).group(1))
        elif s.startswith("db;"):
            out["db"] = float(re.search(r"db;dur=([\d.]+)", s).group(1))
            m = re.search(r'"(\d+) queries"', s)
            if m: out["q"] = int(m.group(1))
        elif s.startswith("dbpool;"):
            m = re.search(r'"(\d+) checkouts"', s)
            if m: out["co"] = int(m.group(1))
    return out

rows = []
for path, item in spec["paths"].items():
    if "get" not in item or "{" in path or path in ("/api/events/stream",):
        continue
    params = {}
    for p in item["get"].get("parameters", []):
        if p.get("in") == "query" and p.get("required"):
            params[p["name"]] = DEFAULTS.get(p["name"], "1")
    best = None
    for attempt in range(2):  # first call warms caches/JIT of SQLAlchemy compiled cache
        t0 = time.perf_counter()
        try:
            resp = c.get(path, headers=H, params=params)
        except Exception as exc:
            best = {"path": path, "status": f"EXC {type(exc).__name__}"}
            break
        wall = (time.perf_counter() - t0) * 1000
        tm = parse_timing(resp.headers)
        best = {
            "path": path, "status": resp.status_code, "wall": round(wall, 1), "app": tm["app"], "db": tm["db"],
            "q": tm["q"], "co": tm["co"], "wire": len(resp.content),
            "raw": len(resp.content) if resp.headers.get("content-encoding") != "gzip" else None,
        }
        # decoded size
        best["decoded"] = len(resp.text.encode()) if resp.status_code == 200 else 0
    rows.append(best)
    print(path, best.get("status"), best.get("q"), best.get("app"), flush=True)
json.dump(rows, open(OUT, "w"))
ok = [r for r in rows if r.get("status") == 200]
print(f"GET endpoints swept: {len(rows)}  200s: {len(ok)}  non-200: {len(rows)-len(ok)}")
