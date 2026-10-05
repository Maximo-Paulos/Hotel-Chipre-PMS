# Resumen Graphify

Generado: 2026-10-05T00:20:29.590881+00:00
Commit: `7ff20e158e67b815acebe4eb117dd8f4d5238ff2`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12832 nodes, 36295 edges, 670 communities, density 0.0004, average degree 5.657, undirected

Top hubs:
  1. Base (degree 403, community 0 Community 0, app/database.py)
  2. Reservation (degree 344, community 9 Community 9, app/models/reservation.py)
  3. HotelConfiguration (degree 327, community 10 Community 10, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 273, community 36 Community 36, app/models/reservation.py)
  5. Room (degree 251, community 11 Community 11, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 270 nodes, 650 internal edges, density 0.0179; top nodes: Base, Base, OTAIntegrationService
  2. Community 1 - Community 1: 265 nodes, 586 internal edges, density 0.0168; top nodes: router.tsx, a585307 Implement PMS audit remediation workflows, d7e130f Merge the Hotels-PMS landing page rebuild
  3. Community 2 - Community 2: 257 nodes, 337 internal edges, density 0.0102; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, reservation-company-group-journey.spec.ts
  4. Community 3 - Community 3: 229 nodes, 332 internal edges, density 0.0127; top nodes: database.py, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, 0ddeb59 Fix day 2 hotel simulation findings (#114)
  5. Community 4 - Community 4: 203 nodes, 349 internal edges, density 0.017; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/postmerge-day2-fixes.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
