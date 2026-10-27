# Resumen Graphify

Generado: 2026-10-27T17:04:36.956368+00:00
Commit: `5a603f66364fa3ba4f3796359d1942c31d90fb1c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 18537 nodes, 74288 edges, 749 communities, density 0.0004, average degree 8.0151, undirected

Top hubs:
  1. Reservation (degree 1530, community 16 Community 16, app/models/reservation.py)
  2. HotelConfiguration (degree 1450, community 0 Community 0, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 1405, community 8 Community 8, app/models/reservation.py)
  4. Room (degree 1145, community 8 Community 8, app/models/room.py)
  5. RoomCategory (degree 935, community 0 Community 0, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 453 nodes, 3784 internal edges, density 0.037; top nodes: HotelConfiguration, RoomCategory, Guest
  2. Community 1 - Community 1: 447 nodes, 694 internal edges, density 0.007; top nodes: database.py, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, 0ddeb59 Fix day 2 hotel simulation findings (#114)
  3. Community 2 - Community 2: 429 nodes, 6773 internal edges, density 0.0738; top nodes: AuditActionEnum, ReservationError, PaymentError
  4. Community 3 - Community 3: 419 nodes, 671 internal edges, density 0.0077; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, f45e8eb Implement Google onboarding and staff aliases
  5. Community 4 - Community 4: 419 nodes, 595 internal edges, density 0.0068; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
