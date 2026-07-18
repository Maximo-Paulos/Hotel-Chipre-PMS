---
name: deploy-preview-check
description: Comprueba que un preview sea aislado y apunte al backend correcto.
---

# deploy-preview-check

Antes de QA cloud, verifica manifest de preview, health del backend, `VITE_API_URL`, `FRONTEND_URL`, CORS y que cada preview use su `DATABASE_URL`/secrets QA aislados.

Lee `knowledge/20-system/cloud-and-deployment.md` y `knowledge/30-operations/cloud-surface-manifest.md`. Si Supabase Branches no está disponible, bloquea el preview y solicita una segunda base aislada.

No despliegues, rotes secretos ni modifiques proveedores desde esta skill.
