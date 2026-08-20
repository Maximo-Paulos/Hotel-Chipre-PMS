# Resumen Graphify

Generado: 2026-08-20T16:02:17.543172+00:00
Commit: `469b13e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 9923 nodes, 45172 edges, 369 communities, density 0.0009, average degree 9.1045, undirected

Top hubs:
  1. Reservation (degree 943, community 9 Community 9, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 0 Community 0, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 418 nodes, 1879 internal edges, density 0.0216; top nodes: HotelConfiguration, Room, Guest
  2. Community 1 - Community 1: 414 nodes, 8270 internal edges, density 0.0967; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, feat/argon2id-password-hashing
  3. Community 2 - Community 2: 402 nodes, 629 internal edges, density 0.0078; top nodes: database.py, dc4b68a ojooooo, config.py
  4. Community 3 - Community 3: 331 nodes, 1630 internal edges, density 0.0298; top nodes: ReservationStatusEnum, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 298 nodes, 1708 internal edges, density 0.0386; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/fix-rate-limiter-race.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
