# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Alcance

Recorrido de solo lectura de la aplicación pública compartida usando las sesiones disponibles de Dueño, Gerencia y Recepción. No se usó Render QA. El catálogo local identifica el destino como `production-labelled-shared-sandbox-operational` y `release_gate_eligible=false`; por eso los resultados sirven para operación y diagnóstico, no para aprobar un release.

## Identidad y estado del servicio

- Reconsulta en vivo: **2026-10-05 05:00 ART (UTC-03)**. Las observaciones de interfaz de abajo fueron manuales durante esta sesión; no se guardaron capturas ni artefactos sanitizados.
- API `GET /health`: estado `ok`, `code_sha=0174f497cc615550c21ba5c78bac0b6893729c7b`.
- Frontend `GET /build-meta.json`: mismo `code_sha`.
- `GET /health/ready` (observación previa de esta misma sesión): `ready=true`; PostgreSQL conectado; Redis desconectado; el lock crítico opera con el advisory lock de PostgreSQL.
- `GET /health/datastores` reconsultado en vivo: PostgreSQL `connected=true`; Redis está configurado para caché, locks distribuidos y realtime, pero `connected=false` (`Redis healthcheck failed`). ClickHouse, Mongo, Cassandra y Neo4j están deshabilitados.
- Al momento de esta reconsulta, PR #119 estaba abierto con HEAD remoto `483cba6319b1d1a7621d13011a2af0f008bf398f`; ese SHA no está en el servicio. El SHA servido debe volver a verificarse tras integrar los cambios de esta rama.

## Recorrido visible

| Cuenta | Pantalla | Observación | Estado |
|---|---|---|---|
| Dueño | Reservas → Caja | Reservas terminó de cargar. Caja mostró el botón “Registrar gasto”; el formulario expuso categoría, proveedor, referencia del comprobante y adjunto privado. No se envió el formulario. La navegación cálida hasta el encabezado de Caja tardó 3.092 ms en una sola muestra. | PASS, solo lectura |
| Dueño | Reportes | La pantalla cargó y mostró las secciones de cobros y caja; no había cobros del día consultado. No se alteraron filtros ni datos. | PASS, solo lectura |
| Recepción | Habitaciones | La pantalla mostró el inventario de 39 habitaciones; no apareció un enlace de Caja ni el error consultado. | PASS, solo lectura |
| Gerencia | Detalle de reserva existente | La pestaña conservaba un formulario de cobro visible. Se dejó intacto y no se pulsó Registrar cobro. La ruta directa a Caja mostró acceso denegado. | PASS parcial; sin envío |
| Gerencia | Permisos / Caja | En la matriz administrativa del Dueño se observó `cash:view` desactivado por un override explícito de rol, aunque `cash:operate`, `cash:expense` y `cash:expense_approve` estaban habilitados. Esto explica que Gerencia no vea Caja. No se cambió la matriz. | Hallazgo de configuración; requiere decisión del Dueño |

La medición de 3.092 ms incluye interacción y espera visible del navegador; no es duración pura de API ni permite calcular percentiles. No se capturaron datos de huéspedes ni importes para el reporte.

## Hallazgos de rendimiento

- La hipótesis de espera en publicaciones de eventos al guardar sigue siendo plausible: Redis está desconectado y los timeouts de cliente son de 1 s. El cambio de PR #119 reduce intentos repetidos dentro de un lote, pero la integración y el efecto real de latencia aún no están verificados.
- El diff local sobre la rama asociada a PR #119 acumula primero los resultados Redis y actualiza el outbox por hotel con contexto RLS explícito, sin mantener checkout de PostgreSQL durante llamadas Redis. La regresión corre localmente con SQLite; PostgreSQL real con `FORCE ROW LEVEL SECURITY` queda sin verificar.
- El diff local añade un cooldown de 30 s solo al camino durable después del commit; los eventos best-effort e invalidaciones directas siguen su camino actual. El replay puede drenar un lote si Redis responde, pero ante `RealtimeEventsUnavailable` deja intactas las filas aún no procesadas y detiene el barrido de otros hoteles. No se midió todavía el efecto de estos cambios sobre latencia en la nube.
- Un agente de rendimiento confirmó que la caché tiene una pausa local de Redis tras fallar, mientras que el publicador de eventos y los locks críticos siguen sus propios caminos. La caída de Redis puede degradar lecturas/cambios distintos; no se atribuye toda la lentitud a una causa única.
- Una sola navegación observada no permite estimar p50/p95/p99. El plan Free puede añadir demoras de arranque tras inactividad; no se cambió el plan ni la configuración del proveedor.

## Cambios externos y límites

- No se registraron cobros ni gastos; no se cambiaron reservas, permisos ni configuración.
- No se enviaron correos ni se activaron webhooks u OTAs.
- El dominio es compartido y no quedó probado que los registros marcados QA estén en un tenant aislado y desechable. Por eso no se alteró el ledger financiero.
- La sesión de Gerencia quedó tal como estaba, con el formulario sin enviar.
- Este recorrido no cubre el resto de la matriz de roles ni reemplaza las pruebas locales de PostgreSQL/RLS o la puerta de release.

## Validación local

- Suite completa final del backend: `uv run --no-project --with-requirements requirements.txt pytest -q` — **2.851 passed, 34 skipped, 12 xfailed** (50 warnings) en 341,61 s.
- Suite focal final — `tests/test_domain_events.py`, `tests/test_tenant_context_after_commit.py`, `tests/test_domain_event_outbox.py`, `tests/test_analytics_task_schedule.py`, más los dos casos afectados por aislamiento del cooldown — **55 passed**.
- Estas pruebas usan SQLite en este entorno y no demuestran PostgreSQL con `FORCE ROW LEVEL SECURITY`. No se usó una instancia PostgreSQL desechable para esta verificación.
