# Resumen Graphify

Generado: 2026-08-20T21:38:11.646345+00:00
Commit: `867e41b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10374 nodes, 52356 edges, 493 communities, density 0.001, average degree 10.0937, undirected

Top hubs:
  1. Reservation (degree 952, community 3 Community 3, app/models/reservation.py)
  2. ReservationStatusEnum (degree 948, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 924, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 778, community 0 Community 0, app/models/room.py)
  5. Guest (degree 734, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 498 nodes, 2542 internal edges, density 0.0205; top nodes: ReservationStatusEnum, HotelConfiguration, Room
  2. Community 1 - Community 1: 387 nodes, 13694 internal edges, density 0.1833; top nodes: feature/mobile-first-operations, feat/feat-temp-permission-grant, feat/tech0021-frontend-sessions-v2
  3. Community 2 - Community 2: 304 nodes, 1895 internal edges, density 0.0411; top nodes: RoomCategory, ReservationSourceEnum, CategoryPricing
  4. Community 3 - Community 3: 277 nodes, 1520 internal edges, density 0.0398; top nodes: Reservation, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 230 nodes, 2309 internal edges, density 0.0877; top nodes: AuditActionEnum, PaymentError, ReservationOperationsError

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0061-quotes-rates.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
