# Resumen Graphify

Generado: 2026-08-20T19:29:14.082669+00:00
Commit: `666ec24`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10166 nodes, 49872 edges, 388 communities, density 0.001, average degree 9.8115, undirected

Top hubs:
  1. Reservation (degree 948, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 944, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 4 Community 4, app/models/hotel_config.py)
  4. Room (degree 769, community 0 Community 0, app/models/room.py)
  5. Guest (degree 730, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 497 nodes, 2647 internal edges, density 0.0215; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 392 nodes, 594 internal edges, density 0.0078; top nodes: database.py, dc4b68a ojooooo, main.py
  3. Community 2 - Community 2: 387 nodes, 12123 internal edges, density 0.1623; top nodes: feature/mobile-first-operations, feat/rbac-permission-metadata, feat/feat-temp-permission-grant
  4. Community 3 - Community 3: 306 nodes, 556 internal edges, density 0.0119; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, AppShell.tsx
  5. Community 4 - Community 4: 295 nodes, 820 internal edges, density 0.0189; top nodes: HotelConfiguration, RoomCategory, Base

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0060-guest-search.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
