# TECH-0140 release gate

Estado local: código, migraciones y contratos implementados; el gate de
lanzamiento sigue `BLOCKED` hasta disponer de evidencia provider-bound firmada.

## Gate reproducible local

```bash
python -m alembic heads
python -m alembic upgrade head       # sólo DB descartable
python scripts/agent_ops/validate_gcp_readiness.py
python scripts/backup/verify_local_backup_restore.py \
  --database-url "$TECH0140_TEST_DATABASE_URL" \
  --table hotel_configuration --table hotel_memberships --table rooms \
  --table reservations --table transactions --table payments \
  --table audit_logs --table domain_event_outbox --table stored_objects
python -m pytest -q
```

El runner `scripts/scale/staged_realtime_load.py` sólo ejecuta recovery y SSE
autenticados contra un host de preview no productivo. Requiere un token sintético
de staging en `LOADTEST_BEARER_TOKEN`, rechaza los hosts compartidos y no realiza
escrituras de reservas/pagos.

## Bundle de evidencia

El bundle certificado debe contener exactamente `summary.json`,
`validated-preview-manifest.json` y `attestation.json` bajo
`qa/evidence/TECH-0140/`, con SHA completo, manifest provider-bound, ejecución
humana y firma Ed25519. No se genera un bundle ficticio en este repositorio:
sin staging aislado, restore firmado, carga autorizada y revisión de seguridad,
el release gate debe permanecer bloqueado.

## Stop thresholds

Detener una campaña autorizada si errores >1%, realtime p95 >3 s, API p95 >1 s,
pool wait p95 >100 ms, conexiones >80% del presupuesto, Redis >75% de memoria o
outbox age >30 s. Nunca usar producción para carga.
