# Implementación de remediación del PMS — 2026-09-10

Esta rama implementa la primera etapa de corrección de la auditoría de uso del PMS y deja preparadas las piezas internas de la segunda etapa. El cambio no constituye una certificación de release ni habilita por sí solo proveedores externos.

## Alcance implementado

- Las reservas y comprobantes muestran número de habitación y nombre de categoría. Los identificadores internos permanecen para relaciones y filtros.
- El resumen diario de caja usa el huso horario del hotel, incluye el arrastre real de un turno que atraviesa medianoche y separa monedas, efectivo, pagos digitales y movimientos manuales. También permite exportar el libro existente a CSV.
- El Dashboard consulta en servidor las próximas cinco llegadas y los estados de acciones pendientes distinguen error, carga y ausencia real.
- Acceso, verificación de correo, restablecimiento de contraseña y navegación móvil tienen validación, foco, Escape, mensajes en español y estados accesibles. No se muestran códigos de demostración.
- El asistente de puesta en marcha expone un checklist calculado con categorías, habitaciones, tarifas, políticas, medios de cobro, personal activo y primera reserva opcional. Cada enlace apunta a una ruta real.
- Se agregaron tareas operativas con historial, prioridad, vencimiento, contexto de habitación/bloqueo, versiones para conflictos y pases de turno. Un pase puede referenciar el último arqueo sin crear un saldo nuevo.
- El cierre de un bloqueo comprueba estado vendible, bloqueos superpuestos, reservas afectadas e incidencias de mantenimiento abiertas. Resolver la incidencia no libera automáticamente la habitación.
- Las comunicaciones de confirmación y comprobante tienen historial, deduplicación, estados de aceptación/fracaso/resultado desconocido y reenvío explícito.

## Integraciones

Booking y Mercado Pago quedan detrás de sus conexiones por hotel, con credenciales aisladas, deduplicación y errores recuperables. Booking sigue pendiente de cuenta Connectivity, alojamiento de prueba, mapeos y certificación del proveedor. Mercado Pago no se probó con dinero real ni se ejecutaron notificaciones reales en esta rama. La conexión o sincronización externa debe activarse de forma explícita por entorno y hotel.

## Migraciones y reversión

Las tablas de tareas, pases y entregas de correo son aditivas y tienen políticas RLS en PostgreSQL. Las dos migraciones nuevas se probaron en SQLite con `upgrade`, `downgrade` hasta la revisión anterior y `upgrade` nuevamente. La reversión funcional recomendada es desactivar permisos o la conexión del hotel; los registros se conservan.

## Verificación

- Backend: `1966 passed, 26 skipped, 12 xfailed, 1 xpassed` en la regresión completa.
- Frontend: i18n, TypeScript, ESLint, build Vite, PWA y metadatos de build aprobados.
- Se conservaron advertencias existentes de `pytest-asyncio`, solapamientos de relaciones SQLAlchemy y compatibilidad de TypeScript de ESLint; no cambian el resultado de las pruebas.
