# Resumen Graphify

Generado: 2026-08-30T19:35:44.497965+00:00
Commit: `af0c518`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11756 nodes, 65903 edges, 437 communities, density 0.001, average degree 11.2118, undirected

Top hubs:
  1. Reservation (degree 1226, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1215, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1172, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 1054, community 0 Community 0, app/models/room.py)
  5. RoomCategory (degree 943, community 2 Community 2, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 782 nodes, 4306 internal edges, density 0.0141; top nodes: Reservation, ReservationStatusEnum, HotelConfiguration
  2. Community 1 - Community 1: 519 nodes, 1010 internal edges, density 0.0075; top nodes: database.py, dc4b68a ojooooo, config.py
  3. Community 2 - Community 2: 451 nodes, 3933 internal edges, density 0.0388; top nodes: RoomCategory, RoomStatusEnum, ReservationSourceEnum
  4. Community 3 - Community 3: 435 nodes, 18096 internal edges, density 0.1917; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  5. Community 4 - Community 4: 291 nodes, 565 internal edges, density 0.0134; top nodes: ReservationsPage.tsx, reservations.ts, guests.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
