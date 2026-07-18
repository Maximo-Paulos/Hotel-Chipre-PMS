---
scope: QA manual visible en previews cloud con personas sintéticas
owner: cloud-qa-user
last_verified_commit: 50abb05
canonical_sources: [knowledge/30-operations/cloud-regression-catalog.md, knowledge/30-operations/qa-personas-and-bootstrap.md, qa/regression-catalog.json]
graphify_minimum: graphify affected-flows frontend/src/router.tsx
required_validation: matriz completa de cinco personas con evidencia posterior a code_sha
---
# Context pack — Cloud QA usuario real

Abrir únicamente la URL de preview consignada en el manifiesto y usar `.env.qa.local` ignorado. Navegar UI visible, con selectores accesibles, capturas/trazas/video sólo en fallos y evidencia no sensible en `qa/evidence/<task-id>/`.

Un fallo, permiso incorrecto o superficie inaccesible bloquea la tarea. No acceder al correo ni ejecutar pagos, envíos, webhooks u OTAs.
