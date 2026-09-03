# Backups y continuidad — TECH-0110

Estado: `IN_PROGRESS` — el mecanismo local y el contrato de datos están
verificados; la configuración y el restore drill del proveedor cloud requieren
acción humana y siguen en `needs-verification`.

## Alcance y límites

PostgreSQL es la fuente operacional de verdad para reservas, huéspedes, pagos y
caja. Este runbook separa la evidencia reproducible en el worktree de la
verificación que sólo puede hacer una persona autorizada en Render/Supabase.

No ejecutar desde un agente: restauraciones sobre producción, cambios de plan o
retención, activación de PITR, rotación de secretos, creación de cuentas,
cutovers ni cambios de billing.

## Objetivo propuesto de continuidad

| Métrica | Objetivo propuesto | Justificación y estado |
|---|---:|---|
| RPO | 15 minutos | Adecuado para reservas/pagos si el plan Supabase contratado ofrece PITR con esa granularidad. `needs-verification`: confirmar disponibilidad, ventana y costo en la consola. |
| RTO | 60 minutos | Permite restaurar una copia en una base aislada, ejecutar migraciones y smoke tests antes de autorizar el retorno operativo. `needs-verification`: medirlo en un drill humano. |
| Retención operativa | 35 días | Cubre un mes completo más margen para detectar errores de conciliación. `needs-verification`: confirmar política legal/comercial del hotel y capacidad del plan. |
| Copia inmutable | Al menos una copia mensual fuera de la cuenta/entorno primario | Reduce el riesgo de borrado o corrupción lógica compartida. `needs-verification`: definir proveedor, cifrado, ownership y costo; no se implementa desde este repo. |

Estos valores son una propuesta operativa, no una configuración aplicada.

## Qué está verificado en el repositorio

- `render.yaml` apunta `DATABASE_URL` a una conexión configurada manualmente en
  Render y ejecuta `python -m alembic upgrade head` antes del web service.
- `render.yaml` declara un Redis/Key Value privado con
  `persistenceMode: journal-snapshot`. Eso sólo cubre la persistencia declarada
  del servicio de colas/cache; no es un backup de PostgreSQL ni sustituye PITR.
- El repo no declara una política de backup, PITR, retención o copia inmutable
  para la base PostgreSQL de Supabase. La disponibilidad de esas funciones y el
  período contratado son `needs-verification` en la consola Supabase.
- `CompanyDocument`, `Reservation`, `Room`, `PricePeriod`, `StockItem`,
  `StockLocation` y los flujos existentes de borrado de reservas/habitaciones
  conservan filas mediante soft-delete y auditoría.
- La migración `20260821_tech0110_operational_soft_delete` agrega el mismo
  envelope nullable (`deleted_at`, `deleted_by_user_id`) a `guests` y
  `payments`, con índices `(hotel_id, deleted_at)`. No habilita endpoints de
  borrado ni cambia el ledger financiero.
- `scripts/backup/verify_local_backup_restore.py` hace dump, restore a un
  destino descartable y compara las tablas operativas críticas, incluyendo
  outbox y `stored_objects`; con `--object-storage-dir` también verifica
  presencia, tamaño y SHA-256 de cada objeto `ready`. En PostgreSQL sólo acepta
  hosts locales.
- El export CSV de la timeline de auditoría de TECH-0070 es un patrón de
  exportación redacted y tenant-scoped. No se considera un backup de base.

## Drill local reproducible

Crear una base SQLite efímera con el esquema Alembic actual y ejecutar el drill
sin apuntar a Render, Supabase ni a una base compartida:

```sh
PYTHON_BIN=/ruta/a/python-3.12
DB_DIR="$(mktemp -d)"
DATABASE_URL="sqlite:///$DB_DIR/source.sqlite3" \
  "$PYTHON_BIN" -m alembic upgrade head
DATABASE_URL="sqlite:///$DB_DIR/source.sqlite3" \
  OBJECT_STORAGE_LOCAL_DIR="$DB_DIR/object-storage" \
  "$PYTHON_BIN" scripts/backup/verify_local_backup_restore.py \
  --object-storage-dir "$DB_DIR/object-storage"
```

Resultado esperado: una línea JSON con `"status": "verified"`,
`"integrity_check": "ok"`, `"foreign_key_check": "ok"`, conteos iguales y el
resumen de objetos verificados. El script elimina el dump y la base restaurada
temporales al finalizar; la base fuente efímera queda bajo `DB_DIR` para
inspección y puede borrarse manualmente al terminar el ensayo.

El drill local demuestra el mecanismo de serialización/restauración y la
integridad básica. No demuestra que el proveedor cloud haya tomado backups ni
que PITR esté activo.

Evidencia ejecutada en este worktree el 2026-08-21: una SQLite temporal creada
con `alembic upgrade head` y datos sintéticos produjo
`{"status":"verified","integrity_check":"ok","foreign_key_check":"ok","tables":{"audit_logs":1,"guests":1,"payments":0,"reservations":0}}`.
También pasó `upgrade head → downgrade -1 → upgrade head` sobre otra base
SQLite temporal.

## Restore drill humano contra el proveedor real

Realizarlo sólo con autorización del responsable de infraestructura y dentro de
una ventana aprobada. Nunca restaurar primero sobre la base productiva.

1. Registrar fecha/hora UTC, SHA desplegado, proyecto Supabase, servicio Render,
   punto de recuperación solicitado y el RPO/RTO objetivo. Confirmar que el
   destino es un proyecto/branch/base aislada sin tráfico ni datos que deban
   preservarse.
2. En Supabase Dashboard, verificar qué mecanismo está contratado: backups
   automáticos, PITR, ventana de retención, cifrado, región y permisos del
   operador. Si PITR o la retención no aparecen habilitados, detener el drill y
   registrar la brecha; no cambiar el plan sin aprobación humana.
3. Crear una restauración en una base aislada en el timestamp elegido. No
   sobrescribir producción. Obtener la cadena de conexión desde el canal seguro
   aprobado; no pegarla en Git, logs, tickets públicos ni este runbook.
4. Validar el schema y las migraciones en el destino restaurado:

   ```sh
   export RESTORE_DATABASE_URL='postgresql://<redacted>@<isolated-host>/<db>'
   DATABASE_URL="$RESTORE_DATABASE_URL" python -m alembic current
   DATABASE_URL="$RESTORE_DATABASE_URL" python -m alembic upgrade head
   ```

5. Ejecutar conteos y checks de integridad desde una sesión protegida. Como
   mínimo, comparar `guests`, `reservations`, `payments` y `audit_logs` con el
   inventario esperado; comprobar FKs inválidas, pagos completados sin su
   transacción, reservas con huésped inexistente y aislamiento entre dos
   `hotel_id` sintéticos. Guardar sólo resultados agregados, nunca PII ni DSN.
6. Levantar una instancia de aplicación contra el destino aislado, en modo
   controlado, y ejecutar smoke tests de lectura: login QA, lista de reservas,
   ficha de huésped, estado de pago, auditoría y reportes. Confirmar que el SHA y
   las migraciones coinciden con el release elegido.
7. Medir desde el timestamp de solicitud hasta que schema, conteos y smoke tests
   estén verdes. Registrar RPO observado, RTO observado, filas esperadas vs.
   recuperadas y cualquier pérdida aceptada.
8. Destruir el destino aislado y sus credenciales temporales según la política
   aprobada, o conservarlo sólo si el responsable lo autoriza. No hacer cutover
   ni cambiar `DATABASE_URL` productivo como parte de este ensayo.
9. El responsable humano firma el resultado: `passed`, `failed` o `blocked`, con
   enlace al ticket interno y acciones correctivas. Un backup sin este restore
   reproducido no se marca como verificado.

Si en el futuro se autoriza un cutover, debe existir un plan separado con
freeze/reanudación de escrituras, rollback, aprobación explícita y evidencia
posterior al SHA; este runbook no lo autoriza.

## Calendario y alertas

### Cadencia sugerida

- Diario: revisar el último backup/PITR point y fallos del proveedor; responsable:
  operador de infraestructura.
- Semanal: revisar edad de la copia más antigua, espacio, retención efectiva y
  errores de conexión/migración; responsable: responsable técnico.
- Mensual: restore drill en una base aislada y medición de RPO/RTO; responsable:
  infraestructura con firma del Product/Project Lead.
- Trimestral: ensayo de recuperación desde un punto histórico y revisión de la
  copia inmutable; responsable: infraestructura + responsable de seguridad.
- Anual o ante cambio de plan: revisar obligaciones de retención, costos,
  ownership, cifrado y contactos de escalamiento.

### Alertas mínimas

| Alerta | Dónde configurarla | Destinatario y respuesta |
|---|---|---|
| Backup/PITR fallido o último punto fuera de 15 min | Supabase Dashboard/notification channel, si el plan lo permite | Infra/on-call: abrir incidente, confirmar si hay punto alternativo; no declarar RPO cumplido. |
| Ventana de retención menor a 35 días o storage próximo al límite | Supabase | Infra + Product Lead: revisar capacidad/costo antes de cambiar plan. |
| Restore drill fallido o RTO > 60 min | Ticket/alert manager interno y registro del runbook | Infra + seguridad: bloquear release de continuidad y corregir/repetir. |
| `alembic upgrade head` fallido en pre-deploy | Logs/alertas del servicio Render | Backend/on-call: detener promoción, revisar migración y hacer forward-fix seguro. |
| Redis/worker persistence o backlog degradado | Render metrics/logs | Backend/on-call: recordar que Redis no es el backup OLTP y verificar PostgreSQL por separado. |
| Errores sostenidos de conexión a PostgreSQL o health datastore | Render metrics/logs y monitorización de aplicación | On-call: investigar disponibilidad; no restaurar ni rotar secretos automáticamente. |

Los nombres exactos de canales, umbrales del proveedor y responsables nominales
son `needs-verification` porque no están en el repo y requieren acceso humano a
las consolas/costos contratados.
