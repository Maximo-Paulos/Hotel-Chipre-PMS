---
name: secure-integration-review
description: Revisa límites de seguridad de integraciones externas.
---

# secure-integration-review

Traza autenticación, autorización, validación, secretos, webhooks, reintentos, PII y efectos externos en el cambio propuesto.

Exige configuración por entorno, verificación de firmas, logs redactados y pruebas de denegación. Evalúa pagos, OTAs, email y APIs de terceros con `knowledge/10-context/security.md`.

No pruebes pagos reales ni ejecutes efectos externos; documenta contratos o adapters usados.
