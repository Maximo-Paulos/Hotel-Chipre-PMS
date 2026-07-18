# API e integraciones

Estado: `confirmed` para routers registrados y OpenAPI generado.

`app/main.py` construye la aplicación FastAPI, valida seguridad runtime al iniciar y registra routers para operación central, auth/invitaciones, pagos/links/surcharges, API keys y booking público, integraciones/OTAs/WhatsApp, analítica/Gemma y master-admin. El contrato reproducible está en [OpenAPI](../_generated/api-surface.md).

Las rutas `/api/connections` y `/api/email` se conservan como respuestas 410 de compatibilidad. Las integraciones deben estar encapsuladas, configurables y ser mockeables; webhooks verifican firma y los efectos externos se prueban por contrato en lugar de ejecutarse durante QA.
