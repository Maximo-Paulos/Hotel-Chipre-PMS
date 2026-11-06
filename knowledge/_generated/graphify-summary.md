# Resumen Graphify

Generado: 2026-11-05T12:24:24.969262+00:00
Commit: `edc799f24a774651f92d6f5dcdbf291f933c4b60`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 18883 nodes, 79093 edges, 816 communities, density 0.0004, average degree 8.3772, undirected

Top hubs:
  1. Reservation (degree 1616, community 1 Community 1, app/models/reservation.py)
  2. HotelConfiguration (degree 1537, community 3 Community 3, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1491, community 1 Community 1, app/models/reservation.py)
  4. Room (degree 1200, community 1 Community 1, app/models/room.py)
  5. RoomCategory (degree 984, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 719 nodes, 1126 internal edges, density 0.0044; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, database.py, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 456 nodes, 2383 internal edges, density 0.023; top nodes: Reservation, ReservationStatusEnum, Room
  3. Community 2 - Community 2: 450 nodes, 3479 internal edges, density 0.0344; top nodes: Company, ReservationSourceEnum, TransactionTypeEnum
  4. Community 3 - Community 3: 444 nodes, 3772 internal edges, density 0.0384; top nodes: HotelConfiguration, RoomCategory, Guest
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
