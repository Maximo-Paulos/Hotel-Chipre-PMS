---
name: graphify-write
description: Actualiza y verifica Graphify después de cambios de código.
---

# graphify-write

Úsala después de modificar archivos de código, migraciones o rutas relevantes.

Ejecuta `graphify update . --scope all --no-description --no-label`, `graphify flows build`, `.venv/bin/python scripts/agent_ops/normalize_graphify_portability.py`, `graphify portable-check` y `graphify check-update`. Registra el resultado y el commit en el handoff o context pack afectado.

`.graphify/graph.json` no se versiona (53 MB y creciendo; GitHub corta en 100 MB por archivo).
Commiteá los artefactos derivados -- `GRAPH_REPORT.md`, `flows.json`, `manifest.json` -- y dejá el
grafo crudo fuera del índice; `tests/test_agent_ops_setup.py` falla si vuelve a entrar.

No introduzcas secretos, llamadas LLM ni exportaciones masivas de nodos al vault.
