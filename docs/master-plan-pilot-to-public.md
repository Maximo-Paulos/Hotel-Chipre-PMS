# Plan Maestro Ejecutable: Piloto Real -> Salida Publica

Este documento esta pensado para que un modelo mas chico ejecute el trabajo con la menor cantidad posible de razonamiento adicional.

## Estado de partida validado

- El PMS ya tiene base funcional de reservas, habitaciones, pagos, conexiones y Gemma.
- El motor de autoasignacion existe y usa OR-Tools, pero no termina de aplicar la penalizacion de fragmentacion/gap day.
- OTA hoy funciona sobre todo como `webhook inbound -> normalizacion -> creacion de reserva`.
- Gemma hoy analiza, propone y genera drafts controlados; no debe autoaplicar cambios sin revision.

## Revision del plan base

### Revision 1: huecos detectados

1. OTA inbound no procesa bien lifecycle real de reservas existentes.
2. Los adapters OTA siguen en stub para muchas operaciones.
3. El solver no aplica de verdad la logica de huecos de una noche.
4. Las operaciones manuales criticas existen en backend pero no estan cerradas en UI.
5. La gestion de huespedes existe en API pero no en UX completa.
6. OTA no guarda roster completo de pasajeros; solo guest principal basico.
7. La UX visual del dueno tiene base, pero no una consola operativa completa.

### Revision 2: correcciones de plan aplicadas

1. Separar claramente `piloto real` de `salida publica`.
2. No intentar cerrar outbound OTA completo antes del piloto; si cerrar lifecycle inbound y resolucion operativa.
3. Forzar criterio de seguridad operativa: ante duda, marcar `manual_review` en vez de automatizar.
4. Mantener a Gemma como capa de sugerencias y drafts, nunca como ejecutor libre.
5. Priorizar UX operativa del dueno y front desk antes de pulido visual final.

## Reglas de ejecucion obligatorias

1. No pedir confirmacion del usuario entre tareas salvo que falte:
   - una credencial externa real,
   - una definicion de negocio riesgosa no inferible del repo,
   - un dato operativo del hotel piloto.
2. Si una decision es dudosa, elegir la opcion mas conservadora:
   - no sobreescribir datos,
   - no autoaplicar cambios de politica,
   - no resolver conflictos OTA en silencio,
   - no borrar informacion historica.
3. Toda logica nueva debe respetar `hotel_id` en backend y la sesion activa en frontend.
4. Toda accion manual relevante debe dejar trazabilidad:
   - quien,
   - cuando,
   - que cambio,
   - motivo.
5. Cada bloque se cierra con:
   - tests puntuales,
   - test suite backend,
   - build frontend,
   - nota breve de estado.
6. No tocar simultaneamente integraciones externas y UX final si primero no esta estable el dominio.

## Definicion de terminado

### Terminado para piloto real

Se considera listo para piloto cuando se cumplan todos:

1. Booking, Expedia y Despegar soportan inbound `new / modified / cancelled / duplicate`.
2. El solver aplica fragmentacion real, estabilidad, exact match y manual review de forma auditable.
3. El dueno puede operar reservas, mover habitaciones, recalcular asignacion y cerrar conflictos sin usar API manual.
4. Existe ficha/listado de huespedes con historial y datos de check-in.
5. Gemma puede leer contexto real, capturar feedback operativo y generar drafts utiles.
6. Hay runbook de piloto y checklist de smoke tests.

### Terminado para salida publica

Se considera listo para cobrar cuando, ademas del piloto exitoso, se cumplan todos:

1. Outbound OTA critico implementado.
2. Hay staging y produccion definidos.
3. Hay backups y restauracion probada.
4. Hay observabilidad minima.
5. Hay hardening de secretos y despliegue.
6. Hay onboarding guiado y documentacion operativa minima.

## Orden macro de ejecucion

Ejecutar en este orden exacto:

1. Fase A - Core operativo para piloto.
2. Fase B - Hardening del piloto.
3. Fase C - Ejecucion del piloto real.
4. Fase D - Cierre para salida publica.

No invertir el orden.

---

## Fase A - Core operativo para piloto

Objetivo: dejar el PMS utilizable de punta a punta para un hotel real, sin depender de API manual ni de razonamiento externo del operador.

### A1. Cerrar lifecycle OTA inbound real

#### Objetivo

Soportar correctamente reservas OTA nuevas, modificadas, canceladas y deliveries duplicados sin desorden interno.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota_service.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota/contracts.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota/adapters/booking.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota/adapters/expedia.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota/adapters/despegar.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/models/ota_core.py`
- tests OTA existentes o nuevos en `tests/`

#### Decisiones obligatorias

1. Mantener idempotencia por `hotel_id + provider + external_reservation_id`.
2. Si el webhook modifica una reserva ya existente:
   - actualizar datos permitidos,
   - si el cambio rompe disponibilidad, marcar `requires_manual_review`,
   - generar accion pendiente.
3. Si el webhook cancela:
   - cancelar reserva interna si todavia es pre-check-in,
   - si ya esta check-in/check-out, no cancelar a ciegas; abrir conflicto operativo.
4. Si llega un duplicate delivery, no duplicar huesped ni reserva.

#### Tareas

1. Refactorizar `_process_normalized_webhook` para distinguir:
   - alta nueva,
   - actualizacion,
   - cancelacion,
   - duplicate noop.
2. Incorporar en `NormalizedOTAReservation` o metadata equivalente el `event_type` si hace falta.
3. Crear handlers internos separados:
   - `_create_incoming_reservation`
   - `_update_incoming_reservation`
   - `_cancel_incoming_reservation`
4. Al actualizar:
   - sincronizar fechas, adultos, ninos, currency, pricing snapshot, settlement hints y notas permitidas.
   - nunca perder el historico OTA link.
5. Si cambia categoria/producto/cupo y no entra automaticamente:
   - no forzar una mala asignacion,
   - dejar `allocation_status=manual_review`,
   - crear follow-up operativo.
6. Si la reserva cancelada tiene ajustes o settlement pendiente:
   - reflejarlo en `pending_actions`.

#### Validacion minima

Crear tests para:

1. `new booking` crea guest/reservation/link.
2. `duplicate booking` no duplica.
3. `modify booking` actualiza fechas/montos.
4. `cancel booking` cancela si corresponde.
5. `cancel booking post-checkin` genera conflicto manual, no destruye el estado real.
6. Igual para Expedia y Despegar usando el bridge normalizado.

#### Criterio de cierre

- lifecycle inbound resuelto y testeado;
- no quedan ramas que devuelvan mapping existente sin procesar el evento.

### A2. Completar el motor de autoasignacion

#### Objetivo

Convertir el solver actual en uno compatible con el requisito central: minimizar huecos de una noche y fragmentacion real.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/allocation_engine.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/allocation_runtime_service.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/allocation_policy_service.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/models/allocation.py`

#### Decisiones obligatorias

1. El solver sigue siendo la fuente de verdad.
2. El solver nunca debe mover reservas locked o check-in.
3. Ante imposibilidad, marcar `manual_review`, no improvisar.
4. La politica publicada es la unica activa; Gemma solo genera drafts.

#### Tareas

1. Implementar la logica real de `gap_penalty` donde hoy hay `pass`.
2. Penalizar explicitamente huecos de 1 noche; opcionalmente generalizar a fragmentacion corta.
3. Revisar el equilibrio entre:
   - `stability`
   - `prefer_exact_match`
   - `room_usage_penalty`
   - `fallback_priority_penalty`
   - `unassigned_penalty`
4. Mantener explicaciones y metricas persistidas en runtime.
5. Agregar tests de solver con escenarios controlados:
   - misma categoria multiples habitaciones,
   - upgrade fallback permitido,
   - habitacion en limpieza,
   - reserva larga vs reservas cortas,
   - hueco de 1 noche,
   - reserva locked.
6. Verificar que `rooms.py` al cambiar estado de cuarto siga pudiendo disparar realloc segura.

#### Validacion minima

1. Tests unitarios de solver.
2. Tests de runtime persistido.
3. Caso de reallocation por habitacion bloqueada/limpieza.

#### Criterio de cierre

- no queda `pass` en logica de fragmentacion;
- los resultados del solver son defendibles contra los casos de negocio basicos.

### A3. Exponer operaciones criticas en la UI del dueño

#### Objetivo

Que el dueño/front desk pueda operar sin ir a API manual ni a base de datos.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/views/protected/ReservationsPage.tsx`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/api/reservations.ts`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/hooks/useReservations.ts`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/views/protected/RoomsPage.tsx`

#### Decisiones obligatorias

1. Mantener `ReservationsPage` como centro operativo principal.
2. No abrir flujos complejos ocultos; toda accion critica debe quedar visible y auditable.
3. Mostrar siempre motivo/impacto antes de acciones irreversibles.

#### Tareas

1. Agregar botones y modales para:
   - mover reserva de habitacion,
   - preview y ejecucion de `rebook OTA -> direct`,
   - recalcular asignacion,
   - abrir detalle de corrida del motor,
   - bloquear o marcar para revision manual si aplica.
2. Mostrar en la ficha:
   - nombre real del huesped,
   - room move mas reciente,
   - conflicto OTA,
   - estado de settlement,
   - historial minimo de ajustes.
3. Reemplazar `Huesped #id` por nombre real en dashboard y reservas.
4. Mejorar la matriz `habitacion vs fechas`:
   - badges de OTA/directa,
   - sin asignar,
   - manual review,
   - check-in/check-out.
5. Agregar CTA visible para recalculo del motor y refresco de estado.

#### Validacion minima

1. Build frontend.
2. Smoke manual:
   - crear reserva,
   - abrir ficha,
   - mover habitacion,
   - ver pending actions,
   - rebook OTA -> direct,
   - recalcular asignacion.

#### Criterio de cierre

- el operador puede cerrar los casos criticos desde UI.

### A4. Cerrar gestion de huespedes y check-in base

#### Objetivo

Hacer que la base de pasajeros sea util y visible.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/api/guests.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/models/guest.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/api/guests.ts`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/hooks/useGuests.ts`
- nueva vista sugerida: `frontend/src/views/protected/GuestsPage.tsx`
- `frontend/src/router.tsx`

#### Decisiones obligatorias

1. Crear pantalla protegida dedicada a huespedes.
2. No depender solo del modal de reservas para gestionar pasajeros.
3. Mantener scoping por hotel y filtros de busqueda por:
   - nombre/apellido,
   - documento,
   - email.

#### Tareas

1. Crear `GuestsPage` con:
   - listado,
   - buscador,
   - apertura de ficha,
   - historial de reservas del huesped,
   - edicion de contacto/documentacion.
2. Mostrar companions o additional guests cuando existan.
3. Desde `ReservationsPage`, convertir el click del huesped en navegacion consistente o drawer mejorado.
4. Preparar la ficha para check-in legal:
   - documento,
   - nacionalidad,
   - fecha nacimiento,
   - telefono,
   - email,
   - observaciones.
5. No bloquear el piloto si OTA no envia todo: permitir completar manualmente.

#### Validacion minima

1. Crear/editar huesped.
2. Buscar por nombre/doc.
3. Abrir historial desde reserva.

#### Criterio de cierre

- el usuario puede acceder facilmente a la base de pasajeros.

### A5. Mejorar ingest OTA de pasajeros

#### Objetivo

Aprovechar mejor los datos OTA y dejar claro que lo faltante se completa manualmente.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota/contracts.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota/adapters/*.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/ota_service.py`

#### Tareas

1. Extender contrato normalizado si el payload OTA trae:
   - telefono,
   - nacionalidad,
   - observaciones,
   - roster,
   - horario llegada.
2. Persistir lo disponible sin inventar.
3. Si faltan datos requeridos para check-in, marcar estado claro en UI de huesped/reserva.

#### Criterio de cierre

- la reserva OTA entra con toda la informacion realmente disponible, y lo faltante queda visible para completar.

---

## Fase B - Hardening del piloto

Objetivo: dejar el sistema suficientemente confiable y operable para probarlo con un hotel real.

### B1. Cerrar el loop Gemma -> feedback -> draft

#### Objetivo

Que Gemma ayude operativamente y aprenda del negocio sin salirse de control.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/gemma_orchestrator.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/gemma_context_service.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/allocation_learning_service.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/frontend/src/views/protected/SettingsAssistantPage.tsx`

#### Decisiones obligatorias

1. Gemma nunca autoaplica politica publicada.
2. Todo cambio generado por Gemma pasa por draft -> review -> apply.
3. Todo feedback operativo relevante debe poder capturarse desde UI.

#### Tareas

1. Agregar desde UI captura de motivos cuando el usuario:
   - mueve habitacion,
   - rechaza asignacion,
   - rebookea OTA -> directa,
   - corrige decision del sistema.
2. Exponer esos motivos a Gemma como feedback estructurado, no como texto suelto opaco.
3. Mejorar pantalla de Gemma para mostrar:
   - insights,
   - drafts,
   - status de runtime,
   - feedback reciente usado para sugerencias.
4. Mantener redaccion de PII.

#### Criterio de cierre

- Gemma ya participa de la operacion de forma visible y auditada.

### B2. Correr Gemma local real

#### Objetivo

Pasar del fallback al runtime local en la maquina de prueba.

#### Archivos base

- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/services/gemma_orchestrator.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/app/scripts/mock_gemma_runtime.py`
- `C:/Users/macap/OneDrive/Escritorio/Hotel-Chipre-Reservas/Hotel-Chipre-PMS/docs/gemma4/local-runtime-testing.md`

#### Tareas

1. Levantar runtime local OpenAI-compatible real.
2. Configurar:
   - `GEMMA_ENABLED=true`
   - `GEMMA_PROVIDER=openai_compatible`
   - `GEMMA_ENDPOINT_URL=...`
   - `GEMMA_MODEL=...`
3. Verificar `GET /api/gemma/chat/runtime-status -> ready`.
4. Hacer smoke test desde UI y API.

#### Criterio de cierre

- Gemma responde con runtime real y no solo con fallback.

### B3. QA de piloto

#### Objetivo

Eliminar roturas gruesas antes del hotel real.

#### Tareas

1. Armar matriz de smoke tests:
   - login,
   - crear reserva directa,
   - OTA nueva/modificada/cancelada,
   - room move,
   - rebook OTA->direct,
   - recalculo solver,
   - guest editing,
   - pago y saldo,
   - Gemma draft.
2. Agregar tests faltantes backend/frontend segun los cambios.
3. Confirmar:
   - `pytest`
   - `npm run build`
   - mocks o fixtures de OTA y Gemma.

#### Criterio de cierre

- hay checklist repetible para piloto.

### B4. Documentacion operativa de piloto

#### Objetivo

Reducir improvisacion durante la prueba real.

#### Tareas

1. Crear runbook corto:
   - como conectar canales,
   - como resolver manual review,
   - como mover una reserva,
   - como rebookear OTA->direct,
   - como revisar Gemma,
   - que hacer ante conflicto.
2. Crear checklist diaria del piloto.

#### Criterio de cierre

- un operador nuevo puede seguir el flujo sin leer codigo.

---

## Fase C - Ejecucion del piloto real

Objetivo: operar un hotel real, capturar feedback y no perder control del dominio.

### C1. Preparar entorno de piloto

#### Tareas

1. Crear entorno de piloto separado del desarrollo.
2. Ejecutar migraciones.
3. Cargar configuracion inicial del hotel:
   - habitaciones,
   - categorias,
   - productos,
   - tarifas,
   - mappings OTA,
   - Gmail.
4. Ejecutar smoke completo antes de abrir uso real.

### C2. Ejecutar piloto

#### Reglas

1. Toda anomalia se registra dentro del sistema o en doc de feedback del piloto.
2. No hacer correcciones por base de datos salvo emergencia.
3. Si aparece un caso ambiguo, preferir manual review y documentar.

### C3. Capturar feedback del hotel

#### Tareas

1. Registrar feedback funcional por categoria:
   - OTA,
   - motor,
   - visualizacion,
   - huespedes,
   - pagos,
   - Gemma.
2. Separar:
   - bug,
   - mejora,
   - regla de negocio nueva.
3. Convertir correcciones operativas del piloto en:
   - cambios de producto,
   - ajustes de politica,
   - backlog post-piloto.

### Criterio de cierre de la fase C

- el hotel pudo operar con el PMS;
- el feedback esta capturado y priorizado;
- no quedaron fallas P0 abiertas.

---

## Fase D - Cierre para salida publica

Objetivo: transformar el piloto exitoso en producto cobrable.

### D1. Completar integraciones OTA y channel manager

#### Objetivo

Pasar de inbound util a integracion comercial completa.

#### Tareas

1. Implementar outbound por provider:
   - inventory,
   - rates,
   - restrictions,
   - cancel,
   - modify,
   - reconcile.
2. Implementar reglas por canal sobre las tablas ya existentes:
   - `ota_inventory_rules`
   - `ota_price_rules`
   - `ota_cancellation_rules`
3. Crear UX para editar esas reglas.

### D2. Seguridad, despliegue y operacion

#### Tareas

1. Definir entornos:
   - local,
   - staging,
   - production.
2. Cerrar secretos y configuracion por entorno.
3. Agregar backups y restore probado.
4. Agregar observabilidad minima:
   - errores backend,
   - fallos OTA,
   - fallos solver,
   - fallos Gemma.
5. Agregar checklist de deploy y rollback.

### D3. UX final y onboarding

#### Tareas

1. Pulir textos de producto y errores.
2. Completar onboarding de hotel.
3. Completar onboarding de conexiones.
4. Crear documentacion corta orientada a cliente.

### D4. Go-live review

#### Gate obligatorio

No lanzar si cualquiera de estas falla:

1. smoke tests en staging;
2. backups/restore no probados;
3. OTA outbound no estable;
4. motor con fallas P0;
5. UX critica con IDs o datos opacos;
6. Gemma o integraciones sin aislamiento correcto por hotel.

---

## Instrucciones de ejecucion para un modelo mas chico

### Modo de trabajo

1. Ejecutar una tarea a la vez, en el orden del plan.
2. Al empezar cada sub-bloque:
   - releer solo los archivos listados,
   - no reanalizar todo el repo.
3. Al terminar cada sub-bloque:
   - correr tests puntuales,
   - si pasan, correr suite completa y build.
4. Si un bloque abre trabajo no planificado, no desviarse; anotar y seguir.

### Cuándo SI preguntar al usuario

Solo preguntar si hace falta:

1. credencial externa real,
2. decision comercial que cambie facturacion real y no este ya definida,
3. dato especifico del hotel piloto,
4. aprobacion para usar infraestructura externa no prevista.

### Cuándo NO preguntar

No preguntar por:

1. naming interno,
2. pequeñas decisiones de UI,
3. refactors de soporte,
4. estructura de tests,
5. redaccion de docs tecnicas.

### Criterio de seguridad operativa

Si aparece una situacion ambigua:

1. no sobreescribir datos,
2. no cancelar de forma irreversible,
3. no publicar politica automaticamente,
4. abrir accion pendiente o `manual_review`.

## Checklist minimo de salida de cada bloque

1. Codigo implementado.
2. Tests nuevos agregados.
3. `python -m pytest -q` en verde.
4. `npm run build` en verde si hubo cambios frontend.
5. Nota breve:
   - que quedo hecho,
   - que falta del siguiente bloque,
   - si existe algun riesgo residual.

## Resumen ejecutivo final

El orden correcto es:

1. OTA inbound lifecycle
2. solver con fragmentacion real
3. UX operativa del dueno
4. huespedes y check-in base
5. Gemma + feedback loop + runtime real
6. QA + runbooks
7. piloto real
8. outbound OTA y hardening de produccion
9. go-live

No comprimir etapas criticas del dominio para acelerar. Acelerar aca sin cerrar OTA, motor y UX operativa rompe el piloto.
