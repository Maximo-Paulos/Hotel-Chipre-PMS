# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Estado

Ejecución parcial de la matriz de 45 casos. Se registraron cuatro fallas reproducidas en la aplicación vigente. Se usaron las sesiones reales de Dueño, Gerencia y Recepción; no se contó con sesiones reales de Copropietario ni Limpieza. El SHA desplegado no fue verificado independientemente y no se ejecutó QA en un preview aislado. Esta corrida no certifica un release.

## Fallas observadas en la base de esta corrida

- **Empresas (Gerencia):** la pantalla mostró `Empresas (0)` junto con `Error interno del servidor`; el formulario cargó.
- **Cotizaciones (Dueño):** Configuración del hotel mostró que la cotización oficial no estaba disponible y que no pudo refrescar las cotizaciones.
- **Reserva OTA (Recepción):** el listado mostró habitación 115, pero la ficha quedó sin habitación y con asignación `unassigned`. Reserva sintética `RES-SW91YMVY`, sin pago.
- **Cambio de habitación (Recepción):** el servidor confirmó el cambio, pero la interfaz siguió en `Moviendo…` por más de 12 segundos mientras actualizaba consultas dependientes; se observó dos veces.

## Parches locales preparados

En el branch de trabajo hay cambios para persistir el estado de asignación correcto, actualizar inmediatamente la reserva al confirmar un cambio de habitación y hacer su refresco secundario en segundo plano, y permitir únicamente lecturas públicas de DolarAPI con una configuración separada de pagos, correo y OTAs. La validación local de esos cambios pasó: suite backend completa (2.702 passed, 31 skipped, 12 xfailed), lint, typecheck, tests y build frontend, además de Playwright focal con las lecturas secundarias demoradas. Aún no hay verificación de estos parches en la aplicación desplegada.

El error de Empresas sigue sin causa raíz confirmada ni parche. Hace falta reproducirlo con el esquema/runtime desplegado o disponer de trazas seguras del backend.

## Efectos externos y cobertura

No se completaron pagos, envíos de correo, webhooks ni sincronizaciones OTA. Se retuvo la reserva OTA sintética para reproducción. No se probó Copropietario ni Limpieza con identidad propia. El archivo `run-metadata.json` conserva `release_gate_eligible: false` y `certification: none`.
