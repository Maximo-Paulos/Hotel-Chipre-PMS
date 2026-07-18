# Resumen Graphify

Generado: 2026-07-18T16:40:12.881433+00:00
Commit: `bc938cf`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 5528 nodes, 17098 edges, 289 communities, density 0.0011, average degree 6.186, undirected

Top hubs:
  1. ReservationStatusEnum (degree 398, community 2 Community 2, app/models/reservation.py)
  2. Reservation (degree 393, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 337, community 2 Community 2, app/models/hotel_config.py)
  4. Base (degree 303, community 7 Community 7, app/database.py)
  5. Room (degree 301, community 2 Community 2, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 275 nodes, 406 internal edges, density 0.0108; top nodes: dc4b68a ojooooo, database.py, main.py
  2. Community 1 - Community 1: 192 nodes, 701 internal edges, density 0.0382; top nodes: main, codex/feature/agent-ops-knowledge, chore/weekly-orchestrator-2026-07-03
  3. Community 2 - Community 2: 174 nodes, 776 internal edges, density 0.0516; top nodes: ReservationStatusEnum, HotelConfiguration, Room
  4. Community 3 - Community 3: 148 nodes, 663 internal edges, density 0.0609; top nodes: TransactionTypeEnum, PaymentMethodEnum, Transaction
  5. Community 4 - Community 4: 115 nodes, 325 internal edges, density 0.0496; top nodes: Reservation, ReservationError, ReservationSourceEnum

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/Desktop/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
