# Resumen Graphify

Generado: 2026-10-24T17:06:33.493617+00:00
Commit: `563ddc01d4b71ee63fce3a7115e02e83600d2ec3`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 17280 nodes, 64348 edges, 709 communities, density 0.0004, average degree 7.4477, undirected

Top hubs:
  1. Reservation (degree 1209, community 17 Community 17, app/models/reservation.py)
  2. HotelConfiguration (degree 1169, community 15 Community 15, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1086, community 17 Community 17, app/models/reservation.py)
  4. Room (degree 884, community 3 Community 3, app/models/room.py)
  5. RoomCategory (degree 709, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 489 nodes, 3270 internal edges, density 0.0274; top nodes: Company, ReservationSourceEnum, TransactionTypeEnum
  2. Community 1 - Community 1: 356 nodes, 1516 internal edges, density 0.024; top nodes: main, fix/local-simulation-workflows, feature/secure-auth-marketing-release-20260926
  3. Community 2 - Community 2: 336 nodes, 5132 internal edges, density 0.0912; top nodes: Guest, AuditActionEnum, ReservationError
  4. Community 3 - Community 3: 326 nodes, 3161 internal edges, density 0.0597; top nodes: Room, RoomCategory, RoomStatusEnum
  5. Community 4 - Community 4: 322 nodes, 643 internal edges, density 0.0124; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
