---
scope: definición de terminado, evidencia, gates y entrega
owner: release-governor
last_verified_commit: bf14bf5
canonical_sources: [knowledge/40-delivery/release-gates.md, knowledge/40-delivery/qa-evidence-template.md, qa/evidence/]
graphify_minimum: graphify check-update .
required_validation: validación local y ciclo de QA funcional sobre Render producción posterior al merge
---
# Context pack — Release governor

No se cierra una tarea funcional sin validación local, revisión de seguridad y QA cloud funcional sobre Render producción posterior al merge, con el hotel de prueba autorizado y el SHA live verificado. Pagos reales, emails, webhooks, OTAs y carga destructiva quedan explícitamente fuera.
