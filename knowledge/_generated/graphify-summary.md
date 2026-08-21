# Resumen Graphify

Generado: 2026-08-20T21:38:20.687822+00:00
Commit: `867e41b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10357 nodes, 52182 edges, 375 communities, density 0.001, average degree 10.0767, undirected

Top hubs:
  1. Reservation (degree 943, community 5 Community 5, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 5 Community 5, app/models/room.py)
  5. Guest (degree 725, community 4 Community 4, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 401 nodes, 2255 internal edges, density 0.0281; top nodes: ReservationStatusEnum, HotelConfiguration, Transaction
  2. Community 1 - Community 1: 385 nodes, 13680 internal edges, density 0.1851; top nodes: feature/mobile-first-operations, feat/feat-temp-permission-grant, feat/tech0021-frontend-sessions-v2
  3. Community 2 - Community 2: 374 nodes, 549 internal edges, density 0.0079; top nodes: database.py, dc4b68a ojooooo, main.py
  4. Community 3 - Community 3: 340 nodes, 557 internal edges, density 0.0097; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  5. Community 4 - Community 4: 337 nodes, 1080 internal edges, density 0.0191; top nodes: Guest, Base, RoomStatusEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0071-master-admin-mfa.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
