# Resumen Graphify

Generado: 2026-09-25T20:21:55.195211+00:00
Commit: `1b6ca04597722a24f7cfe7a1d5b6e7ce82688d1e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 14242 nodes, 82216 edges, 530 communities, density 0.0008, average degree 11.5456, undirected

Top hubs:
  1. Reservation (degree 1473, community 0 Community 0, app/models/reservation.py)
  2. HotelConfiguration (degree 1391, community 0 Community 0, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1388, community 0 Community 0, app/models/reservation.py)
  4. Room (degree 1241, community 4 Community 4, app/models/room.py)
  5. RoomCategory (degree 1107, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 697 nodes, 3847 internal edges, density 0.0159; top nodes: Reservation, HotelConfiguration, ReservationStatusEnum
  2. Community 1 - Community 1: 570 nodes, 1172 internal edges, density 0.0072; top nodes: database.py, dc4b68a ojooooo, config.py
  3. Community 2 - Community 2: 547 nodes, 22953 internal edges, density 0.1537; top nodes: 958fce2 Merge pull request #31 from Maximo-Paulos/feature/mobile-first-operations, feat/tech0063-oltp-performance, feature/mobile-first-operations
  4. Community 3 - Community 3: 538 nodes, 4322 internal edges, density 0.0299; top nodes: RoomCategory, RoomStatusEnum, CategoryPricing
  5. Community 4 - Community 4: 449 nodes, 1383 internal edges, density 0.0138; top nodes: Room, Guest, ReservationSourceEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
