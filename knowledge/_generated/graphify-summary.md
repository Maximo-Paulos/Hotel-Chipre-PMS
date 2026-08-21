# Resumen Graphify

Generado: 2026-08-21T03:53:05.746370+00:00
Commit: `b6cd93c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10508 nodes, 53663 edges, 377 communities, density 0.001, average degree 10.2137, undirected

Top hubs:
  1. Reservation (degree 963, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 959, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 940, community 8 Community 8, app/models/hotel_config.py)
  4. Room (degree 784, community 0 Community 0, app/models/room.py)
  5. Guest (degree 745, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 618 nodes, 3289 internal edges, density 0.0173; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 410 nodes, 14358 internal edges, density 0.1712; top nodes: feature/mobile-first-operations, feat/tech0063-oltp-performance, feat/feat-temp-permission-grant
  3. Community 2 - Community 2: 368 nodes, 1935 internal edges, density 0.0287; top nodes: Transaction, TransactionTypeEnum, PaymentMethodEnum
  4. Community 3 - Community 3: 361 nodes, 619 internal edges, density 0.0095; top nodes: database.py, 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2
  5. Community 4 - Community 4: 339 nodes, 2106 internal edges, density 0.0368; top nodes: RoomCategory, ReservationSourceEnum, CategoryPricing

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0040-restore-defaults.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
