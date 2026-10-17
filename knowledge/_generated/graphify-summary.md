# Resumen Graphify

Generado: 2026-10-17T05:57:19.957572+00:00
Commit: `96c79d98c0f431d6a5a56a64873bb634ab98a770`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15434 nodes, 47023 edges, 678 communities, density 0.0004, average degree 6.0934, undirected

Top hubs:
  1. HotelConfiguration (degree 605, community 5 Community 5, app/models/hotel_config.py)
  2. Reservation (degree 602, community 3 Community 3, app/models/reservation.py)
  3. ReservationStatusEnum (degree 484, community 6 Community 6, app/models/reservation.py)
  4. Base (degree 438, community 14 Community 14, app/database.py)
  5. Room (degree 431, community 6 Community 6, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 302 nodes, 453 internal edges, density 0.01; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 0ddeb59 Fix day 2 hotel simulation findings (#114)
  2. Community 1 - Community 1: 273 nodes, 443 internal edges, density 0.0119; top nodes: config.py, 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2
  3. Community 2 - Community 2: 255 nodes, 453 internal edges, density 0.014; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 251 nodes, 1140 internal edges, density 0.0363; top nodes: Reservation, TransactionTypeEnum, Transaction
  5. Community 4 - Community 4: 248 nodes, 323 internal edges, density 0.0105; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, config.ts

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
