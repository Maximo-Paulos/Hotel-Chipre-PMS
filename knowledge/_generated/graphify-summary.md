# Resumen Graphify

Generado: 2026-08-20T19:03:41.575928+00:00
Commit: `0f570db`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10195 nodes, 48970 edges, 388 communities, density 0.0009, average degree 9.6067, undirected

Top hubs:
  1. Reservation (degree 943, community 7 Community 7, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 1 Community 1, app/models/hotel_config.py)
  4. Room (degree 769, community 4 Community 4, app/models/room.py)
  5. Guest (degree 725, community 1 Community 1, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 468 nodes, 756 internal edges, density 0.0069; top nodes: database.py, dc4b68a ojooooo, main.py
  2. Community 1 - Community 1: 436 nodes, 1649 internal edges, density 0.0174; top nodes: HotelConfiguration, Guest, Base
  3. Community 2 - Community 2: 392 nodes, 11150 internal edges, density 0.1455; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, feat/argon2id-password-hashing
  4. Community 3 - Community 3: 296 nodes, 535 internal edges, density 0.0123; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, AppShell.tsx
  5. Community 5 - Community 5: 295 nodes, 1803 internal edges, density 0.0416; top nodes: RoomCategory, ReservationSourceEnum, CategoryPricing

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-temp-permission-grant.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
