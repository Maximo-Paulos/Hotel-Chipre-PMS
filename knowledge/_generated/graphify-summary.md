# Resumen Graphify

Generado: 2026-10-06T21:33:17.105098+00:00
Commit: `c76452d6a940e38e5f2d876a8c4923291292b3da`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13894 nodes, 46318 edges, 687 communities, density 0.0005, average degree 6.6673, undirected

Top hubs:
  1. Reservation (degree 499, community 1 Community 1, app/models/reservation.py)
  2. HotelConfiguration (degree 450, community 1 Community 1, app/models/hotel_config.py)
  3. Base (degree 409, community 7 Community 7, app/database.py)
  4. ReservationStatusEnum (degree 408, community 1 Community 1, app/models/reservation.py)
  5. Room (degree 369, community 1 Community 1, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 483 nodes, 7619 internal edges, density 0.0655; top nodes: codex/fix-ronda-2-week-simulation, fix/pms-save-read-latency, fix/pending-actions-bounded
  2. Community 1 - Community 1: 286 nodes, 1133 internal edges, density 0.0278; top nodes: Reservation, HotelConfiguration, ReservationStatusEnum
  3. Community 2 - Community 2: 264 nodes, 353 internal edges, density 0.0102; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, usePermissions.ts
  4. Community 3 - Community 3: 241 nodes, 1087 internal edges, density 0.0376; top nodes: Transaction, TransactionTypeEnum, TransactionStatusEnum
  5. Community 4 - Community 4: 240 nodes, 400 internal edges, density 0.0139; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
