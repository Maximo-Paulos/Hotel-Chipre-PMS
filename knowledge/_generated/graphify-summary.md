# Resumen Graphify

Generado: 2026-11-09T19:36:53.894879+00:00
Commit: `6139bb5c778ed7a3d110f04b94f971cc2286dcdc`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 16193 nodes, 77330 edges, 806 communities, density 0.0006, average degree 9.551, undirected

Top hubs:
  1. Reservation (degree 535, community 3 Community 3, app/models/reservation.py)
  2. HotelConfiguration (degree 513, community 10 Community 10, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 470, community 7 Community 7, app/models/reservation.py)
  4. Base (degree 452, community 8 Community 8, app/database.py)
  5. Room (degree 356, community 7 Community 7, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 750 nodes, 1189 internal edges, density 0.0042; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, database.py
  2. Community 1 - Community 1: 507 nodes, 32438 internal edges, density 0.2529; top nodes: edc799f Add FX payment currency and hotel-currency change flow (#130), 56a2230 Merge pull request #127 from Maximo-Paulos/refactor/pms-efficiency-remediation, 150ca64 Reduce PMS request load and keep analytics facts fresh
  3. Community 2 - Community 2: 466 nodes, 886 internal edges, density 0.0082; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 362 nodes, 1903 internal edges, density 0.0291; top nodes: Reservation, ReservationSourceEnum, TransactionTypeEnum
  5. Community 4 - Community 4: 352 nodes, 462 internal edges, density 0.0075; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, collaboration.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-primary-checkin-20261109.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
