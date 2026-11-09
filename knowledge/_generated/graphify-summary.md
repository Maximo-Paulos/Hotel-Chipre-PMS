# Resumen Graphify

Generado: 2026-11-09T16:49:16.366423+00:00
Commit: `cf6ef49f21888a45da98337c29d562b6337d9c0b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 16166 nodes, 76075 edges, 813 communities, density 0.0006, average degree 9.4117, undirected

Top hubs:
  1. Reservation (degree 535, community 3 Community 3, app/models/reservation.py)
  2. HotelConfiguration (degree 513, community 10 Community 10, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 470, community 6 Community 6, app/models/reservation.py)
  4. Base (degree 452, community 8 Community 8, app/database.py)
  5. Room (degree 356, community 6 Community 6, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 772 nodes, 1235 internal edges, density 0.0041; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 500 nodes, 31341 internal edges, density 0.2512; top nodes: edc799f Add FX payment currency and hotel-currency change flow (#130), 150ca64 Reduce PMS request load and keep analytics facts fresh, 56a2230 Merge pull request #127 from Maximo-Paulos/refactor/pms-efficiency-remediation
  3. Community 2 - Community 2: 463 nodes, 883 internal edges, density 0.0083; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 375 nodes, 1977 internal edges, density 0.0282; top nodes: Reservation, ReservationSourceEnum, TransactionTypeEnum
  5. Community 4 - Community 4: 349 nodes, 458 internal edges, density 0.0075; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, crossTabSync.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-pending-balance-extension-no-email.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
