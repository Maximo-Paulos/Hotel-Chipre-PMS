# Resumen Graphify

Generado: 2026-10-06T03:33:18.943700+00:00
Commit: `d96fa5178d0e6bacdfc4517b992efad3bc0b002b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13693 nodes, 44250 edges, 694 communities, density 0.0005, average degree 6.4632, undirected

Top hubs:
  1. Reservation (degree 444, community 5 Community 5, app/models/reservation.py)
  2. HotelConfiguration (degree 411, community 3 Community 3, app/models/hotel_config.py)
  3. Base (degree 408, community 2 Community 2, app/database.py)
  4. ReservationStatusEnum (degree 355, community 5 Community 5, app/models/reservation.py)
  5. Room (degree 318, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 504 nodes, 7025 internal edges, density 0.0554; top nodes: codex/fix-ronda-2-week-simulation, fix/pms-save-read-latency, fix/pending-actions-bounded
  2. Community 1 - Community 1: 397 nodes, 612 internal edges, density 0.0078; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness
  3. Community 2 - Community 2: 255 nodes, 591 internal edges, density 0.0182; top nodes: Base, Base, str
  4. Community 3 - Community 3: 246 nodes, 726 internal edges, density 0.0241; top nodes: HotelConfiguration, Room, RoomCategory
  5. Community 4 - Community 4: 239 nodes, 397 internal edges, density 0.014; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
