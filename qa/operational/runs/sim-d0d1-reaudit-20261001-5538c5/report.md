# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

- Run: `sim-d0d1-reaudit-20261001-5538c5`
- Inicio: 2026-10-01T15:27:03-03:00
- Código observado: `377196c6ba076e14525c5bd79edfec7eab1f1c46`
- Superficie: Chrome visible, `https://app.hotels-pms.com`
- Alcance: reauditoría operativa de los hallazgos de D0 y D1; propietario, gerencia y recepción; pruebas adicionales de housekeeping/codueño sólo si hay una sesión real disponible.
- Marcador de datos sintéticos: `sim-d0d1-reaudit-20261001-5538c5`
- Límites: no modificar reservas preexistentes; no enviar correo, no usar pasarelas, no transferir dinero, no disparar webhooks ni sincronización OTA. Los registros nuevos, si se pueden aislar, se etiquetarán con el marcador anterior.
- Estado inicial: PostgreSQL saludable; Redis con error mientras bloqueos distribuidos y tiempo real figuran requeridos.

## Matriz de recorrido

| Área | Rol | Estado | Evidencia breve |
|---|---|---|---|
| Sesiones y permisos | owner / manager / reception | EN CURSO | Identidades comprobadas en UI; recorrido pendiente. |
| Reservas directas, futuras, Booking, Expedia y empresa | manager / reception | PENDIENTE | Sólo registros sintéticos y manuales; ningún canal externo. |
| Cotización con tarifa vigente | manager | FAIL | La pantalla de Tarifas muestra precio para la categoría/noches consultadas; el formulario recibe HTTP 400 `No active prices found for rate plan`, deshabilita Crear y no permite continuar. No se creó reserva. |
| Monedas, método de pago y precio | owner / manager / reception | PENDIENTE | Verificar cotizaciones y estado; no realizar transacción externa. |
| Movimiento manual y motor de asignación | manager / reception | PENDIENTE | Primero sólo sobre reservas sintéticas. |
| Caja, custodia y arqueo | reception / manager / owner | PENDIENTE | Revisar caja abierta antes de cualquier escritura; Redis degradado es riesgo. |
| Limpieza y planilla | housekeeping / manager / reception | PENDIENTE | No cambiar estado de habitación ocupada ni reserva ajena. |
| Hallazgos F-001–F-053 | roles por superficie | PENDIENTE | Clasificar PASS / FAIL / BLOCKED / NOT_APPLICABLE con evidencia visible. |

## Hallazgos observados antes de mutar

- Redis está desconectado; no se han realizado escrituras de reserva, caja o habitación en esta corrida.
- Se observan registros sintéticos de corridas anteriores en el hotel; se dejan intactos.

## Criterios de producto confirmados durante la auditoría

- En una reserva de empresa, el importe base contratado puede seguir correspondiendo a una habitación doble aunque el huésped llegue con una persona adicional. La operación debe permitir asignar una habitación con capacidad suficiente y registrar el adicional por separado, por persona y noche; cambiar la habitación no debe recalcular ni sustituir la tarifa base contratada.
- El precio unitario del adicional por persona y noche puede cambiar con fecha de vigencia. La cantidad de personas adicionales debe multiplicar el cargo unitario. Un cambio de tarifa no modifica cargos ya generados de forma automática; solo se corrigen cargos anteriores si personal autorizado selecciona explícitamente las noches a editar. En ese caso se registra el ajuste auditado con importe previo/nuevo y diferencia, sin alterar cobros ni asignaciones existentes, incluso si la noche está pagada o parcialmente pagada.
- Crear o editar la cuenta de empresa y la configuración de sus reservas corresponde a Dueño, Codueña y Gerencia, además de cualquier usuario con permiso explícito. Recepción sí puede hacer las operaciones de estadía (incluido check-in/check-out y completar los datos del huésped) y registrar por defecto el pago del adicional contra las noches elegidas, pero no editar empresa, fechas, ocupación, tarifa base o habitación de esa reserva.
- Por ahora, Booking/Expedia/Despegar se cargan manualmente como reservas normales, identificando el canal y el precio informado; no se conecta ni sincroniza una OTA. Si una OTA ya pagó, el usuario puede registrar el importe conocido como pago externo para el saldo/ingreso de la reserva, pero no debe aparecer como efectivo o dinero recibido por el hotel. Los cargos/comisiones de OTA quedan fuera del registro de caja del PMS; el hotel registra el importe bruto del dinero que efectivamente recibe y mantiene el pago externo en una sección separada.
- En empresas con pago diferido, el alojamiento puede facturarse fuera del PMS. El cargo por persona adicional queda aparte y es el único componente que se cobra dentro del PMS durante la estadía: Recepción puede elegir las noches pagadas, y noches futuras no abonadas quedan como pendiente de revisión. No se debe mostrar ese pago del adicional como si cubriera la factura de alojamiento de la empresa.
- El catálogo y la venta de minibar quedan para una iteración futura; el stock actual es control interno. Los precios de planes de la app también quedan pendientes hasta terminar el producto o cargar el motor de pagos. Si se implementan códigos de descuento o regalos de suscripción, solo Dueño puede concederlos. Las imágenes cifradas de documentos de huéspedes se consideran trabajo futuro.
- Dueño y Codueña deben compartir accesos administrativos por defecto. En la matriz visible la Codueña sí tiene Usuarios, Suscripción, Seguridad de lectura y Permisos, pero no tiene cinco acciones administrativas que sí están disponibles para Dueño: override de tarifa manual, configuración del rango de tarifa manual, corrección del total pagado, administración de API keys y manejo de secretos/conexiones de seguridad. Mantener la transferencia/cambio de titularidad como acción exclusiva del Dueño por su impacto de propiedad; las acciones sensibles compartidas conservan MFA/step-up.

### Criterios de aceptación para cerrar el hallazgo de empresa

- Una reserva contratada como doble conserva esa categoría y su importe base aunque, al llegar tres personas, se asigne a una habitación física triple. La factura/contrato base de la empresa sigue reflejando la doble; cada persona que exceda la ocupación contratada genera su adicional por noche y no se convierte en una tarifa triple.
- El adicional se calcula por cada persona y noche cubierta y permite seleccionar qué noches se pagan. El cambio de precio guarda una fecha efectiva; cargos nuevos para noches desde esa fecha toman el precio vigente para cada noche. Los cargos ya generados permanecen como están salvo edición puntual de noches seleccionadas por personal autorizado; la corrección debe conservar valor anterior, nuevo, diferencia, actor y motivo en una auditoría/ajuste, sin sobrescribir transacciones ni sus asignaciones.
- Dueño, Codueña y Gerencia pueden gestionar empresa y los datos de reserva por defecto. Otros usuarios solo pueden hacerlo con permisos explícitos. Recepción puede completar datos del huésped, ejecutar operaciones de estadía y registrar por defecto el pago del adicional en noches seleccionadas; esos permisos operativos no conceden creación/edición de empresas, cambios de fechas/ocupación/tarifa/habitación ni ajustes de capacidad.
- `Reservation.category_id` conserva la categoría vendida/contratada y `room_id -> Room.category_id` identifica la categoría física. El movimiento debe mantenerlos separados. La auditoría confirmó que no hace falta duplicar la categoría contratada en una columna nueva; sí hay que corregir mutaciones que sobrescriben el campo vendido y consumidores que lo usan como categoría física.

## Brechas confirmadas por inspección de código

- La pantalla de empresas y el modelo `Company` guardan un único `extra_person_nightly_surcharge`, sin fecha desde la que rige cada precio. `add_company_night_charges` toma el precio actual al generar cargos, sin seleccionar una tarifa histórica por fecha de estadía. Además, crea exactamente un cargo fijo por reserva/noche y no representa cuántas personas adicionales se cobran. Se necesita tarifa efectiva por fecha más cantidad y precio unitario snapshot en el cargo; el backfill solo puede iniciar desde la fecha de corte, porque el historial anterior no existe. El cambio de tarifa no debe tocar cargos emitidos; una edición manual exige noches seleccionadas, importe previo/nuevo y diferencia auditable, y nunca reescribe pagos.
- `Reservation.category_id` representa la categoría vendida/contratada y `room_id` enlaza la habitación física. Los movimientos manuales y grupales sobrescriben hoy `category_id` con la categoría del cuarto destino. El movimiento manual puede además cotizar/reemplazar el importe base como categoría nueva. La corrección debe conservar categoría e importe base de la empresa, validar capacidad según el cuarto físico y añadir el cargo extra por separado.
- La ruta de movimiento manual autoriza por permisos de movimiento de habitación, pero no agrega una comprobación de `company:manage` cuando la reserva pertenece a una empresa. Recepción no tiene permiso de cambio de capacidad por defecto; aun así, una concesión de movimiento independiente no debe habilitar cambios de reservas empresariales sin autorización de empresa.
- Recepción carece de `company:manage` por defecto; el cargo empresarial se crea bajo ese permiso. Las rutas de cobro permiten asignar pagos a cargos seleccionados, sujeto al permiso de cobro. Esto coincide con la separación pedida: personal autorizado prepara el adicional; Recepción puede cobrarlo sin administrar la cuenta.
- La reconsulta visible de una reserva del 20 al 22/10/2026 en la categoría Doble Baño Compartido falló: `GET /api/bookings/price-quote?category_id=5&check_in_date=2026-10-20&check_out_date=2026-10-22&occupancy=1` respondió HTTP 400 con `No active prices found for rate plan`. En Tarifas el dueño ve valores cargados para esa misma categoría y noches. El usuario ve “No hay una tarifa disponible”; `Crear` queda deshabilitado. El formulario fue cerrado sin guardar y no se modificó ningún registro. La causa quedó confirmada por inspección: la cotización infiere un único plan comercial y su ruta estricta oculta el resolver diario (DailyRate/PricePeriod/categoría) que alimenta Tarifas. En el worktree se agregó un fallback solo cuando plan/producto/impuesto no fueron seleccionados explícitamente; la regresión focalizada y el contrato completo de cotización pasan localmente (7 tests). Aún no está desplegado ni revalidado en nube.

## Resultados

Auditoría parcial. Hay tres recorridos visibles PASS (sesión de Gerencia, denegación de Empresas para Recepción y lectura de suscripción/configuración monetaria), fallos confirmados en el adicional/upgrade de empresa (fecha efectiva, conteo por personas, categoría contratada y permisos), en la cotización, y en cinco permisos administrativos que el Owner-visible matrix niega a Co-owner pese a la política confirmada. También hay casos BLOCKED por preservar datos compartidos (caja preexistente y MFA activa sin una cuenta de prueba desactivada). El formulario de cotización falló en la app desplegada con HTTP 400; el parche local pasó 7 pruebas de contrato de cotización. El resto de F-001–F-053 sigue sin cierre de reauditoría y release.

La ruta Owner de Permisos presentó un desafío MFA; después de completar step-up, la matriz quedó visible y se registró una comparación de roles solo lectura. La Mac ya está desbloqueada. No se ingresó ni persistió ningún código en el run.
