# Resumen Graphify

Generado: 2026-11-05T03:39:06.758119+00:00
Commit: `37011c3ebe11a7fabd0218a46dbcc2d3b45dedd4`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 18799 nodes, 77271 edges, 783 communities, density 0.0004, average degree 8.2208, undirected

Top hubs:
  1. Reservation (degree 1577, community 2 Community 2, app/models/reservation.py)
  2. HotelConfiguration (degree 1498, community 12 Community 12, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1452, community 2 Community 2, app/models/reservation.py)
  4. Room (degree 1161, community 2 Community 2, app/models/room.py)
  5. RoomCategory (degree 945, community 12 Community 12, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 556 nodes, 762 internal edges, density 0.0049; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], database.py, 9e4b357 Reduce PMS request load and complete simulation remediation
  2. Community 1 - Community 1: 433 nodes, 652 internal edges, density 0.007; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 81a7ffe Fix hotel simulation day 0 and day 1 findings
  3. Community 2 - Community 2: 431 nodes, 2259 internal edges, density 0.0244; top nodes: Reservation, ReservationStatusEnum, Room
  4. Community 3 - Community 3: 429 nodes, 6773 internal edges, density 0.0738; top nodes: AuditActionEnum, ReservationError, PaymentError
  5. Community 5 - Community 5: 371 nodes, 3003 internal edges, density 0.0438; top nodes: Company, TransactionTypeEnum, Transaction

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
