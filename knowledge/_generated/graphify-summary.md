# Resumen Graphify

Generado: 2026-08-20T20:15:49.043376+00:00
Commit: `0ad7802`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10212 nodes, 50747 edges, 380 communities, density 0.001, average degree 9.9387, undirected

Top hubs:
  1. Reservation (degree 943, community 3 Community 3, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 3 Community 3, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 420 nodes, 1591 internal edges, density 0.0181; top nodes: HotelConfiguration, Guest, Base
  2. Community 1 - Community 1: 401 nodes, 605 internal edges, density 0.0075; top nodes: database.py, dc4b68a ojooooo, main.py
  3. Community 2 - Community 2: 389 nodes, 12902 internal edges, density 0.171; top nodes: feature/mobile-first-operations, feat/feat-temp-permission-grant, feat/rbac-permission-metadata
  4. Community 3 - Community 3: 340 nodes, 1301 internal edges, density 0.0226; top nodes: Reservation, ReservationStatusEnum, Room
  5. Community 4 - Community 4: 321 nodes, 600 internal edges, density 0.0117; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, auth.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0031-invitation-lifecycle.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
