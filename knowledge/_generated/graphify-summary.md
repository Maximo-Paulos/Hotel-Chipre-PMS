# Resumen Graphify

Generado: 2026-07-28T00:17:31.347551+00:00
Commit: `bfb74db`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 8586 nodes, 35111 edges, 358 communities, density 0.001, average degree 8.1787, undirected

Top hubs:
  1. ReservationStatusEnum (degree 816, community 3 Community 3, app/models/reservation.py)
  2. Reservation (degree 815, community 11 Community 11, app/models/reservation.py)
  3. HotelConfiguration (degree 791, community 2 Community 2, app/models/hotel_config.py)
  4. Room (degree 656, community 0 Community 0, app/models/room.py)
  5. Guest (degree 638, community 3 Community 3, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 313 nodes, 1194 internal edges, density 0.0245; top nodes: Room, RoomCategory, Base
  2. Community 1 - Community 1: 311 nodes, 518 internal edges, density 0.0107; top nodes: dc4b68a ojooooo, database.py, main.py
  3. Community 2 - Community 2: 287 nodes, 1602 internal edges, density 0.039; top nodes: HotelConfiguration, TransactionTypeEnum, PaymentMethodEnum
  4. Community 3 - Community 3: 277 nodes, 957 internal edges, density 0.025; top nodes: ReservationStatusEnum, Guest, ReservationError
  5. Community 4 - Community 4: 258 nodes, 1265 internal edges, density 0.0382; top nodes: CategoryPricing, DailyRate, ReservationChannelCodeEnum

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS/.claude/worktrees/agent-aecd3f4cd61235ef5.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
