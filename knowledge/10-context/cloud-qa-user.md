---
scope: QA manual visible en Render producción sobre el hotel de prueba autorizado
owner: cloud-qa-user
last_verified_commit: 42dd238
canonical_sources: [knowledge/30-operations/cloud-regression-catalog.md, knowledge/30-operations/qa-personas-and-bootstrap.md, qa/regression-catalog.json]
consumers: [cloud-qa-user, qa-testing]
graphify_minimum: graphify affected-flows --files frontend/src/router.tsx
required_validation: matriz funcional con personas autorizadas y evidencia posterior a code_sha
---
# Context pack — QA de Render producción usuario real

Abrir únicamente `https://app.hotels-pms.com` después de confirmar que el workflow `Production Render QA cycle` verificó el SHA live. Navegar UI visible, con selectores accesibles, capturas/trazas/video sólo en fallos y evidencia no sensible en `qa/operational/runs/<run-id>/`.

Usar sólo el hotel de prueba autorizado y datos sintéticos/reversibles. Un fallo, permiso incorrecto, perfil inseguro o superficie inaccesible bloquea la tarea. No acceder al correo ni ejecutar pagos reales, envíos, webhooks u OTAs.
