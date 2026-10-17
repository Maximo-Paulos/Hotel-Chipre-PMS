# Reloj de negocio para simulación local

El reloj de negocio permite avanzar de a un día a la vez para un hotel sintético durante QA local. No adelanta el reloj del sistema. En las marcas de tiempo operativas admitidas, usa la fecha de negocio del hotel y conserva la hora local actual; las marcas de seguridad y auditoría siguen en tiempo UTC real.

## Activación

La función queda apagada por defecto. Para habilitarla, configurá explícitamente estas condiciones:

- `APP_ENV=development` explícito.
- `LOCAL_SIMULATION_CLOCK_ENABLED=true`.
- `LOCAL_SIMULATION_CLOCK_HOTEL_ID=<id del hotel sintético>`.
- `EXTERNAL_EFFECTS_ENABLED=false`.
- `CONNECTIONS_ENABLED=false`.

La base puede ser SQLite local o PostgreSQL local. Para PostgreSQL, `LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE` debe nombrar exactamente la base permitida; `DATABASE_URL` y la sesión SQLAlchemy deben coincidir en base, host de loopback (`127.0.0.1` o `::1`) y puerto. No se permiten parámetros de conexión ni `PGSERVICE`; si existe `PGHOSTADDR`, también debe ser loopback. Cualquier discrepancia cierra el reloj.

Si una condición no coincide, `hotel_today(db, hotel_id)` usa la fecha actual del hotel y el endpoint de avance no modifica datos. La coincidencia del id hace que un segundo hotel del mismo proceso conserve su fecha normal. Un `ENVIRONMENT` legado que contradiga `APP_ENV=development` también cierra el reloj.

`GET /api/config/business-clock` requiere una membresía activa del hotel y permite lectura a todos los roles. `POST /api/config/business-clock/advance` requiere que el rol sea exactamente `owner`; avanza un día y registra la fecha anterior/nueva. La fecha operativa inicial es el día local actual del hotel. El flag `simulation_enabled` solo informa que todas las compuertas están abiertas para el hotel autenticado.

## Fechas de negocio y tiempo real

Las fechas implícitas usadas por calendario de tarifas, tarifa vigente de habitaciones, tablero de housekeeping, ventana de visibilidad de reservas, selección de promociones por fecha de reserva, defaults de reportes de Analytics/financieros, precio de lavandería sin `effective_from`, deduplicación diaria de alertas de stock y contexto operativo de Gemma usan `hotel_today`. También lo hacen los consumidores preexistentes de la helper: reservas/operación, reportes diarios, cargos nocturnos de empresas y horizonte de asignación.

Las marcas de tiempo de acciones operativas cubiertas usan `hotel_business_now` y se persisten como UTC normalizado en columnas heredadas sin zona horaria. Incluyen movimientos de stock y ropa blanca, remitos y seguimiento de lavandería, lotes de lavandería, tareas/eventos/fotos/pases de turno, caja, check-in/out y pagos. Los códigos diarios de lote de lavandería también usan la fecha del hotel. En modo normal, `hotel_business_now` devuelve la hora real UTC.

MFA, sesiones, invitaciones y sus vencimientos, tokens, auditorías de seguridad, login, expiraciones, reintentos de proveedores y eventos/outbox siguen usando hora UTC real. La tabla del reloj guarda `advanced_at` en hora real y el evento de auditoría conserva su timestamp real. Las marcas de tiempo técnicas o de configuración que no representan una acción operativa también conservan sus valores reales; no se reemplazan los defaults globales de los modelos.

La migración `20261017_local_business_clock` agrega la tabla si falta. Si el arranque local ya la creó con `Base.metadata.create_all`, valida su esquema, instala igualmente RLS por `hotel_id` en PostgreSQL y conserva cualquier fecha simulada existente. SQLite local no usa RLS. El downgrade elimina la tabla solo cuando no contiene estado; si hay una fecha guardada, falla para evitar perderla. No requiere backfill ni cambia otros datos existentes.
