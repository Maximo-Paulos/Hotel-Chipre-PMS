# Resumen Graphify

Generado: 2026-08-20T16:49:06.370537+00:00
Commit: `453cc6c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10002 nodes, 45771 edges, 376 communities, density 0.0009, average degree 9.1524, undirected

Top hubs:
  1. Reservation (degree 943, community 2 Community 2, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 2 Community 2, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 9 Community 9, app/models/hotel_config.py)
  4. Room (degree 769, community 5 Community 5, app/models/room.py)
  5. Guest (degree 725, community 8 Community 8, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 415 nodes, 8655 internal edges, density 0.1008; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, feat/argon2id-password-hashing
  2. Community 1 - Community 1: 381 nodes, 595 internal edges, density 0.0082; top nodes: database.py, dc4b68a ojooooo, config.py
  3. Community 2 - Community 2: 353 nodes, 1946 internal edges, density 0.0313; top nodes: Reservation, ReservationStatusEnum, Transaction
  4. Community 3 - Community 3: 309 nodes, 1672 internal edges, density 0.0351; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate
  5. Community 4 - Community 4: 272 nodes, 490 internal edges, density 0.0133; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, AppShell.tsx

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/fix-google-oauth-takeover.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
