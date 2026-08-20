# Resumen Graphify

Generado: 2026-08-20T18:30:13.816518+00:00
Commit: `ff29e0d`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10119 nodes, 47889 edges, 369 communities, density 0.0009, average degree 9.4652, undirected

Top hubs:
  1. Reservation (degree 943, community 14 Community 14, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 1 Community 1, app/models/hotel_config.py)
  4. Room (degree 769, community 1 Community 1, app/models/room.py)
  5. Guest (degree 725, community 1 Community 1, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 475 nodes, 774 internal edges, density 0.0069; top nodes: database.py, dc4b68a ojooooo, main.py
  2. Community 1 - Community 1: 453 nodes, 1912 internal edges, density 0.0187; top nodes: HotelConfiguration, Room, Guest
  3. Community 2 - Community 2: 422 nodes, 10419 internal edges, density 0.1173; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, feat/argon2id-password-hashing
  4. Community 3 - Community 3: 343 nodes, 1724 internal edges, density 0.0294; top nodes: ReservationStatusEnum, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 304 nodes, 543 internal edges, density 0.0118; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, AppShell.tsx

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-rbac-metadata.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
