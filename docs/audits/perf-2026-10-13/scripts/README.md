# Cómo reproducir las mediciones

Todo se ejecutó sobre bases **descartables**; nada toca el repo ni producción. Requisitos: PostgreSQL 16 local (con `pg_stat_statements` si quiere el ranking de sentencias), Python 3.12 con `requirements.txt`, Node 22 para el build del frontend.

```bash
export REPO=$PWD AUDIT_DIR=/ruta/a/un/directorio/de/trabajo
# 1) base + migraciones (cronometra el costo de deploy: 173 migraciones ≈ 7,6 s)
createdb hotel_profile
DATABASE_URL=postgresql+psycopg2://USER:PASS@127.0.0.1:5432/hotel_profile python -m alembic upgrade head
# 2) datos sintéticos (hotel 1): rooms guests reservations
DATABASE_URL=... python docs/audits/perf-2026-10-13/scripts/seed_profile.py 30 1800 6500   # un hotel
# 30 hoteles (escala): ... seed_scale.py 30 1800 6500 1 30
# 3) levantar el API con el entorno de producción de render.yaml (pool 4+2, realtime por Postgres, sin Redis)
#    y un rol de DB NOBYPASSRLS para que la RLS aplique (ver §1 del informe)
# 4) OpenAPI -> barrido de todos los GET sin parámetros de ruta (consultas, tiempo, bytes por endpoint)
curl -s http://127.0.0.1:8042/openapi.json > $AUDIT_DIR/openapi.json
python scripts/sweep_gets.py http://127.0.0.1:8042 $AUDIT_DIR/sweep.json
# 5) carga concurrente (mezcla light|heavy; usuarios; segundos; think-time)
python scripts/loadtest.py http://127.0.0.1:8042 heavy 5,10,20 20 0.5
# 6) egreso DB->API: poner scripts/tcpcount.py (proxy contador) entre el API y Postgres
python scripts/tcpcount.py 5441 5432 $AUDIT_DIR/proxy_counts.txt
# 7) análisis estático
python scripts/schema_audit.py     # tablas/columnas/tipos/FKs del ORM
python scripts/ast_scan.py $AUDIT_DIR/ast_scan.json   # N+1, .all() sin límite, commits por función
```

- `seed_profile.py` y `write_probe.py` rechazan cualquier `DATABASE_URL` que no sea el Postgres local de pruebas (`127.0.0.1:5440`): ajuste el puerto o la guarda a su entorno.
- `prototypes/` contiene los dos experimentos (carga perezosa global y caché de autenticación + un solo `set_config`). Son **medidas de potencial sobre copias descartables, no código para mergear**: el caché omite a propósito la revocación inmediata de permisos.
- Escala multi-hotel: `seed_scale.py N_ROOMS N_GUESTS N_RES HOTEL_DESDE HOTEL_HASTA`.
- Verificaciones de la lectura completa (base migrada con `APP_ENV=development alembic upgrade head`, ver `LECTURA-COMPLETA.md`, última sección): `measure_hot_paths.py` (sentencias/commits de limitador, clave de API pública, `billing_policy`, Argon2 vs HMAC, costo de *listeners*), `verify_public_booking_pii.py` (exposición de documento del huésped vía API pública), `verify_misc_findings.py` (`/health/datastores` público, `connections.py` no montado, credenciales de onboarding en claro), `audit_loss_repro.py` y `scan_post_commit_audit.py` (auditoría posterior al `commit`).
