# Resumen Graphify

Generado: 2026-11-09T06:40:02.726251+00:00
Commit: `b4d2a10b6c0faa6a9c58d32dff3836a07ce7d045`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 16101 nodes, 73514 edges, 815 communities, density 0.0006, average degree 9.1316, undirected

Top hubs:
  1. Reservation (degree 533, community 4 Community 4, app/models/reservation.py)
  2. HotelConfiguration (degree 513, community 10 Community 10, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 468, community 4 Community 4, app/models/reservation.py)
  4. Base (degree 452, community 8 Community 8, app/database.py)
  5. Room (degree 356, community 7 Community 7, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 752 nodes, 1200 internal edges, density 0.0042; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 488 nodes, 29025 internal edges, density 0.2443; top nodes: 150ca64 Reduce PMS request load and keep analytics facts fresh, edc799f Add FX payment currency and hotel-currency change flow (#130), 56a2230 Merge pull request #127 from Maximo-Paulos/refactor/pms-efficiency-remediation
  3. Community 2 - Community 2: 455 nodes, 865 internal edges, density 0.0084; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 394 nodes, 801 internal edges, density 0.0103; top nodes: client.ts, session.tsx, SettingsHotelPage.tsx
  5. Community 4 - Community 4: 374 nodes, 2097 internal edges, density 0.0301; top nodes: Reservation, ReservationStatusEnum, ReservationSourceEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-stageshow-rooms-polish-6e9297.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
