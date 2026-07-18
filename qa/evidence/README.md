# Evidencia QA versionable

Crear un directorio por tarea con `summary.json` siguiendo `knowledge/40-delivery/qa-evidence-template.md`. Sólo se versionan resultados redactados y hashes de artefactos. Screenshots, trazas, videos, perfiles y sesiones van a `artifacts/qa/` (ignorado).

Validar con:

```bash
.venv/bin/python scripts/agent_ops/check_qa_evidence.py qa/evidence/<task-id>/summary.json
```
