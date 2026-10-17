"""Closed-loop load test: N virtual users, each loops over a request mix with think time."""
import asyncio, random, statistics, sys, time
import httpx

BASE = sys.argv[1]
MIX = sys.argv[2]            # light | heavy
VUS = [int(x) for x in sys.argv[3].split(",")]
DUR = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
THINK = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5

LIGHT = ["/api/reservations/?limit=50", "/api/rooms/", "/api/config/", "/api/reservations/actions/pending",
         "/api/guests/search?q=Perez", "/api/rooms/availability", "/api/subscription/status", "/api/reports/operational/daily"]
HEAVY = LIGHT + ["/api/rooms/housekeeping-board", "/api/reports/revenue", "/api/reports/daily"]
PATHS = LIGHT if MIX == "light" else HEAVY

async def login(client):
    r = await client.post("/api/auth/login", json={"email": "owner@perf.test", "password": "PerfPass1234!"})
    r.raise_for_status()
    return r.json()["access_token"]

async def vu(i, client, H, stop, lat, errs):
    rnd = random.Random(i)
    while time.monotonic() < stop:
        p = rnd.choice(PATHS)
        t0 = time.perf_counter()
        try:
            r = await client.get(p, headers=H)
            dt = (time.perf_counter() - t0) * 1000
            lat.append(dt)
            if r.status_code >= 400:
                errs[r.status_code] = errs.get(r.status_code, 0) + 1
        except Exception as e:
            errs[type(e).__name__] = errs.get(type(e).__name__, 0) + 1
        await asyncio.sleep(THINK * rnd.uniform(0.5, 1.5))

async def run(n):
    limits = httpx.Limits(max_connections=n + 5)
    async with httpx.AsyncClient(base_url=BASE, timeout=60, limits=limits) as client:
        tok = await login(client)
        H = {"Authorization": f"Bearer {tok}", "X-Hotel-Id": "1"}
        lat, errs = [], {}
        stop = time.monotonic() + DUR
        t0 = time.monotonic()
        await asyncio.gather(*[vu(i, client, H, stop, lat, errs) for i in range(n)])
        el = time.monotonic() - t0
    lat.sort()
    pct = lambda q: lat[min(len(lat) - 1, int(len(lat) * q))] if lat else 0
    print(f"{MIX:5s} VUs={n:3d} req={len(lat):5d} rps={len(lat)/el:6.1f}  p50={pct(.5):7.0f}ms p95={pct(.95):7.0f}ms p99={pct(.99):7.0f}ms max={lat[-1] if lat else 0:7.0f}ms  errors={errs or 0}", flush=True)

for n in VUS:
    asyncio.run(run(n))
