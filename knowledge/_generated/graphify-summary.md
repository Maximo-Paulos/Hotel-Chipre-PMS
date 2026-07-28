# Resumen Graphify

Generado: 2026-07-28T20:08:27.458776+00:00
Commit: `765ff7b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 8638 nodes, 36255 edges, 351 communities, density 0.001, average degree 8.3943, undirected

Top hubs:
  1. ReservationStatusEnum (degree 834, community 3 Community 3, app/models/reservation.py)
  2. Reservation (degree 833, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 814, community 2 Community 2, app/models/hotel_config.py)
  4. Room (degree 674, community 0 Community 0, app/models/room.py)
  5. Guest (degree 656, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 389 nodes, 1685 internal edges, density 0.0223; top nodes: Room, Guest, RoomCategory
  2. Community 1 - Community 1: 349 nodes, 587 internal edges, density 0.0097; top nodes: dc4b68a ojooooo, database.py, main.py
  3. Community 2 - Community 2: 337 nodes, 1738 internal edges, density 0.0307; top nodes: HotelConfiguration, TransactionTypeEnum, PaymentMethodEnum
  4. Community 3 - Community 3: 275 nodes, 904 internal edges, density 0.024; top nodes: ReservationStatusEnum, Reservation, ReservationError
  5. Community 4 - Community 4: 267 nodes, 1365 internal edges, density 0.0384; top nodes: CategoryPricing, DailyRate, ReservationChannelCodeEnum

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS/.claude/worktrees/agent-a406cbc9533347deb.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
