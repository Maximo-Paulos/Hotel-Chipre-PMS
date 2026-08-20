# Resumen Graphify

Generado: 2026-08-20T16:18:19.820219+00:00
Commit: `dceb376`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 9985 nodes, 45519 edges, 377 communities, density 0.0009, average degree 9.1175, undirected

Top hubs:
  1. Reservation (degree 943, community 1 Community 1, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 1 Community 1, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 8 Community 8, app/models/hotel_config.py)
  4. Room (degree 769, community 4 Community 4, app/models/room.py)
  5. Guest (degree 725, community 7 Community 7, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 420 nodes, 8473 internal edges, density 0.0963; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, feat/argon2id-password-hashing
  2. Community 1 - Community 1: 369 nodes, 2074 internal edges, density 0.0305; top nodes: Reservation, ReservationStatusEnum, Transaction
  3. Community 2 - Community 2: 349 nodes, 542 internal edges, density 0.0089; top nodes: database.py, dc4b68a ojooooo, config.py
  4. Community 3 - Community 3: 330 nodes, 1742 internal edges, density 0.0321; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate
  5. Community 4 - Community 4: 292 nodes, 1141 internal edges, density 0.0269; top nodes: Room, RoomCategory, RoomStatusEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-totp-mfa.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
