# Resumen Graphify

Generado: 2026-09-26T09:43:28.287681+00:00
Commit: `222ef845ffdb80074016a5fbd97343735708822e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11140 nodes, 29268 edges, 575 communities, density 0.0005, average degree 5.2546, undirected

Top hubs:
  1. Base (degree 376, community 1 Community 1, app/database.py)
  2. Reservation (degree 277, community 5 Community 5, app/models/reservation.py)
  3. HotelConfiguration (degree 261, community 11 Community 11, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 220, community 31 Community 31, app/models/reservation.py)
  5. Room (degree 207, community 14 Community 14, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 258 nodes, 411 internal edges, density 0.0124; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  2. Community 1 - Community 1: 200 nodes, 422 internal edges, density 0.0212; top nodes: Base, Base, 8845d08 Fix eight real defects found auditing the whole project
  3. Community 2 - Community 2: 189 nodes, 1084 internal edges, density 0.061; top nodes: feature/secure-auth-marketing-release-20260926, codex/production-render-qa, codex/public-site-inquiries
  4. Community 3 - Community 3: 166 nodes, 289 internal edges, density 0.0211; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts
  5. Community 4 - Community 4: 156 nodes, 636 internal edges, density 0.0526; top nodes: ReservationSourceEnum, Transaction, TransactionStatusEnum

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
