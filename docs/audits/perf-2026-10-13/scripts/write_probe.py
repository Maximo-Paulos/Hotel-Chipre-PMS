import httpx, re, sys, json, subprocess
BASE=sys.argv[1]
c=httpx.Client(base_url=BASE, timeout=30)
tok=c.post("/api/auth/login",json={"email":"owner@perf.test","password":"PerfPass1234!"}).json()["access_token"]
H={"Authorization":f"Bearer {tok}","X-Hotel-Id":"1"}
def timing(r):
    out={}
    for s in r.headers.get_list("server-timing"):
        if s.startswith("app;"): out["app_ms"]=float(re.search(r"dur=([\d.]+)",s).group(1))
        m=re.search(r'"(\d+) queries"',s)
        if m: out["queries"]=int(m.group(1))
    return out
def outbox_count():
    return int(subprocess.check_output(["psql","-h","127.0.0.1","-p","5440","-U","pms","-d","hotel_profile","-At","-c","select count(*) from domain_event_outbox"]).decode())
cats=c.get("/api/rooms/categories",headers=H).json(); cat=cats[0]["id"]
guests=c.get("/api/guests/search",headers=H,params={"q":"Perez"}).json()
print("guests search type:",type(guests).__name__, (list(guests.keys()) if isinstance(guests,dict) else len(guests)))

import datetime as dt
today=dt.date.today()
ci=today+dt.timedelta(days=200); co=ci+dt.timedelta(days=2)
guest_id=guests[0]["id"]
def step(name, r):
    t=timing(r)
    print(f"{name:34s} http={r.status_code} queries={t.get('queries')} app_ms={t.get('app_ms')} outbox_total={outbox_count()}")
    return r
print("outbox before:", outbox_count())
q=step("GET  /api/bookings/price-quote", c.get("/api/bookings/price-quote",headers=H,params={"category_id":cat,"check_in_date":str(ci),"check_out_date":str(co),"guest_id":guest_id,"occupancy":2}))
qj=q.json(); token=qj.get("quote_token") or qj.get("token")
print("quote keys:",list(qj.keys())[:12])
r=step("POST /api/reservations/ (create)", c.post("/api/reservations/",headers=H,json={"guest_id":guest_id,"category_id":cat,"check_in_date":str(ci),"check_out_date":str(co),"num_adults":2,"quote_token":token}))
if r.status_code>=300: print(r.text[:400]); sys.exit()
rid=r.json()["id"]; total=r.json().get("total_amount")
print("reservation id",rid,"total",total)
r=step("GET  /api/reservations/{id}", c.get(f"/api/reservations/{rid}",headers=H))
import uuid
r=step("POST /api/payments/ (deposit)", c.post("/api/payments/",headers={**H,"Idempotency-Key":str(uuid.uuid4())},json={"reservation_id":rid,"amount":1000,"payment_method":"bank_transfer","transaction_type":"deposit","currency":"ARS"}))
if r.status_code>=300: print(r.text[:300])

# move reservation dates to today so check-in is legal, then check-in/out
r=step("POST /api/payments/ (balance)", c.post("/api/payments/",headers={**H,"Idempotency-Key":str(uuid.uuid4())},json={"reservation_id":rid,"amount":float(total)-1000,"payment_method":"bank_transfer","transaction_type":"balance_payment","currency":"ARS"}))
if r.status_code>=300: print(r.text[:300])
