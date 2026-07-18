# Producto y personas

Estado: `confirmed` para superficies declaradas; cobertura funcional detallada se verifica mediante catálogo QA.

Hotel Chipre PMS centraliza operación de hotel: huéspedes, reservas, asignación/habitaciones, check-in/out, caja y pagos, reportes, configuración, integraciones, analítica y administración de plataforma. La interfaz separa marketing público de operación en host de aplicación.

Personas operativas que deben conservar permisos y recorridos diferenciados:

- **Owner**: configura hotel, usuarios, integraciones, suscripción y revisa el negocio.
- **Manager**: dirige operaciones, reservas, reportes y excepciones autorizadas.
- **Recepción**: atiende huéspedes, reserva, check-in/out y caja según permisos.
- **Housekeeping**: consulta/actualiza operación de habitaciones y tareas autorizadas.
- **Master-admin**: administra la plataforma en `/adminpmsmaster`, separado de los hoteles.

La IA sólo debe recomendar y explicar: no puede mutar reservas, precios o asignaciones críticas sin flujo explícito, autorización y auditoría.
