# Resumen Graphify

Generado: 2026-07-27T23:25:15.882830+00:00
Commit: `531bfbf`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 8453 nodes, 33984 edges, 335 communities, density 0.001, average degree 8.0407, undirected

Top hubs:
  1. ReservationStatusEnum (degree 816, community 0 Community 0, app/models/reservation.py)
  2. Reservation (degree 815, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 772, community 1 Community 1, app/models/hotel_config.py)
  4. Room (degree 656, community 0 Community 0, app/models/room.py)
  5. Guest (degree 638, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 488 nodes, 2732 internal edges, density 0.023; top nodes: ReservationStatusEnum, Reservation, Room
  2. Community 1 - Community 1: 294 nodes, 1669 internal edges, density 0.0387; top nodes: HotelConfiguration, TransactionTypeEnum, PaymentMethodEnum
  3. Community 2 - Community 2: 279 nodes, 455 internal edges, density 0.0117; top nodes: database.py, main.py, config.py
  4. Community 3 - Community 3: 228 nodes, 1169 internal edges, density 0.0452; top nodes: CategoryPricing, DailyRate, ReservationChannelCodeEnum
  5. Community 4 - Community 4: 215 nodes, 959 internal edges, density 0.0417; top nodes: codex/feature/agent-ops-knowledge, main, codex/feature/trusted-qa-bootstrap

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS/.claude/worktrees/agent-a3c8668a591bf7739.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
