# Resumen Graphify

Generado: 2026-11-05T10:04:46.630776+00:00
Commit: `60fea8cb82063e0ee3648aeb2309f9e2e5300999`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 18860 nodes, 78776 edges, 787 communities, density 0.0004, average degree 8.3538, undirected

Top hubs:
  1. Reservation (degree 1616, community 3 Community 3, app/models/reservation.py)
  2. HotelConfiguration (degree 1537, community 1 Community 1, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1491, community 3 Community 3, app/models/reservation.py)
  4. Room (degree 1200, community 3 Community 3, app/models/room.py)
  5. RoomCategory (degree 984, community 1 Community 1, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 667 nodes, 1100 internal edges, density 0.005; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, database.py, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 467 nodes, 3902 internal edges, density 0.0359; top nodes: HotelConfiguration, RoomCategory, Company
  3. Community 2 - Community 2: 450 nodes, 3455 internal edges, density 0.0342; top nodes: ReservationSourceEnum, TransactionTypeEnum, Transaction
  4. Community 3 - Community 3: 435 nodes, 2303 internal edges, density 0.0244; top nodes: Reservation, ReservationStatusEnum, Room
  5. Community 4 - Community 4: 422 nodes, 7606 internal edges, density 0.0856; top nodes: AuditActionEnum, ReservationError, PaymentError

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
