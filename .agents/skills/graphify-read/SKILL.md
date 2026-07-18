---
name: graphify-read
description: Lee el grafo técnico sin modificarlo.
---

# graphify-read

Usa esta skill para preguntas de arquitectura, dependencias, hotspots o impacto de código.

1. Lee `.graphify/GRAPH_REPORT.md` y ejecuta `graphify check-update`.
2. Si el grafo está fresco, usa sólo la consulta mínima: `summary`, `query`, `minimal-context` o `affected-flows`.
3. Marca toda conclusión con la frescura del grafo y distingue evidencia de inferencia.

No ejecutes `graphify update`, no exportes miles de nodos a Obsidian y no sustituyas la inspección del código cuando el grafo esté desactualizado.
