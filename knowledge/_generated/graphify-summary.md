# Resumen Graphify

Generado: 2026-08-22T00:03:32.495461+00:00
Commit: `8a53fc3`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10921 nodes, 58041 edges, 380 communities, density 0.001, average degree 10.6292, undirected

Top hubs:
  1. HotelConfiguration (degree 1015, community 2 Community 2, app/models/hotel_config.py)
  2. Reservation (degree 1004, community 2 Community 2, app/models/reservation.py)
  3. ReservationStatusEnum (degree 996, community 2 Community 2, app/models/reservation.py)
  4. Room (degree 835, community 1 Community 1, app/models/room.py)
  5. Guest (degree 771, community 1 Community 1, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 456 nodes, 729 internal edges, density 0.007; top nodes: database.py, dc4b68a ojooooo, main.py
  2. Community 1 - Community 1: 452 nodes, 1826 internal edges, density 0.0179; top nodes: Room, Guest, RoomCategory
  3. Community 2 - Community 2: 447 nodes, 2616 internal edges, density 0.0262; top nodes: HotelConfiguration, Reservation, ReservationStatusEnum
  4. Community 3 - Community 3: 427 nodes, 16749 internal edges, density 0.1842; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  5. Community 4 - Community 4: 336 nodes, 2000 internal edges, density 0.0355; top nodes: CategoryPricing, DailyRate, ReservationChannelCodeEnum

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/codex-debt-subscription-models.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
