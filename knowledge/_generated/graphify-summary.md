# Resumen Graphify

Generado: 2026-08-20T18:51:08.022409+00:00
Commit: `0534c64`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10128 nodes, 48674 edges, 384 communities, density 0.0009, average degree 9.6118, undirected

Top hubs:
  1. Reservation (degree 943, community 7 Community 7, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 4 Community 4, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 436 nodes, 1649 internal edges, density 0.0174; top nodes: HotelConfiguration, Guest, Base
  2. Community 1 - Community 1: 393 nodes, 11156 internal edges, density 0.1448; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, feat/argon2id-password-hashing
  3. Community 2 - Community 2: 371 nodes, 569 internal edges, density 0.0083; top nodes: database.py, dc4b68a ojooooo, main.py
  4. Community 3 - Community 3: 308 nodes, 547 internal edges, density 0.0116; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, AppShell.tsx
  5. Community 5 - Community 5: 295 nodes, 1803 internal edges, density 0.0416; top nodes: RoomCategory, ReservationSourceEnum, CategoryPricing

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-unified-audit-read.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
