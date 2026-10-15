# Resumen Graphify

Generado: 2026-10-15T20:14:16.758749+00:00
Commit: `ef0aa41f0efd7cfdebf42918700add640adbcbf6`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15130 nodes, 45086 edges, 652 communities, density 0.0004, average degree 5.9598, undirected

Top hubs:
  1. Reservation (degree 550, community 16 Community 16, app/models/reservation.py)
  2. HotelConfiguration (degree 525, community 7 Community 7, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 442, community 54 Community 54, app/models/reservation.py)
  4. Base (degree 431, community 9 Community 9, app/database.py)
  5. Room (degree 404, community 43 Community 43, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 319 nodes, 486 internal edges, density 0.0096; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 262 nodes, 417 internal edges, density 0.0122; top nodes: config.py, 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2
  3. Community 2 - Community 2: 247 nodes, 332 internal edges, density 0.0109; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, 150ca64 Reduce PMS request load and keep analytics facts fresh
  4. Community 3 - Community 3: 228 nodes, 1169 internal edges, density 0.0452; top nodes: ReservationSourceEnum, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 209 nodes, 363 internal edges, density 0.0167; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
