# Resumen Graphify

Generado: 2026-11-05T05:51:42.069718+00:00
Commit: `75edbce9f3d35ace71c4954eba8e593461a11150`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 18804 nodes, 77302 edges, 769 communities, density 0.0004, average degree 8.2219, undirected

Top hubs:
  1. Reservation (degree 1577, community 2 Community 2, app/models/reservation.py)
  2. HotelConfiguration (degree 1498, community 3 Community 3, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1452, community 2 Community 2, app/models/reservation.py)
  4. Room (degree 1161, community 2 Community 2, app/models/room.py)
  5. RoomCategory (degree 945, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 585 nodes, 795 internal edges, density 0.0047; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], database.py, 9e4b357 Reduce PMS request load and complete simulation remediation
  2. Community 1 - Community 1: 556 nodes, 871 internal edges, density 0.0056; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness
  3. Community 2 - Community 2: 472 nodes, 2375 internal edges, density 0.0214; top nodes: Reservation, ReservationStatusEnum, Room
  4. Community 3 - Community 3: 446 nodes, 3582 internal edges, density 0.0361; top nodes: HotelConfiguration, RoomCategory, PricingPolicyError
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
