---
scope: Graphify, arquitectura, hotspots, contexto mínimo y frescura
owner: knowledge-graph-curator
last_verified_commit: bf14bf5
canonical_sources: [.graphify/GRAPH_REPORT.md, knowledge/_generated/graphify-summary.md, .graphify/flows.json]
consumers: [architecture-reviewer, docs-writer, knowledge-graph-curator]
graphify_minimum: graphify check-update .
required_validation: graphify update scope all + flows build + portable-check + check-update tras código
---
# Context pack — Grafo de conocimiento

Graphify es el mapa técnico, no un vault alternativo. Antes de conclusiones estructurales leer `GRAPH_REPORT.md` y navegar `.graphify/wiki/index.md` si existe. Tras cambios de código ejecutar `graphify update . --scope all --no-description --no-label`, `graphify flows build`, `.venv/bin/python scripts/agent_ops/normalize_graphify_portability.py` y verificar portable/frescura.
