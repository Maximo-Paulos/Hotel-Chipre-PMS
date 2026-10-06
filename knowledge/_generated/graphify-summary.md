# Resumen Graphify

Generado: 2026-10-06T04:31:15.028083+00:00
Commit: `56072f64781d54576a7a5700f94f98a3702a03d7`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13798 nodes, 45092 edges, 720 communities, density 0.0005, average degree 6.536, undirected

Top hubs:
  1. Reservation (degree 468, community 5 Community 5, app/models/reservation.py)
  2. HotelConfiguration (degree 434, community 10 Community 10, app/models/hotel_config.py)
  3. Base (degree 408, community 3 Community 3, app/database.py)
  4. ReservationStatusEnum (degree 378, community 5 Community 5, app/models/reservation.py)
  5. Room (degree 339, community 10 Community 10, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 547 nodes, 872 internal edges, density 0.0058; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, database.py
  2. Community 1 - Community 1: 507 nodes, 7048 internal edges, density 0.0549; top nodes: codex/fix-ronda-2-week-simulation, fix/pms-save-read-latency, fix/pending-actions-bounded
  3. Community 2 - Community 2: 334 nodes, 584 internal edges, density 0.0105; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 253 nodes, 591 internal edges, density 0.0185; top nodes: Base, Base, str
  5. Community 4 - Community 4: 236 nodes, 410 internal edges, density 0.0148; top nodes: client.ts, router.tsx, session.tsx

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
