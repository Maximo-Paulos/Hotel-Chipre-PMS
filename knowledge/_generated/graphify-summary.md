# Resumen Graphify

Generado: 2026-09-18T04:18:50.391761+00:00
Commit: `788d35be190e75c14289180f669d93aed01a59d3`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13694 nodes, 78030 edges, 543 communities, density 0.0008, average degree 11.3962, undirected

Top hubs:
  1. Reservation (degree 1433, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1370, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1363, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 1232, community 3 Community 3, app/models/room.py)
  5. RoomCategory (degree 1089, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 887 nodes, 5107 internal edges, density 0.013; top nodes: Reservation, ReservationStatusEnum, HotelConfiguration
  2. Community 1 - Community 1: 548 nodes, 22105 internal edges, density 0.1475; top nodes: feat/tech0063-oltp-performance, 958fce2 Merge pull request #31 from Maximo-Paulos/feature/mobile-first-operations, feature/mobile-first-operations
  3. Community 2 - Community 2: 511 nodes, 997 internal edges, density 0.0077; top nodes: database.py, config.py, main.py
  4. Community 3 - Community 3: 431 nodes, 1780 internal edges, density 0.0192; top nodes: Room, RoomCategory, RoomStatusEnum
  5. Community 4 - Community 4: 429 nodes, 3365 internal edges, density 0.0367; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
