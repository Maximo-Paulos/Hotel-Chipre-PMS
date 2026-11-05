# Pilot Runbook

## Objetivo

Preparar y recorrer una prueba local de Hotel Chipre PMS con PostgreSQL 16, datos sintéticos y efectos externos controlados. Este runbook no habilita cobros ni envíos reales.

## Preflight de base de datos

1. Usar exclusivamente el perfil Colima `hcpms-codex-qa` y el contenedor PostgreSQL 16 del proyecto. Si el perfil está detenido, iniciarlo; no borrar ni reutilizar otros perfiles, contenedores, volúmenes o bases.
2. Confirmar la versión del servidor y el puerto local publicados antes de conectar. La configuración activa del perfil usa loopback en el puerto `55433`.
3. Crear una base vacía y desechable, con roles de prueba propios, para cada corrida independiente. Cargar solo datos sintéticos. No derivar `DATABASE_URL` desde `.env`, `.env.render` ni una conexión remota.
4. Para pruebas backend con `pg_session`/`pg_engine`, pasar `DATABASE_URL_TEST` y `POSTGRES_TEST_DATABASE_URL_EXPLICIT` con el mismo DSN local, junto con toda la evidencia exigida por `tests/postgres_test_safety.py`. La guarda debe confirmar host, puerto, nombre de base, rol, rama y clasificación `synthetic-only` antes de que se creen tablas.
5. Para Playwright, seguir [frontend/e2e/README.md](../frontend/e2e/README.md): base PostgreSQL 16 nueva, roles separados `_app_runner` y `_seed_runner`, variables E2E explícitas y efectos externos deshabilitados.

La skill local `colima-postgres-only` contiene el procedimiento completo de aislamiento y limpieza. Borrar únicamente la base y los roles creados por esa corrida, después de verificar sus nombres exactos. Nunca usar SQLite, aunque una fixture antigua o un comando genérico lo elija por defecto.

## Validación previa

Aplicar migraciones solo con `DATABASE_URL` fijada explícitamente a la base PostgreSQL local desechable:

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
```

Ejecutar pruebas con fixtures PostgreSQL y la guarda de aislamiento activa. Por ejemplo:

```bash
.venv/bin/python -m pytest \
  tests/test_fx_rate_cache_postgres.py \
  tests/test_manual_fx_payment_quotes_postgres.py \
  tests/test_rate_money_precision_postgres.py -q
```

No ejecutar `pytest -q` como validación integral: `tests/conftest.py` todavía define la fixture general `db_engine` sobre SQLite en memoria, y muchos módulos crean sus propias bases SQLite. Esos módulos no cuentan como validados para este piloto hasta migrar sus fixtures y probarlos en PostgreSQL. Un subconjunto focal aprobado tampoco equivale a cobertura completa.

Las validaciones frontend que no usan base pueden correrse aparte:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

## Controles de efectos externos

- Mantener pagos, Mercado Pago, Gmail, Resend, WhatsApp, OTAs y eventos entrantes deshabilitados durante simulaciones locales. Los cobros y notificaciones de proveedor se simulan; no llamar a Mercado Pago.
- DolarAPI puede habilitarse por separado para la consulta pública y de solo lectura solicitada para la cotización. Una respuesta válida se guarda en PostgreSQL con la hora en que el PMS la recibió. Si la API falla, se permite ese respaldo hasta 24 horas; vencido, no hay conversión automática.
- Cuando no queda cotización automática vigente, una persona con `payment:fx_manual_set` puede fijar un monto para una reserva, moneda y medio determinados, con motivo y auditoría. El cobro posterior requiere permiso de caja y conserva exactamente el importe aprobado; la autorización se consume una sola vez.
- WhatsApp debe mostrarse como **Próximamente** y sus rutas de API, CRM y webhook deben permanecer bloqueadas para la prueba.

## Recorrido operativo sintético

1. Crear un hotel vacío y completar onboarding con Owner, Recepción y Gerencia sintéticos.
2. Configurar categorías, habitaciones, moneda, tarifas, política de seña e impuestos antes de cotizar.
3. Crear reservas manuales; validar asignación, búsqueda, edición y conflictos.
4. Recorrer llegada, check-in parcial y completo, cambios de habitación permitidos, checkout y cierre de caja.
5. Probar cobros en efectivo, pagos mixtos, saldo, recibo y devoluciones simuladas. Mercado Pago no forma parte de esta fase local.
6. Probar permisos con cada rol: Recepción no fija una cotización FX manual; una persona autorizada sí; Recepción puede cobrar el monto previamente aprobado sin modificarlo.
7. Probar la caída de DolarAPI con respuestas simuladas: cotización actual, respaldo menor de 24 horas, respaldo vencido, monto manual autorizado y rechazo de una conversión automática sin respaldo.
8. Revisar reportes, auditoría, caja, notificaciones locales, responsive y errores visibles.

## Criterios de parada

Detener la validación del flujo afectado si:

- la conexión no apunta al PostgreSQL 16 local desechable o no supera la guarda de aislamiento;
- migraciones fallan o el esquema no llega al head esperado;
- se puede cobrar una moneda distinta con una tasa vencida sin autorización manual;
- un usuario sin permiso puede fijar el monto, o quien cobra puede alterarlo;
- se duplica un pago, se supera el saldo, se pierde la auditoría o se mezcla información entre hoteles;
- una simulación intenta contactar Mercado Pago, un proveedor de correo, WhatsApp u OTA;
- el recorrido de reserva, asignación, check-in/out o caja deja datos inconsistentes.

## Estado de cierre

Registrar para cada corrida: SHA de `HEAD` y cambios locales, perfil y versión PostgreSQL, identidad de la base desechable, pruebas ejecutadas y omitidas, estado de migraciones, flags de efectos externos, resultados UI/API y fallos reproducibles. No declarar la app lista mientras haya módulos DB que solo se ejecuten con SQLite, regresiones sin cubrir o pasos de OAuth/webhooks que todavía no se puedan validar localmente.
