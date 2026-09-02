---
name: deploy-preview-check
description: Comprueba que Render producción esté desplegando el backend correcto.
---

# deploy-preview-check

Antes de QA cloud, verifica el manifiesto de Render producción, el health del backend, `APP_BASE_URL`, `FRONTEND_URL`, CORS, Redis y el SHA live exacto.

Lee `knowledge/20-system/cloud-and-deployment.md` y `knowledge/30-operations/cloud-surface-manifest.md`. Si el perfil seguro o el SHA live no coinciden, bloquea la prueba y no muta la infraestructura.

No despliegues, rotes secretos ni modifiques proveedores desde esta skill.
