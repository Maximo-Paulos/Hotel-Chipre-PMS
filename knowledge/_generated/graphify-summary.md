# Resumen Graphify

Generado: 2026-11-09T00:34:06.850622+00:00
Commit: `41f718c05edee36de84da4085d649e7b403ef8f7`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15985 nodes, 68225 edges, 804 communities, density 0.0005, average degree 8.5361, undirected

Top hubs:
  1. Reservation (degree 528, community 4 Community 4, app/models/reservation.py)
  2. HotelConfiguration (degree 512, community 10 Community 10, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 463, community 7 Community 7, app/models/reservation.py)
  4. Base (degree 452, community 6 Community 6, app/database.py)
  5. Room (degree 355, community 4 Community 4, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 743 nodes, 1153 internal edges, density 0.0042; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 449 nodes, 857 internal edges, density 0.0085; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  3. Community 2 - Community 2: 442 nodes, 24122 internal edges, density 0.2475; top nodes: 150ca64 Reduce PMS request load and keep analytics facts fresh, codex/qa-fixes-round-20261108, edc799f Add FX payment currency and hotel-currency change flow (#130)
  4. Community 3 - Community 3: 388 nodes, 811 internal edges, density 0.0108; top nodes: client.ts, session.tsx, SettingsHotelPage.tsx
  5. Community 4 - Community 4: 334 nodes, 1591 internal edges, density 0.0286; top nodes: Reservation, Room, RoomStatusEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-qa-fixes-round-20261108.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
