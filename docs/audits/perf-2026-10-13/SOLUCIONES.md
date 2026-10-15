# Soluciones concretas — qué cambiar, dónde y cómo se comprobó

Complemento de [`REPORT.md`](REPORT.md) (diagnóstico y plan) y [`LECTURA-COMPLETA.md`](LECTURA-COMPLETA.md) (notas archivo por archivo). Aquí está **el cambio** para cada hallazgo de mayor impacto, con su estado:

- **Probado**: el código de esta carpeta se ejecutó y su autoprueba pasó (se indica el comando).
- **Prototipo medido**: se aplicó a una copia descartable y se midió (`prototypes/`); no es para mergear tal cual.
- **Diseño**: cambio descrito con el punto exacto del código; falta implementarlo y probarlo en el repo.

Nada de esto modifica código de producto: el PR de auditoría es solo documentación.

---

## A. Integridad y seguridad (antes de abrir el piloto)

### S1 · La auditoría posterior al `commit` se pierde (N1) — *Diseño + guardia reproducible*

**Causa** (`app/services/audit_log_service.py:136-181`): `safe_create_audit_log` *nunca hace commit*; la fila queda "durable solo con la transacción de negocio del llamador". Los 15 sitios que la invocan **después** de `db.commit()` abren una transacción nueva, insertan la fila, y al cerrar la sesión (`get_db`) se hace `rollback`. En PostgreSQL se pierde; en SQLite persiste por una rareza del SAVEPOINT, por eso ningún test lo detecta (`scripts/audit_loss_repro.py`).

**Cambio** (mismo patrón en los 15 sitios que lista `scripts/scan_post_commit_audit.py`): auditar *antes* del `commit`, después de un `flush()` que asigne los ids.

```python
# app/api/guests.py — create_guest (hoy: commit → refresh → audit)
db.flush()                         # guest.id y companion.id disponibles, aún sin commit
if created:
    audit_log_service.safe_create_audit_log(db, hotel_id=context.hotel_id, table_name="guests",
        record_id=guest.id, action=AuditActionEnum.CREATE, actor_user_id=context.user_id,
        payload_after=audit_log_service.model_snapshot(guest))
for companion in new_companions:
    audit_log_service.safe_create_audit_log(db, ..., record_id=companion.id, ...)
db.commit()                        # negocio + auditoría en UNA transacción
db.refresh(guest)
```

**Guardia para que no vuelva a pasar:** en CI, ejecutar `scripts/scan_post_commit_audit.py` y fallar si informa > 0 sitios (agregar `sys.exit(1 if res else 0)` al final), más un test de integración contra PostgreSQL que compruebe que existe la fila de `audit_logs` tras un `POST /api/guests/`.

### S2 · Archivos en disco efímero (N2) — *Diseño*

1. `app/config.py` (validador de producción): agregar el error `OBJECT_STORAGE_BACKEND must not be 'local' in production`.
2. Implementar el backend S3-compatible (hoy `object_storage.py` solo tiene GCS completo): Cloudflare R2 ofrece capa gratuita compatible con S3; Supabase Storage (1 GB gratis) es la alternativa sin cuenta nueva.
3. Migrar los `PaymentProofBlob.content` (imágenes dentro de la base) al bucket y dejar solo la clave de objeto.
4. `render.yaml`: si se conserva `local` solo en desarrollo, no declarar disco.

### S3 · Credenciales de proveedores en claro (N3) — *Diseño*

`onboarding_service.upsert_payment_methods/upsert_ota_channels` persiste `payload.model_dump()` como JSON. Ya existe el cifrado que usa Stripe/MFA:

```python
from app.services.encryption import get_encryption_fernet   # exige clave Fernet propia en producción
f = get_encryption_fernet()
secret_fields = {"access_token", "client_secret", "api_key", "password", "webhook_secret"}
def seal(creds: dict[str, str]) -> dict[str, str]:
    return {k: ("enc:" + f.encrypt(v.encode()).decode() if k in secret_fields and v else v) for k, v in creds.items()}
```

Aplicar `seal` antes de serializar y descifrar solo al activar el proveedor. La lectura del estado ya devuelve solo `has_credentials` y los nombres de campo (`onboarding_service.py:149-155`): mantenerlo así. Rotar las credenciales que ya se hayan cargado en una base real.

### S4 · La API pública de reservas expone documentos (N4) — *Diseño*

`PublicReservationCreate.guest_id` permite referenciar cualquier huésped y `PublicReservationRead.guest` devuelve `document_type`/`document_number` (✔ `scripts/verify_public_booking_pii.py`). Cambio: el endpoint recibe los datos del huésped (nombre, correo, teléfono) y **crea o resuelve** el huésped dentro del hotel de la clave, y el esquema público devuelve un `PublicGuestSummary` sin documento ni dirección.

### S5 · `/health/datastores` público (N15) — *Diseño*

Dejar `/health/live` y `/health/ready` públicos (Render los usa) y proteger `/health/datastores` con la dependencia de administrador maestro que ya usa el panel o con un secreto en cabecera.

---

## B. Costo por request (el mayor retorno de consumo)

### S6 · Una línea que evita el 500 tras un corte de conexión — *Diseño trivial*

`app/database.py:154` (`_handle_query_error`) accede a `exception_context.connection.info` sin comprobar `None`; con `pool_pre_ping` la conexión puede no existir todavía.

```python
@event.listens_for(engine, "handle_error")
def _handle_query_error(exception_context):
    connection = exception_context.connection
    if connection is None:          # falló antes de tener conexión (pre-ping, reconexión)
        return
    starts = connection.info.get(_SLOW_QUERY_START_KEY)
    ...
```

### S7 · Costo fijo por request: de 9 a ~4 sentencias — *Prototipo medido*

`prototypes/02-auth-cache-and-single-set-config.patch` (+36 % req/s en endpoints livianos). Versión de producción:

- **Un solo `set_config`**: `SELECT set_config('app.user_id', :u, true), set_config('app.hotel_id', :h, true)` en lugar de dos sentencias, y reaplicarlo en `after_begin` con la misma sentencia (`tenant_context.reapply_tenant_context_on_connection`).
- **Quitar `pool_pre_ping=True`** (un viaje por checkout) y reemplazarlo por `pool_recycle=300` más reintento único ante `OperationalError` de desconexión (S6 es requisito).
- **Permisos efectivos**: resolver solo el permiso solicitado y cachear el diccionario por `(hotel_id, user_id, rol)` con TTL corto, invalidado por el `NOTIFY` que el sistema ya emite al cambiar permisos/membresías. El prototipo usó TTL fijo de 10 s *sin* invalidación (omite a propósito la revocación inmediata): para producción hay que invalidar con el evento.

### S8 · Carga perezosa por defecto — *Prototipo medido (+ receta)*

`prototypes/01-lazy-select-all-relationships.sh` cambia las 138 relaciones a `lazy="select"` (analytics/rooms 2.370 → 17 ms; RSS 1.233 → 611 MB; sin 503). **No es para mergear solo**: rompe serializadores (`/api/bookings/`: 47 → 6.512 consultas). Receta:

1. Cambiar el default a `lazy="raise_on_sql"` en lugar de `select`: cualquier carga implícita falla en tests en vez de degradar en silencio.
2. Ejecutar la suite: fallan los endpoints que dependen de una relación; en cada uno agregar `selectinload(...)`/`joinedload(...)` explícito (hoy ya lo hacen 11 archivos).
3. Agregar el **test de presupuesto de consultas por endpoint** (equivalente backend de `query-load-budget.test.mjs`): `assert queries <= N` por ruta con `app.database.start_request_db_metrics`, para que el N+1 no vuelva.
4. Tras el cambio solo fallan 6 tests de aserciones sobre la *forma* del SQL (§ 3.1 del informe).

### S9 · Reportes con `GROUP BY` — *Diseño (con prueba de paridad obligatoria)*

`financial_report_service.py:215-330` trae todas las transacciones y reservas como objetos y suma en `defaultdict`. **No se propone aquí una consulta lista** porque las reglas de negocio viven en Python (`filter_pms_revenue_transactions`, `reportable_origin`, moneda de cobro `tender_currency or currency`). Pasos:

1. Escribir la consulta agregada (`SUM(...) GROUP BY currency, payment_method, día`, `JOIN reservations`) con las reglas como `CASE`/columnas; donde una regla no se exprese en SQL, **materializar el indicador al escribir** (columna en `transactions`).
2. **Prueba de paridad**: sembrar una base (`scripts/seed_profile.py`) y comprobar que la versión SQL y la actual devuelven el mismo reporte para varios rangos y hoteles; recién entonces reemplazar.
3. Meta: 110 → ≤ 6 sentencias, 2,9 s → ≤ 150 ms.

---

## C. Procesos en segundo plano y retención

### S10 · Retención con `pg_cron` — *Probado*

`solutions/retention_pg_cron.sql` define `hotel_chipre_private.purge_operational_data()` (lotes de 10.000) para `rate_limit_events` (1 día), `security_tokens` (1 día tras vencer/consumirse) y `domain_event_outbox` (publicados 7 días; resueltos 30). Sigue el patrón de `alembic/versions/20260925_public_inquiry_retention.py`. **Prueba:** `DATABASE_URL_PSQL=postgresql://USER:PASS@127.0.0.1:5440/BASE solutions/test_retention.sh` → borra lo viejo y conserva lo vigente. Pendiente: envolverlo en una migración Alembic (con el mismo *fail-closed* en producción si no hay `pg_cron`) y confirmar que `_replay_or_reset` (`domain_events.py:1780`) reinicia a los clientes con cursor anterior a la retención. `app/tasks/cleanup_tokens.py` existe pero **no lo ejecuta nadie**: esta función lo reemplaza.

### S11 · Un solo programador de tareas — *Diseño*

1. `POST /internal/jobs/run` autenticado con `INTERNAL_JOBS_SECRET` (comparación en tiempo constante) que llama a `run_scheduled_hotel_jobs`.
2. Cloudflare Cron Trigger (5 gratuitos) cada 5–15 min que hace ese `POST`:

```js
// worker de Cloudflare (cron trigger)
export default { async scheduled(_e, env) {
  const r = await fetch(`${env.API_URL}/internal/jobs/run`, { method: "POST", headers: { "x-jobs-secret": env.JOBS_SECRET } });
  if (!r.ok) throw new Error(`jobs ${r.status}`);
}};
```

3. Apagar el servicio cron de Render (288 contenedores/día → 0), borrar `render-no-show-cron.yaml` (apunta a un servicio inexistente) y el árbol Celery/beat.

### S12 · Webhooks que no bloquean el bucle de eventos (N9) — *Diseño trivial*

`app/api/ota_webhooks.py:48-80` declara `async def` y llama a código síncrono de base. Separar: leer el cuerpo con `await`, luego ejecutar la parte de base en el *threadpool*:

```python
from starlette.concurrency import run_in_threadpool
payload = await _guarded_json_payload(...)           # solo I/O de red (await)
return await run_in_threadpool(_handle_ota_webhook, "booking", hotel_id, webhook_secret, payload, db)
```

`validate_webhook_secret` (consulta síncrona) también debe ir dentro del *threadpool*. Mismo cambio en `whatsapp_meta_webhook` y en el snapshot de FX.

---

## D. Costo de CPU y de memoria

### S13 · HMAC en lugar de Argon2id para secretos de corta vida (N8) — *Probado*

`solutions/otp_hmac.py` (autoprueba: `python solutions/otp_hmac.py` → **4,6 µs** por verificación frente a ~59.000 µs de Argon2id). Mezcla propósito + sujeto + código con un *pepper* derivado de `INTEGRATIONS_ENCRYPTION_KEY`, comparación en tiempo constante y **convivencia con los hashes Argon2 existentes** (prefijo `hmac-sha256$` vs `$argon2`). Aplica a `adapters/memory_tokens.py` (6 dígitos), `temporary_action_grant_service.py:240` y `mfa_service.py` (códigos de recuperación; verificar hoy cuesta hasta 10 × 59 ms). **Compromiso a conocer:** si alguien obtiene a la vez la base *y* el pepper, un código de 6 dígitos cae en milisegundos; con Argon2 caería en ~16 h de CPU. Como los códigos viven 15 minutos y el pepper nunca está en la base, el riesgo residual es bajo; para contraseñas de personas **se mantiene Argon2id**.

### S14 · Tope global de cuerpo (N13) — *Probado*

`solutions/body_limit_middleware.py` (autoprueba: `python solutions/body_limit_middleware.py`): middleware ASGI puro, 413 por `Content-Length` y por conteo en cuerpos *chunked*, topes por prefijo para las rutas que sí reciben imágenes base64.

### S15 · Limitador de intentos en memoria con respaldo en BD solo al bloquear — *Diseño*

Hoy cada intento cuesta 4 sentencias + `commit` (✔ `measure_hot_paths.py`; 20 intentos = 80 sentencias). Con **un solo worker** (`render.yaml`) un contador en memoria con ventana deslizante es exacto y cuesta 0 sentencias; escribir en la tabla únicamente cuando se supera el límite (para que el bloqueo sobreviva a un reinicio y se pueda auditar). Si se escala a más de un worker, volver al contador compartido (Redis o BD).

### S16 · Clave de API pública: verificar con caché y espaciar la escritura (N6) — *Diseño*

10 sentencias + `commit` por llamada hoy. Cachear `(prefijo → hotel_id, propósito, vence)` en memoria 30–60 s e invalidar al revocar; escribir `last_used_at` como máximo una vez cada 5 minutos por clave (`UPDATE … WHERE last_used_at < now() - interval '5 min'`).

### S17 · `billing_policy` sin reflexión de tabla (N7) — *Diseño trivial*

`Table("master_billing_policies", MetaData(), autoload_with=bind)` (`master_admin/billing_policy.py:42`) en cada llamada = 21 sentencias. Declarar el modelo (ya existe en `master_admin/models.py`) y consultar una sola vez por pantalla del panel (una consulta agregada en vez de una por hotel).

---

## E. Dependencias, imagen y arranque

### S18 · Núcleo + extras opcionales — *Diseño*

`requirements.txt` (hoy 291 MB instalados, 178 MB de `ortools`/pandas/numpy):

```text
requirements.txt          # núcleo: fastapi, uvicorn[standard], sqlalchemy, alembic, psycopg2-binary, pydantic-settings, argon2-cffi, cryptography, requests…
requirements-dev.txt      # -r requirements.txt + pytest*
requirements-solver.txt   # ortools (import perezoso ya existente en allocation_engine)
requirements-celery.txt   # celery, redis   (solo si se reactiva)
```

`Dockerfile.backend` en dos etapas (compilar ruedas en la primera; la imagen final sin `build-essential` ni `libpq-dev` porque se usa `psycopg2-binary`) y `uvicorn[standard]` (uvloop/httptools). Retirar `pymongo`, `cassandra-driver` y `neo4j` junto con `app/db/*`, `graph_projection.py` y `timeseries_projection.py` (código que solo escribe).

---

## F. Hallazgos de la tercera pasada (§ 0.3 del informe): datos, operación y frontend

### S19 · Búsqueda de la clave de API pública compatible con RLS (M4) — *Probado (SQL)*

**Causa:** `hotel_api_keys` tiene RLS `FORCE` (`alembic/versions/20260820_missing_tenant_rls.py:24-26,53-56`) con política `hotel_id = NULLIF(current_setting('app.hotel_id'),'')::int`, pero `verify_key` (`app/services/hotel_api_key_service.py:69`) busca por `key_hash` **antes** de fijar `app.hotel_id` (`app/dependencies/api_key_auth.py:35-70`; el comentario afirma que esa búsqueda "queda fuera de RLS", y la política no lo permite). Con un rol `NOBYPASSRLS`: 0 filas → todas las claves dan 401. Con `BYPASSRLS`: la RLS no protege nada. Reproducido.

**Cambio:** [`solutions/api_key_lookup_under_rls.sql`](solutions/api_key_lookup_under_rls.sql) crea `hotel_chipre_private.lookup_api_key(hash)` (`SECURITY DEFINER`, `search_path` fijo, `REVOKE … FROM PUBLIC`, devuelve solo esa fila) y el índice único sobre `key_hash` que hoy falta (M3). `verify_key` pasa a `SELECT * FROM hotel_chipre_private.lookup_api_key(:h)` y luego `set_tenant_hotel_context`. La política de la tabla no se toca.

**Cómo se comprobó:** `PGHOST=127.0.0.1 PGPORT=5440 PGUSER=pgtest PGPASSWORD=pgtest bash solutions/test_api_key_lookup.sh` → consulta directa sin contexto 0 filas (el bug), `lookup_api_key(hash)` 1, hash inexistente 0, `SELECT *` sin contexto sigue en 0 (aislamiento intacto). **Falta** decidir el rol dueño de la función (necesita `BYPASSRLS`; en Supabase `postgres` lo tiene, `needs-verification`) y probarlo con el rol real de `DATABASE_URL`.

### S20 · Copia de seguridad lógica y restauración probada (O7) — *Probado (SQL local)*

**Causa:** no hay backup ni restauración programados en el repo; el plan gratuito no incluye PITR.

**Cambio:** [`solutions/backup_restore_drill.sh`](solutions/backup_restore_drill.sh): `pg_dump -Fc` → restaura en una **base nueva y descartable** → compara el conteo de filas de **todas** las tablas de `public` → borra la base de prueba → falla (código ≠ 0) si algo difiere; opcionalmente cifra con `age` antes de subir. Corre semanal desde un workflow programado de GitHub Actions (`on: schedule`) con `SRC_URL` = conexión directa de Supabase (no el pooler 6543) y sube el `.age` a un bucket gratuito (R2/B2). Un backup que nunca se restauró no cuenta.

**Cómo se comprobó:** contra el PostgreSQL local, 2 tablas / 2.005 filas → `DRILL OK`; con un `pg_dump` que inserta una fila después del volcado → `DIFIERE hotels: origen=6 restaurado=5` y `DRILL FALLO` (el drill sí puede fallar). **Falta:** probarlo contra Supabase real (límite de conexiones y de tamaño) y medir el tiempo con los datos del piloto.

### S21 · Minutos de CI y despliegues innecesarios (O3, O5) — *Diseño (YAML validado)*

**Cambio:** [`solutions/ci_concurrency_snippet.yml`](solutions/ci_concurrency_snippet.yml): `concurrency` con `cancel-in-progress` por PR (un push nuevo cancela los jobs ya obsoletos), `paths-ignore` para `docs/`, `knowledge/`, `qa/`, `.graphify/` y `*.md`, `timeout-minutes` en los jobs sin tope, caché de `~/.cache/ms-playwright`, y `buildFilter` en `render.yaml` para que solo `app/`, `alembic/`, `requirements.txt` y `runtime.txt` disparen despliegue. Quitar (o pasar a `workflow_dispatch`) `build-and-push.yml`: construye 2 imágenes por merge y nadie las consume. **Advertencia:** `paths-ignore` bloquea el merge si esos checks son *required* en la rama; en ese caso filtrar dentro del job.

**Ahorro:** con 63 de 111 commits no-merge (57 %) sin tocar código de ejecución y ≈ 29–35 min por push (e2e 16,1 min medido; resto estimado), lo evitable es del orden de la mitad de los minutos. No se midió en CI real.

### S22 · Arranque del frontend: menos requests antes de la primera consulta (F2) — *Diseño*

**Cambio** (los tres en `frontend/src`, sin tocar el backend):
1. `hooks/usePermissions.ts:16-22`: sembrar con lo que el refresh/login ya trajo.
```ts
const seeded = session.permissions && session.role
  ? { hotel_id: session.hotelId!, role: session.role, permissions: session.permissions }
  : undefined;
const query = useQuery<EffectivePermissionsResponse>({
  queryKey: effectivePermissionsKey(session.hotelId, session.userId),
  queryFn: () => fetchEffectivePermissions(session),
  enabled: hasValidSession(session),
  staleTime: 5 * 60 * 1000,
  initialData: seeded,
  initialDataUpdatedAt: seeded ? Date.now() : undefined, // cuenta como "fresco" por staleTime
});
```
2. El idioma de interfaz ya llega en `hotel-config`: eliminar `useHotelInterfaceLanguage` para quien tiene `hotel_settings:read` (y devolver `interface_language` en la respuesta del refresh para el resto; hoy `GET /api/config/interface-language` = 1 request + 1 `SELECT` por carga de página).
3. `GET /api/events/recovery` y `/api/events/stream` hoy son secuenciales (`src/sync/crossTabSync.ts:589-592`): lanzarlos en paralelo o fusionar el recovery en el primer mensaje del stream.

**Efecto esperado:** quita 2 de las 6 lecturas del shell (permisos, idioma: de 9 a 7 requests) y 1 viaje secuencial; fusionar `config/`, `onboarding/status`, `subscription/status` y `notifications?limit=1` en un `GET` de arranque lo lleva a ≈ 4; el refresh sigue bloqueando el render para quien ya tenía sesión (F2), por eso no es el cambio de mayor retorno por sí solo. No se ejecutó ni se midió.

### S23 · Datos de otra persona tras cerrar sesión (F5) — *Diseño trivial*

`SessionProvider` ya está dentro de `QueryClientProvider` (`main.tsx:47-57`), así que `logout` (`state/session.tsx:218-229`) puede vaciar la caché:
```ts
const queryClient = useQueryClient();
const logout = useCallback(() => {
  /* … igual que hoy … */
  setClientSession(null);
  setSession(EMPTY_SESSION);
  setRestoredSession(false);
  queryClient.clear();               // ← nuevo: ninguna consulta del usuario anterior sobrevive
}, [session, queryClient]);
```
Hacer lo mismo en `handleUnauthorized` (`api/client.ts`, la salida por 401) y agregar `session.userId` a las claves de caché con datos personales (`["notification-inbox", …]`, `["notification-preferences", …]`, `["reservations", …]`). Test: iniciar sesión como A, abrir `/reservas`, cerrar sesión, iniciar como B y comprobar que no se pinta ninguna fila de A antes de la respuesta de B.

### S24 · `PricingPage` no debe poder vaciar los planes (F6) — *Diseño trivial*

Backend: `schemas/marketing.py:84-85` → `plans: list[PlanIn] = Field(..., min_length=1)` (un `plans: []` pasa a 422). Frontend: `PricingPage.tsx:57-93` deshabilita "Publicar precios" mientras el `GET` esté cargando o haya fallado, y cambia `key={plan.code || index}` por un id estable (hoy pierde el foco al tipear el código). Test: `PUT` con `plans: []` → 422 y los planes siguen.

---

## Orden recomendado

| Orden | Solución | Esfuerzo | Efecto |
|---|---|---|---|
| 1 | S1, S2, S3, S4, S5 (§ A), S19, S24 | 1–3 días | Evita pérdida de datos, fuga de credenciales/documentos, claves de API caídas por RLS y el borrado de planes |
| 1-bis | S20 (backup + restauración probada), S21 (CI/despliegue), S23 | horas | Red de seguridad antes del primer dato real; −½ de minutos de CI; sin datos del usuario anterior en recepción compartida |
| 2 | S6 | minutos | Evita el 500 tras un corte de conexión |
| 3 | S8 con su test de presupuesto | 3–5 días | Memoria −50 %, ×3–×5 de capacidad con reportes |
| 4 | S7, S15, S16, S17 | 2–4 días | De 9 a ~4 sentencias por request |
| 5 | S9 con prueba de paridad | 3–5 días | Reportes de 2,9 s a ~150 ms |
| 6 | S10, S11, S12, S13, S14 | 2–3 días | Sin crecimiento no acotado, sin cron de pago, sin bloqueos del bucle |
| 7 | S18 y migración de frontend a Cloudflare Pages | 1–2 días | −65 % de dependencias; plan gratuito válido en licencia |
| 8 | S22 y el resto de F1–F16 (§ 0.3 del informe) | 3–5 días | De 9 requests de arranque a 7 (a ≈ 4 con un `GET` de arranque único); listas con ventana de fechas; sin fan-out de `analytics` |
