# Resumen Graphify

Generado: 2026-09-03T02:01:46.310126+00:00
Commit: `0fc3f497841b8da166631d5ca5d476943ed1dbd5`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12024 nodes, 67376 edges, 456 communities, density 0.0009, average degree 11.2069, undirected

Top hubs:
  1. Reservation (degree 1272, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1261, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1208, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 1083, community 10 Community 10, app/models/room.py)
  5. RoomCategory (degree 974, community 2 Community 2, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 662 nodes, 3741 internal edges, density 0.0171; top nodes: Reservation, ReservationStatusEnum, HotelConfiguration
  2. Community 1 - Community 1: 516 nodes, 1005 internal edges, density 0.0076; top nodes: database.py, dc4b68a ojooooo, config.py
  3. Community 2 - Community 2: 466 nodes, 3809 internal edges, density 0.0352; top nodes: RoomCategory, RoomStatusEnum, CategoryPricing
  4. Community 3 - Community 3: 440 nodes, 18458 internal edges, density 0.1911; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  5. Community 4 - Community 4: 390 nodes, 1109 internal edges, density 0.0146; top nodes: Guest, Base, ReservationSourceEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS-tech-0140.
[graphify check-update] graph.json built from 21b67dd but HEAD is 0fc3f49
[graphify check-update] Run the graphify skill with --update to refresh semantic data.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
