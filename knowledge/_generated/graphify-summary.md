# Resumen Graphify

Generado: 2026-10-17T21:40:10.252948+00:00
Commit: `dcaa730303924465150e1b5168c13438a92c6c9f`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15695 nodes, 48324 edges, 686 communities, density 0.0004, average degree 6.1579, undirected

Top hubs:
  1. HotelConfiguration (degree 650, community 6 Community 6, app/models/hotel_config.py)
  2. Reservation (degree 632, community 0 Community 0, app/models/reservation.py)
  3. ReservationStatusEnum (degree 515, community 0 Community 0, app/models/reservation.py)
  4. Base (degree 448, community 10 Community 10, app/database.py)
  5. Room (degree 436, community 0 Community 0, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 290 nodes, 1455 internal edges, density 0.0347; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 290 nodes, 421 internal edges, density 0.01; top nodes: database.py, bf4a21f Fix day 0 and day 1 hotel simulation findings, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness
  3. Community 2 - Community 2: 269 nodes, 340 internal edges, density 0.0094; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, 81a7ffe Fix hotel simulation day 0 and day 1 findings, 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback
  4. Community 3 - Community 3: 257 nodes, 1440 internal edges, density 0.0438; top nodes: Company, ReservationSourceEnum, TransactionTypeEnum
  5. Community 5 - Community 5: 246 nodes, 430 internal edges, density 0.0143; top nodes: ed918c6 Make the whole app one visual system and fix what the e2e journeys exposed, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup, business-journey.spec.ts

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
