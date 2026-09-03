# Portabilidad futura a Google Cloud — TECH-0140/T12

Estado: `ready-for-provider-validation`; este documento no provisiona recursos,
no activa billing y no cambia DNS, OAuth, secretos ni conexiones productivas.

## Forma objetivo

- Cloud Run ejecuta una imagen inmutable y sin usuario root, con shutdown
  gracioso para cerrar pools y SSE.
- Cloud SQL PostgreSQL conserva la autoridad transaccional y se migra primero a
  una instancia staging restaurada, nunca con dual-write financiero.
- GCS privado recibe objetos `ready`; las URLs firmadas duran como máximo cinco
  minutos y Secret Manager/IAM administra las credenciales.
- Memorystore/Valkey queda detrás de `CacheStore`, `EventBus` y `LockManager`.
- El job único de Alembic termina antes de enviar tráfico. Cloud Run comienza
  con `min-instances=0`; el máximo se calcula a partir de conexiones reales.

## Validación local

```bash
python scripts/agent_ops/validate_gcp_readiness.py
```

El validador sólo lee archivos y devuelve un JSON. No ejecuta `gcloud`, `apply`,
Terraform, billing ni llamadas de proveedor.

## Cutover futuro, sólo con aprobación

1. Capturar manifest firmado del proveedor, SHA, región, plan y presupuesto.
2. Probar imagen contra el PostgreSQL actual y luego Cloud SQL staging/restore.
3. Verificar migraciones, RLS, conteos, checksums de `StoredObject`, workers,
   readiness, logs y rollback.
4. Cambiar tráfico de forma gradual durante una coexistencia de 24–72 horas;
   no realizar dual-write de reservas, pagos o caja.
5. Mantener la imagen/SHA anterior y volver al proveedor actual ante cualquier
   violación de SLO, lag, error de tenant o discrepancia financiera.
