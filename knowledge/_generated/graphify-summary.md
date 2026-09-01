# Resumen Graphify

Generado: 2026-09-01T12:30:11.604504+00:00
Commit: `e2ae869`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12184 nodes, 68539 edges, 450 communities, density 0.0009, average degree 11.2507, undirected

Top hubs:
  1. Reservation (degree 1322, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1298, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1253, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 1147, community 0 Community 0, app/models/room.py)
  5. RoomCategory (degree 1022, community 17 Community 17, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 813 nodes, 4636 internal edges, density 0.014; top nodes: Reservation, ReservationStatusEnum, HotelConfiguration
  2. Community 1 - Community 1: 486 nodes, 890 internal edges, density 0.0076; top nodes: database.py, config.py, main.py
  3. Community 2 - Community 2: 470 nodes, 18591 internal edges, density 0.1687; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  4. Community 3 - Community 3: 412 nodes, 3097 internal edges, density 0.0366; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate
  5. Community 4 - Community 4: 353 nodes, 1594 internal edges, density 0.0257; top nodes: Transaction, TransactionTypeEnum, PaymentMethodEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/worktrees/Hotel-Chipre-PMS-realtime-collaboration.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] graph.json built from 9aee997 but HEAD is e2ae869
[graphify check-update] Run the graphify skill with --update to refresh semantic data.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
