# Resumen Graphify

Generado: 2026-09-26T08:58:14.256052+00:00
Commit: `9aa0beea9ddb1fcf33e2c6f60a23dab3438f1b9f`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11136 nodes, 29243 edges, 583 communities, density 0.0005, average degree 5.252, undirected

Top hubs:
  1. Base (degree 376, community 2 Community 2, app/database.py)
  2. Reservation (degree 277, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 261, community 11 Community 11, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 220, community 30 Community 30, app/models/reservation.py)
  5. Room (degree 207, community 13 Community 13, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 276 nodes, 451 internal edges, density 0.0119; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  2. Community 1 - Community 1: 217 nodes, 1166 internal edges, density 0.0498; top nodes: codex/production-render-qa, codex/public-site-inquiries, docs/auditoria-pms-20260908
  3. Community 2 - Community 2: 200 nodes, 422 internal edges, density 0.0212; top nodes: Base, Base, 8845d08 Fix eight real defects found auditing the whole project
  4. Community 3 - Community 3: 156 nodes, 636 internal edges, density 0.0526; top nodes: ReservationSourceEnum, Transaction, TransactionStatusEnum
  5. Community 4 - Community 4: 154 nodes, 439 internal edges, density 0.0373; top nodes: Reservation, AuditActionEnum, ReservationError

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
