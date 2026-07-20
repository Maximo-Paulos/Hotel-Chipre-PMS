# Resumen Graphify

Generado: 2026-07-20T03:53:42.676008+00:00
Commit: `767226c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 6171 nodes, 19157 edges, 297 communities, density 0.001, average degree 6.2087, undirected

Top hubs:
  1. ReservationStatusEnum (degree 440, community 0 Community 0, app/models/reservation.py)
  2. Reservation (degree 435, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 379, community 4 Community 4, app/models/hotel_config.py)
  4. Room (degree 332, community 0 Community 0, app/models/room.py)
  5. Guest (degree 317, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 195 nodes, 1012 internal edges, density 0.0535; top nodes: ReservationStatusEnum, Reservation, Room
  2. Community 1 - Community 1: 194 nodes, 273 internal edges, density 0.0146; top nodes: dc4b68a ojooooo, main.py, e34785c prueba
  3. Community 2 - Community 2: 186 nodes, 871 internal edges, density 0.0506; top nodes: main, codex/feature/agent-ops-knowledge, chore/weekly-orchestrator-2026-07-03
  4. Community 3 - Community 3: 159 nodes, 655 internal edges, density 0.0521; top nodes: TransactionTypeEnum, PaymentMethodEnum, Transaction
  5. Community 4 - Community 4: 127 nodes, 407 internal edges, density 0.0509; top nodes: HotelConfiguration, RoomCategory, ReservationSourceEnum

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/Desktop/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
