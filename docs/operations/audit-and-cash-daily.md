# Auditoría operativa y caja diaria

## Traslado de habitación

Un traslado de una reserva futura modifica la asignación de la reserva y se
refleja en `Habitaciones`, pero no cambia el estado físico de las habitaciones.
Una reserva alojada sí modifica el estado físico: la habitación destino queda
ocupada y recepción debe decidir si la habitación origen queda en `Limpieza`,
`Libre` o `Mantenimiento`. La decisión debe ser explícita; si no se elige
`Limpieza`, la justificación es obligatoria.

El movimiento guarda reserva, origen, destino, motivo, nota, actor, fecha,
decisión y estados físico previo/posterior. El traslado, su evento, los cambios
de habitación y la auditoría de la reserva se confirman en la misma transacción.
Los movimientos históricos conservan sus campos nuevos en `NULL` cuando no
existía ese dato.

## Auditoría integral

La vista `/operacion/auditoria` y `GET /api/operations/audit` son de lectura y
requieren `operations:audit:view`, otorgado por defecto sólo a owner y
co-owner. La proyección combina los ledgers append-only existentes:

- mutaciones de filas (`audit_logs`);
- eventos de negocio y seguridad;
- movimientos de habitación y cambios de estado de reservas;
- transacciones de pago, ajustes de facturación y movimientos de caja;
- apertura, arqueo, diferencias y custodia de caja.

No se crea un segundo ledger financiero. La consulta está aislada por hotel,
paginada y admite filtros por fecha local, usuario, área, reserva, habitación y
acción. Las áreas normalizadas incluyen reservas, habitaciones, pagos, caja,
huéspedes, inventario, lavandería, comercial, usuarios, permisos,
configuración y seguridad. Los payloads sensibles continúan redactados.

## Caja diaria

`GET /api/cash-register/daily-summary?date=YYYY-MM-DD` usa el día calendario
del huso horario configurado en el hotel. Incluye únicamente transacciones
completadas; pendientes y fallidas quedan fuera, las devoluciones restan y una
operación sin actor humano se muestra como `Sistema/Proveedor`.

El resumen separa cobros por medio y cobrador de la caja física. La caja física
se calcula con apertura, ingresos/egresos manuales, cobros de efectivo,
ajustes, esperado, arqueo y diferencia; tarjetas, transferencias, Mercado Pago,
PayPal y otros medios no inflan el efectivo. La pantalla `/caja` conserva las
mutaciones protegidas por `cash:operate` y permite el consolidado de lectura a
los roles con `cash:view`.

Al cerrar un turno, `Saldo contado` registra todo el efectivo físico del cajón.
El cierre guarda el saldo esperado, el contado, la diferencia, las notas, el
autor y la hora. La caja sucesora comienza en cero. Al recibir la custodia,
Dueño o Codueña puede declarar por separado el efectivo que deja como fondo de
cambio; ese importe se limita a lo entregado y queda registrado como apertura
de la caja sucesora. La aprobación de una diferencia y la recepción de
custodia son decisiones independientes.

Los gastos manuales se cargan con categoría, proveedor y referencia o imagen
privada del comprobante. Cargar un gasto lo deja pendiente y no reduce el
saldo esperado. Dueño, Codueña y Gerencia pueden registrarlo y aprobarlo; la
aprobación o rechazo requiere MFA y queda auditado. Recepción solo puede
cargarlo si tiene `cash:expense` otorgado explícitamente; el gasto queda
pendiente hasta su aprobación.

La exportación CSV admite rangos de fechas locales del hotel. Usa encabezados
en español, punto y coma, codificación UTF-8 con BOM y coma decimal para abrir
en Excel con configuración es-AR; los textos que podrían interpretarse como
fórmulas se exportan como texto. Los cobros de un mismo lote grupal aparecen
como una sola línea en el registro de caja.

Los timestamps operativos almacenados como UTC se exponen con zona explícita en
las respuestas de caja y pagos. La interfaz interpreta como UTC los timestamps
legados sin sufijo y los muestra en el huso horario configurado en el hotel, con
reloj de 24 horas; las fechas de calendario no pasan por esa conversión.
