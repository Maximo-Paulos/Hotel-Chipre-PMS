# Resumen Graphify

Generado: 2026-08-20T21:48:41.717542+00:00
Commit: `867e41b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10363 nodes, 52215 edges, 375 communities, density 0.001, average degree 10.0772, undirected

Top hubs:
  1. Reservation (degree 943, community 1 Community 1, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 1 Community 1, app/models/reservation.py)
  3. HotelConfiguration (degree 920, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 0 Community 0, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 490 nodes, 1936 internal edges, density 0.0162; top nodes: HotelConfiguration, Room, Guest
  2. Community 1 - Community 1: 394 nodes, 2215 internal edges, density 0.0286; top nodes: Reservation, ReservationStatusEnum, Transaction
  3. Community 2 - Community 2: 387 nodes, 13696 internal edges, density 0.1834; top nodes: feature/mobile-first-operations, feat/feat-temp-permission-grant, feat/tech0021-frontend-sessions-v2
  4. Community 3 - Community 3: 367 nodes, 596 internal edges, density 0.0089; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  5. Community 4 - Community 4: 359 nodes, 518 internal edges, density 0.0081; top nodes: database.py, dc4b68a ojooooo, main.py

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0051-subscriptions.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
