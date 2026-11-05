# Resumen Graphify

Generado: 2026-11-05T02:42:26.675060+00:00
Commit: `654deaa43255512d27a0aec11fbd95a6a6ff623e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 18785 nodes, 77151 edges, 789 communities, density 0.0004, average degree 8.2141, undirected

Top hubs:
  1. Reservation (degree 1577, community 0 Community 0, app/models/reservation.py)
  2. HotelConfiguration (degree 1498, community 3 Community 3, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1452, community 0 Community 0, app/models/reservation.py)
  4. Room (degree 1161, community 0 Community 0, app/models/room.py)
  5. RoomCategory (degree 945, community 0 Community 0, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 539 nodes, 2735 internal edges, density 0.0189; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 471 nodes, 746 internal edges, density 0.0067; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 9e4b357 Reduce PMS request load and complete simulation remediation
  3. Community 2 - Community 2: 468 nodes, 645 internal edges, density 0.0059; top nodes: database.py, main.py, 81a7ffe Fix hotel simulation day 0 and day 1 findings
  4. Community 3 - Community 3: 430 nodes, 3494 internal edges, density 0.0379; top nodes: HotelConfiguration, Guest, PricingPolicyError
  5. Community 4 - Community 4: 429 nodes, 6773 internal edges, density 0.0738; top nodes: AuditActionEnum, ReservationError, PaymentError

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
