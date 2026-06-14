"""Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.

Rationale: the only reachable PG here is a REMOTE Supabase pooler, so client
wall-clock is dominated by network RTT and is NOT representative of production.
EXPLAIN (ANALYZE, BUFFERS) reports SERVER-SIDE execution time + the chosen plan
(Index vs Seq Scan), which is network-independent and the authoritative metric.

Bulk-seeds a modest dataset for hotel 90002, runs EXPLAIN on the hot queries,
prints server-side ms + scan type, then cleans up.
"""
import os
import re
import sys
from dotenv import load_dotenv
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
dsn = re.sub(r"/postgres(\?.*)?$", "/hotel_chipre_test", os.environ["DATABASE_URL"])
HID = 90002
e = create_engine(dsn, pool_pre_ping=True)

def explain(c, label, sql, params):
    plan = c.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql), params).scalar()
    node = plan[0]["Plan"]
    exec_ms = plan[0]["Execution Time"]
    txt = str(plan)
    scan = "Seq Scan" if "Seq Scan" in txt else ("Index" if "Index" in txt else node.get("Node Type"))
    print(f"{label:42s} | exec={exec_ms:8.2f} ms | {'SEQ-SCAN' if 'Seq Scan' in txt else 'INDEX/other: '+scan}")

from app.models.hotel_config import HotelConfiguration
from sqlalchemy.orm import Session
with Session(e) as s:
    s.query(__import__("app.models.guest", fromlist=["Guest"]).Guest).filter_by(hotel_id=HID).delete()
    s.query(HotelConfiguration).filter_by(id=HID).delete()
    s.add(HotelConfiguration(id=HID, hotel_name="Perf", subscription_active=True))
    s.commit()
with e.begin() as c:
    # bulk seed 3000 guests in one round-trip
    rows = [{"h": HID, "fn": f"Guest{i}", "ln": f"Last{i%500}", "dn": f"DOC{i:07d}",
             "em": f"g{i}@perf.test", "ph": f"+5411{i:08d}", "tc": True} for i in range(3000)]
    c.execute(text("INSERT INTO guests (hotel_id, first_name, last_name, document_number, email, phone, terms_accepted, created_at, updated_at) "
                   "VALUES (:h,:fn,:ln,:dn,:em,:ph,:tc, NOW(), NOW())"), rows)
    c.execute(text("ANALYZE guests"))

print(f"seeded 3000 guests for hotel {HID}; EXPLAIN ANALYZE (server-side):")
with e.connect() as c:
    explain(c, "guest search by document (trgm/eq)",
            "SELECT * FROM guests WHERE hotel_id=:h AND document_number = :d", {"h": HID, "d": "DOC0001234"})
    explain(c, "guest search by last_name LIKE (trgm)",
            "SELECT * FROM guests WHERE hotel_id=:h AND last_name ILIKE :q", {"h": HID, "q": "%Last42%"})
    explain(c, "guest search by email LIKE (trgm)",
            "SELECT * FROM guests WHERE hotel_id=:h AND email ILIKE :q", {"h": HID, "q": "%g1234%"})
    explain(c, "guest list by hotel_id (index)",
            "SELECT * FROM guests WHERE hotel_id=:h ORDER BY last_name LIMIT 50", {"h": HID})

with e.begin() as c:
    c.execute(text("DELETE FROM guests WHERE hotel_id=:h"), {"h": HID})
    c.execute(text("DELETE FROM hotel_configuration WHERE id=:h"), {"h": HID})
print("cleaned up.")
e.dispose()
