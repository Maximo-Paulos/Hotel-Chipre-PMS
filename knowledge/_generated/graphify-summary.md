# Resumen Graphify

Generado: 2026-07-23T14:36:55.565980+00:00
Commit: `d25c542`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 6251 nodes, 19636 edges, 290 communities, density 0.001, average degree 6.2825, undirected

Top hubs:
  1. ReservationStatusEnum (degree 440, community 1 Community 1, app/models/reservation.py)
  2. Reservation (degree 435, community 1 Community 1, app/models/reservation.py)
  3. HotelConfiguration (degree 379, community 4 Community 4, app/models/hotel_config.py)
  4. Room (degree 332, community 1 Community 1, app/models/room.py)
  5. Guest (degree 317, community 1 Community 1, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 265 nodes, 390 internal edges, density 0.0111; top nodes: dc4b68a ojooooo, database.py, main.py
  2. Community 1 - Community 1: 195 nodes, 1011 internal edges, density 0.0534; top nodes: ReservationStatusEnum, Reservation, Room
  3. Community 2 - Community 2: 178 nodes, 985 internal edges, density 0.0625; top nodes: codex/feature/agent-ops-knowledge, main, codex/feature/trusted-qa-bootstrap
  4. Community 3 - Community 3: 169 nodes, 689 internal edges, density 0.0485; top nodes: TransactionTypeEnum, PaymentMethodEnum, Transaction
  5. Community 4 - Community 4: 127 nodes, 407 internal edges, density 0.0509; top nodes: HotelConfiguration, RoomCategory, ReservationSourceEnum

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] graph.json built from bf14bf5 but HEAD is d25c542
[graphify check-update] Run the graphify skill with --update to refresh semantic data.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
