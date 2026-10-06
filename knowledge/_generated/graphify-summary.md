# Resumen Graphify

Generado: 2026-10-06T15:36:03.369528+00:00
Commit: `4b7d260ebbde2f423f38a976e4d42b00f3393ec5`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13800 nodes, 45300 edges, 692 communities, density 0.0005, average degree 6.5652, undirected

Top hubs:
  1. Reservation (degree 468, community 6 Community 6, app/models/reservation.py)
  2. HotelConfiguration (degree 434, community 9 Community 9, app/models/hotel_config.py)
  3. Base (degree 408, community 3 Community 3, app/database.py)
  4. ReservationStatusEnum (degree 378, community 9 Community 9, app/models/reservation.py)
  5. Room (degree 339, community 8 Community 8, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 510 nodes, 805 internal edges, density 0.0062; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 6871292 Fix day 0 and day 1 simulation findings (#113)
  2. Community 1 - Community 1: 496 nodes, 7204 internal edges, density 0.0587; top nodes: codex/fix-ronda-2-week-simulation, fix/pms-save-read-latency, fix/pending-actions-bounded
  3. Community 2 - Community 2: 330 nodes, 576 internal edges, density 0.0106; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 250 nodes, 587 internal edges, density 0.0189; top nodes: Base, Base, str
  5. Community 4 - Community 4: 243 nodes, 352 internal edges, density 0.012; top nodes: database.py, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, 0ddeb59 Fix day 2 hotel simulation findings (#114)

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
