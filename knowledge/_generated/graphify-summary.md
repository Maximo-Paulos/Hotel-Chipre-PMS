# Resumen Graphify

Generado: 2026-08-20T18:54:04.186769+00:00
Commit: `b4cdeb9`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10139 nodes, 48736 edges, 376 communities, density 0.0009, average degree 9.6136, undirected

Top hubs:
  1. Reservation (degree 943, community 8 Community 8, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 4 Community 4, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 436 nodes, 1649 internal edges, density 0.0174; top nodes: HotelConfiguration, Guest, Base
  2. Community 1 - Community 1: 432 nodes, 659 internal edges, density 0.0071; top nodes: database.py, dc4b68a ojooooo, main.py
  3. Community 2 - Community 2: 392 nodes, 11160 internal edges, density 0.1456; top nodes: feature/mobile-first-operations, feat/rbac-permission-metadata, fix/rls-missing-tenant-tables
  4. Community 3 - Community 3: 301 nodes, 481 internal edges, density 0.0107; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  5. Community 5 - Community 5: 295 nodes, 1803 internal edges, density 0.0416; top nodes: RoomCategory, ReservationSourceEnum, CategoryPricing

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0021-frontend.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
