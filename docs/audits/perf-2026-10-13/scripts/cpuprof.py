import os, sys, cProfile, pstats, io, re
sys.path.insert(0, os.environ.get("REPO", "."))
os.environ["DATABASE_URL"] = "postgresql+psycopg2://pms_app:pms_app@127.0.0.1:5440/hotel_profile"
os.environ["APP_ENV"] = "production"
from fastapi.testclient import TestClient
import app.main as M
from app.config import get_settings
get_settings.cache_clear()
with TestClient(M.app) as c:
    tok = c.post("/api/auth/login", json={"email":"owner@perf.test","password":"PerfPass1234!"}).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}", "X-Hotel-Id": "1"}
    target = sys.argv[1]
    for _ in range(5): c.get(target, headers=H)
    pr = cProfile.Profile(); pr.enable()
    N = int(sys.argv[2])
    for _ in range(N): r = c.get(target, headers=H)
    pr.disable()
    print("status", r.status_code, "bytes", len(r.content))
    s = io.StringIO(); ps = pstats.Stats(pr, stream=s).sort_stats("tottime"); ps.print_stats(22)
    out = s.getvalue().splitlines()
    total = [l for l in out if "function calls" in l]
    print(total[0] if total else "")
    for l in out[out.index(next(x for x in out if "tottime" in x)) :][:24]: print(l[:170])
