"""Introspect the real SQLAlchemy metadata: tables, columns, types, indexes, FKs."""
import os, sys, json, collections
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("APP_ENV", "test")
sys.path.insert(0, os.environ.get("REPO", "."))
from sqlalchemy import Float, Numeric, JSON, Enum, Text, String, Boolean, DateTime, Integer, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base
import app.models  # noqa
import app.master_admin.models  # noqa

tables = Base.metadata.sorted_tables
out = {"tables": {}}
tot_cols = tot_idx = tot_fk = 0
float_cols, json_cols, enum_cols, text_cols, str_nolen = [], [], [], [], []
fk_cols_noidx = []
for t in tables:
    cols = list(t.columns)
    idx = list(t.indexes)
    uniq = [c for c in t.constraints if c.__class__.__name__ == "UniqueConstraint"]
    fks = list(t.foreign_key_constraints)
    pk_cols = [c.name for c in t.primary_key.columns]
    # leading columns that are covered by an index / unique / pk
    covered_leading = set()
    for i in idx:
        cs = [c.name for c in i.columns]
        if cs: covered_leading.add(cs[0])
    for u in uniq:
        cs = [c.name for c in u.columns]
        if cs: covered_leading.add(cs[0])
    if pk_cols: covered_leading.add(pk_cols[0])
    for c in cols:
        if c.unique or c.index:
            covered_leading.add(c.name)
    for fk in fks:
        fcols = [c.name for c in fk.columns]
        if fcols[0] not in covered_leading:
            fk_cols_noidx.append((t.name, tuple(fcols), fk.referred_table.name))
    for c in cols:
        ty = c.type
        if isinstance(ty, Float):
            float_cols.append(f"{t.name}.{c.name}")
        if isinstance(ty, (JSON, JSONB)):
            json_cols.append(f"{t.name}.{c.name}")
        if isinstance(ty, Enum):
            enum_cols.append(f"{t.name}.{c.name}")
        if isinstance(ty, Text):
            text_cols.append(f"{t.name}.{c.name}")
    out["tables"][t.name] = dict(
        cols=len(cols), idx=len(idx), uniq=len(uniq), fks=len(fks),
        has_hotel_id=("hotel_id" in t.columns),
    )
    tot_cols += len(cols); tot_idx += len(idx); tot_fk += len(fks)

print(f"TABLES={len(tables)} COLUMNS={tot_cols} INDEXES={tot_idx} FKs={tot_fk}")
no_hotel = [n for n, v in out["tables"].items() if not v["has_hotel_id"]]
print(f"\nTables WITHOUT hotel_id ({len(no_hotel)}): {no_hotel}")
print(f"\nFloat columns ({len(float_cols)}): {float_cols}")
print(f"\nJSON/JSONB columns ({len(json_cols)}): {json_cols}")
print(f"\nEnum columns ({len(enum_cols)}): {len(enum_cols)}")
print(f"\nText columns: {len(text_cols)}")
print(f"\nFKs whose leading column has NO index ({len(fk_cols_noidx)}):")
for tn, cols, ref in fk_cols_noidx:
    print(f"   {tn}{cols} -> {ref}")
print("\nBiggest tables by columns:")
for n, v in sorted(out["tables"].items(), key=lambda kv: -kv[1]["cols"])[:20]:
    print(f"   {n:42s} cols={v['cols']:3d} idx={v['idx']:2d} uniq={v['uniq']:2d} fks={v['fks']:2d}")
print("\nTables with 0 secondary indexes AND 0 uniques (excluding tiny):")
for n, v in out["tables"].items():
    if v["idx"] == 0 and v["uniq"] == 0 and v["cols"] > 4:
        print(f"   {n} cols={v['cols']} fks={v['fks']}")
