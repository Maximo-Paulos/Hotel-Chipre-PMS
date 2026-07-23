---
scope: API FastAPI, servicios de dominio e integraciones
owner: backend-engineer
last_verified_commit: 71cb80e
canonical_sources: [app/main.py, app/api/, app/services/, knowledge/_generated/api-surface.md]
graphify_minimum: graphify minimal-context --files app/main.py --task backend
required_validation: pytest focal + OpenAPI + graphify check-update
---
# Context pack — Backend

FastAPI registra routers en `app/main.py`; los routers deben mantener transporte/validación delgados y delegar reglas a `app/services/`. El contrato actual se genera en `_generated/api-surface.md` y `openapi.json`.

Preservar contexto de hotel, autorización, transiciones de reserva/pago e idempotencia. Integraciones de pagos, email, WhatsApp y OTA son límites externos: validar por contrato y no ejecutar efectos reales en QA cloud.
