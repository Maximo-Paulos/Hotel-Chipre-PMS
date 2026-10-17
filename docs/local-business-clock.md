# Reloj de negocio para simulación local

El reloj de negocio permite avanzar de a un día a la vez para un hotel sintético durante QA local. El cambio afecta fechas de operación; nunca adelanta el reloj del sistema ni fabrica instantes.

## Activación

La función queda apagada por defecto. Para habilitarla, configurá en el entorno local las cuatro condiciones siguientes:

- `APP_ENV=development` explícito.
- `LOCAL_SIMULATION_CLOCK_ENABLED=true`.
- `LOCAL_SIMULATION_CLOCK_HOTEL_ID=<id del hotel sintético>`.
- `DATABASE_URL` con dialecto SQLite.

Si una condición no coincide, `hotel_today(db, hotel_id)` usa la fecha actual del hotel y el endpoint de avance no modifica datos. La coincidencia del id hace que un segundo hotel del mismo proceso conserve su fecha normal.

`GET /api/config/business-clock` requiere una membresía activa del hotel y permite lectura a todos los roles. `POST /api/config/business-clock/advance` requiere que el rol sea exactamente `owner`; avanza un día y registra la fecha anterior/nueva. La fecha operativa inicial es el día local actual del hotel. El flag `simulation_enabled` solo informa que todas las compuertas están abiertas para el hotel autenticado.

## Fechas de negocio y tiempo real

Las fechas implícitas usadas por calendario de tarifas, tarifa vigente de habitaciones, tablero de housekeeping, ventana de visibilidad de reservas, selección de promociones por fecha de reserva, defaults de reportes de Analytics/financieros, precio de lavandería sin `effective_from`, deduplicación diaria de alertas de stock y contexto operativo de Gemma usan `hotel_today`. También lo hacen los consumidores preexistentes de la helper: reservas/operación, reportes diarios, cargos nocturnos de empresas y horizonte de asignación.

La hora real UTC sigue controlando MFA, sesiones, invitaciones y sus vencimientos, tokens, auditoría, login, expiraciones, reintentos de proveedores, eventos/outbox y marcas de tiempo de pagos, correos y operaciones. La tabla del reloj guarda `advanced_at` en hora real, y el evento de auditoría conserva su timestamp real. Los datos `created_at`/`updated_at` siguen siendo instantes reales.

La migración `20261017_local_business_clock` agrega la tabla si falta. Si el arranque local ya la creó con `Base.metadata.create_all`, valida su esquema y conserva cualquier fecha simulada existente. El downgrade elimina la tabla solo cuando no contiene estado; si hay una fecha guardada, falla para evitar perderla. No requiere backfill ni cambia otros datos existentes.
