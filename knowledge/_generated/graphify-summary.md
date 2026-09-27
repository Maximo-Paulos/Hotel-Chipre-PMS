# Resumen Graphify

Generado: 2026-09-27T00:08:35.608743+00:00
Commit: `9d05e2c49d8734fb84c6ebee3eab012e1e317425`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11362 nodes, 30119 edges, 610 communities, density 0.0005, average degree 5.3017, undirected

Top hubs:
  1. Base (degree 381, community 2 Community 2, app/database.py)
  2. Reservation (degree 287, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 274, community 11 Community 11, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 225, community 3 Community 3, app/models/reservation.py)
  5. Room (degree 217, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 212 nodes, 287 internal edges, density 0.0128; top nodes: main.py, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, f45e8eb Implement Google onboarding and staff aliases
  2. Community 1 - Community 1: 196 nodes, 1117 internal edges, density 0.0585; top nodes: main, feature/secure-auth-marketing-release-20260926, codex/production-render-qa
  3. Community 2 - Community 2: 171 nodes, 362 internal edges, density 0.0249; top nodes: Base, Base, str
  4. Community 3 - Community 3: 160 nodes, 611 internal edges, density 0.048; top nodes: Reservation, ReservationStatusEnum, Room
  5. Community 4 - Community 4: 144 nodes, 207 internal edges, density 0.0201; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, usePermissions.ts

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
