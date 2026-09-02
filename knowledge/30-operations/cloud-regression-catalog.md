# Catálogos de regresión cloud

La fuente machine-readable es `qa/regression-catalog.json`, esquema v2. Sus
45 casos forman 173 combinaciones caso/persona y 335 combinaciones
caso/persona/dispositivo. La campaña funcional se ejecuta sobre el frontend y
backend desplegados en Render producción, usando el hotel de prueba autorizado y
datos sintéticos/reversibles.

La campaña sobre los dominios compartidos usa un catálogo separado:
`qa/operational/shared-sandbox-catalog.json`. Sus ejecuciones viven en
`qa/operational/runs/<run-id>/` con artefactos bajo
`artifacts/qa-operational/<run-id>/`. Son evidencia operativa no certificante y el
release gate formal debe rechazarlas.

Cobertura mínima obligatoria:

- Marketing: home, precios, funciones, SEO routes, responsive y redirecciones.
- Auth: registro/login, reset/verify como contrato sin acceso a buzón, invitación y errores.
- Onboarding/operación: dashboard, huéspedes, reservas, habitaciones, caja, reportes, lista de espera, lavandería, stock y tarifas.
- Analytics/settings: analítica, filtros, empresas, usuarios, roles, API keys, conexiones, seguridad, suscripción y asistente.
- Master-admin: login, dashboard, billing, email, stripe y auditoría con identidad separada.
- Flujos públicos con API key: contrato, autorización y errores; no exponer keys en evidencia.

Cada fila se registra por persona y dispositivo con URL canónica,
precondición, acción humana, esperado, observado, evidencia y `code_sha`. Un fallo,
una exclusión no declarada o evidencia incompleta bloquea el cierre funcional.

Las 99 observaciones heredadas se conservan como historia no certificada bajo
`qa/history/observations/`; no forman parte del catálogo normativo.
