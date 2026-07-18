# Catálogo de regresión cloud

La fuente machine-readable es `qa/regression-catalog.json`. Este catálogo se ejecuta sobre el par frontend/backend del mismo preview y contra una Supabase Branch aislada.

Cobertura mínima obligatoria:

- Marketing: home, precios, funciones, SEO routes, responsive y redirecciones.
- Auth: registro/login, reset/verify como contrato sin acceso a buzón, invitación y errores.
- Onboarding/operación: dashboard, huéspedes, reservas, habitaciones, caja, reportes, lista de espera, lavandería, stock y tarifas.
- Analytics/settings: analítica, filtros, empresas, usuarios, roles, API keys, conexiones, seguridad, suscripción y asistente.
- Master-admin: login, dashboard, billing, email, stripe y auditoría con identidad separada.
- Flujos públicos con API key: contrato, autorización y errores; no exponer keys en evidencia.

Cada fila se registra con persona, URL preview, precondición, acción humana, esperado, observado, evidencia y `code_sha`. Un fallo, una exclusión no declarada o evidencia incompleta bloquea el cierre.
