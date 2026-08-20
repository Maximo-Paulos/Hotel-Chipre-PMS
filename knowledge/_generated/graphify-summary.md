# Resumen Graphify

Generado: 2026-08-20T14:45:03.336076+00:00
Commit: `6cbb087`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 9872 nodes, 44253 edges, 378 communities, density 0.0009, average degree 8.9654, undirected

Top hubs:
  1. Reservation (degree 943, community 7 Community 7, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 1 Community 1, app/models/hotel_config.py)
  4. Room (degree 769, community 1 Community 1, app/models/room.py)
  5. Guest (degree 725, community 1 Community 1, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 425 nodes, 7489 internal edges, density 0.0831; top nodes: feature/mobile-first-operations, worktree-agent-af404149f1b835229, worktree-agent-aa90c760fab5d7651
  2. Community 1 - Community 1: 399 nodes, 1785 internal edges, density 0.0225; top nodes: HotelConfiguration, Room, Guest
  3. Community 2 - Community 2: 357 nodes, 549 internal edges, density 0.0086; top nodes: database.py, dc4b68a ojooooo, config.py
  4. Community 3 - Community 3: 333 nodes, 1777 internal edges, density 0.0321; top nodes: ReservationStatusEnum, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 304 nodes, 1733 internal edges, density 0.0376; top nodes: RoomCategory, CategoryPricing, DailyRate

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/fix-audit-log-cascade.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
