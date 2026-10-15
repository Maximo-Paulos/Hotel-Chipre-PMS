# Resumen Graphify

Generado: 2026-10-15T21:09:48.028025+00:00
Commit: `46969e1930518e4b9afb4bf1919357fc541474ab`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15131 nodes, 45151 edges, 655 communities, density 0.0004, average degree 5.968, undirected

Top hubs:
  1. Reservation (degree 550, community 17 Community 17, app/models/reservation.py)
  2. HotelConfiguration (degree 525, community 8 Community 8, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 442, community 52 Community 52, app/models/reservation.py)
  4. Base (degree 431, community 9 Community 9, app/database.py)
  5. Room (degree 404, community 41 Community 41, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 294 nodes, 374 internal edges, density 0.0087; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, 150ca64 Reduce PMS request load and keep analytics facts fresh
  2. Community 1 - Community 1: 262 nodes, 417 internal edges, density 0.0122; top nodes: config.py, 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2
  3. Community 2 - Community 2: 242 nodes, 305 internal edges, density 0.0105; top nodes: bf4a21f Fix day 0 and day 1 hotel simulation findings, 0ddeb59 Fix day 2 hotel simulation findings (#114), 9a75a8e Merge pull request #99 from Maximo-Paulos/feature/operational-audit-cash-daily
  4. Community 3 - Community 3: 228 nodes, 1169 internal edges, density 0.0452; top nodes: ReservationSourceEnum, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 213 nodes, 375 internal edges, density 0.0166; top nodes: ed918c6 Make the whole app one visual system and fix what the e2e journeys exposed, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup, business-journey.spec.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
