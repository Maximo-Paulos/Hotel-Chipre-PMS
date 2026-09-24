# Resumen Graphify

Generado: 2026-09-24T21:40:34.232616+00:00
Commit: `cd0705c851d98db7852c14e74f7e9ba56acdc9e2`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 14068 nodes, 81089 edges, 525 communities, density 0.0008, average degree 11.5281, undirected

Top hubs:
  1. Reservation (degree 1469, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1384, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1380, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 1237, community 4 Community 4, app/models/room.py)
  5. RoomCategory (degree 1103, community 9 Community 9, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 755 nodes, 4123 internal edges, density 0.0145; top nodes: Reservation, ReservationStatusEnum, HotelConfiguration
  2. Community 1 - Community 1: 546 nodes, 22939 internal edges, density 0.1542; top nodes: 958fce2 Merge pull request #31 from Maximo-Paulos/feature/mobile-first-operations, feat/tech0063-oltp-performance, feature/mobile-first-operations
  3. Community 2 - Community 2: 511 nodes, 950 internal edges, density 0.0073; top nodes: database.py, config.py, main.py
  4. Community 3 - Community 3: 432 nodes, 3371 internal edges, density 0.0362; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate
  5. Community 4 - Community 4: 430 nodes, 1196 internal edges, density 0.013; top nodes: Room, Guest, DocumentTypeEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
