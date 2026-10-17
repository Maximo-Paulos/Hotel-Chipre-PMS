"""Mide, sobre PostgreSQL real, el costo de cuatro rutas calientes que la lectura
completa señaló como sospechosas. Solo lectura del código: no modifica la app.

Uso (base migrada con ``alembic upgrade head`` y ``APP_ENV=development``):

    export DATABASE_URL=postgresql+psycopg2://USER:PASS@127.0.0.1:5440/hotel_measure
    APP_ENV=development python docs/audits/perf-2026-10-13/scripts/measure_hot_paths.py

Cuenta sentencias con el mismo contador que usa ``request_telemetry`` en producción
(``app.database.start_request_db_metrics``), de modo que las cifras son comparables
con ``db_query_count`` de los logs de Render.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import statistics
import time

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import sessionmaker

import app.database as appdb
import app.models  # noqa: F401  (registra todos los mapeos)
from app.database import (
    Base,
    finish_request_db_metrics,
    get_engine,
    start_request_db_metrics,
)

URL = os.environ["DATABASE_URL"]
engine = get_engine(URL)
appdb._engine = engine
appdb._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Session = appdb._SessionLocal

COMMITS = {"n": 0}


@event.listens_for(engine, "commit")
def _count_commit(conn):
    COMMITS["n"] += 1


def measured(label, fn, repeat=1):
    """Ejecuta ``fn`` ``repeat`` veces en una sesión nueva y devuelve sentencias/commits/ms."""
    rows = []
    for _ in range(repeat):
        COMMITS["n"] = 0
        token = start_request_db_metrics()
        started = time.perf_counter()
        db = Session()
        try:
            fn(db)
        finally:
            db.close()
        elapsed = (time.perf_counter() - started) * 1000
        m = finish_request_db_metrics(token)
        rows.append((int(m["query_count"]), COMMITS["n"], elapsed))
    q = statistics.median(r[0] for r in rows)
    c = statistics.median(r[1] for r in rows)
    ms = statistics.median(r[2] for r in rows)
    print(f"{label:<58} sentencias={q:>5.0f}  commits={c:>3.0f}  {ms:8.1f} ms")
    return {"label": label, "statements": q, "commits": c, "ms": round(ms, 1)}


def setup():
    from app.models.hotel_config import HotelConfiguration
    from app.services.hotel_api_key_service import issue_key
    from app.models.hotel_api_key import APIKeyPurposeEnum

    db = Session()
    try:
        if db.get(HotelConfiguration, 1) is None:
            db.add(HotelConfiguration(id=1, hotel_name="Medición", hotel_timezone="America/Argentina/Buenos_Aires", default_currency="ARS"))
            db.commit()
        _key, secret = issue_key(
            db, hotel_id=1, name="medicion", purpose=APIKeyPurposeEnum.WEB_ENGINE,
            created_by_user_id=None, expires_at=None,
        )
        db.commit()
        return secret
    finally:
        db.close()


results = []
secret = setup()

# 1) Limitador persistido en BD: 1 intento y 20 intentos de la misma clave
from app.adapters.rate_limiter import SimpleRateLimiter

limiter = SimpleRateLimiter("medicion", limit=100, window_seconds=60)
results.append(measured("limitador BD: 1 intento (allow + commit)", lambda db: (limiter.allow("k1", db=db), db.commit())))
results.append(measured("limitador BD: 20 intentos en una transacción", lambda db: ([limiter.allow("k2", db=db) for _ in range(20)], db.commit())))
mem = SimpleRateLimiter("medicion_mem", limit=100, window_seconds=60)
results.append(measured("limitador en memoria: 20 intentos", lambda db: [mem.allow("k3") for _ in range(20)]))

# 2) API pública: dependencia completa por llamada (verify_key + límite + last_used_at + commit)
from app.dependencies.api_key_auth import require_web_engine_api_context

results.append(measured("API pública: autenticación de 1 llamada", lambda db: require_web_engine_api_context(db=db, x_api_key=secret), repeat=5))

# 3) Política de facturación del panel master: reflexión de tabla por llamada
from app.master_admin.billing_policy import get_policy_payload

results.append(measured("billing_policy.get_policy_payload (1 hotel)", lambda db: get_policy_payload(db), repeat=5))
results.append(measured("billing_policy.get_policy_payload x50 hoteles", lambda db: [get_policy_payload(db) for _ in range(50)]))

# 4) Códigos de un solo uso: Argon2id vs HMAC
from app.services.security import hash_password, verify_password

def _argon(db):
    h = hash_password("483920")
    verify_password("483920", h)

results.append(measured("código 6 dígitos: hash+verify con Argon2id (hash_password)", _argon, repeat=5))
pepper = b"pepper-del-servidor"
def _hmac(db):
    d = hmac.new(pepper, b"483920", hashlib.sha256).hexdigest()
    hmac.compare_digest(d, d)
results.append(measured("código 6 dígitos: HMAC-SHA256 + compare_digest", _hmac, repeat=5))

# 5) Listeners por sentencia: costo de calcular bytes de parámetros (telemetría)
from app.database import _estimate_parameter_bytes

stmt = "SELECT " + ", ".join(f"reservations.col_{i} AS reservations_col_{i}" for i in range(75)) + " FROM reservations WHERE hotel_id = %(h)s"
params = {"h": 1, **{f"p{i}": i for i in range(30)}}
N = 20000
t = time.perf_counter()
for _ in range(N):
    len(stmt.encode("utf-8")) + _estimate_parameter_bytes(params)
per = (time.perf_counter() - t) / N * 1e6
print(f"{'telemetría: bytes de sentencia de 75 columnas + 31 parámetros':<58} {per:8.1f} µs/sentencia")
results.append({"label": "telemetría bytes por sentencia (µs)", "us": round(per, 1)})

# 6) audited_change: búsqueda de modelo por tabla recorriendo todos los mappers
from app.decorators.audit_hooks import _get_model_for_table

t = time.perf_counter()
for _ in range(2000):
    _get_model_for_table("guests")
per = (time.perf_counter() - t) / 2000 * 1e6
mappers = len(list(Base.registry.mappers))
print(f"{'audited_change: _get_model_for_table ({} mappers)'.format(mappers):<58} {per:8.1f} µs/llamada")
results.append({"label": f"_get_model_for_table ({mappers} mappers) µs", "us": round(per, 1)})

print(json.dumps(results, indent=2, ensure_ascii=False))
