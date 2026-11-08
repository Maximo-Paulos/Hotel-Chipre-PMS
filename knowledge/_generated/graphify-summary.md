# Resumen Graphify

Generado: 2026-11-08T20:36:22.635620+00:00
Commit: `8eb40c2c65521e2b9db4f85b2ad557b5b58f9ab8`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15963 nodes, 67376 edges, 806 communities, density 0.0005, average degree 8.4415, undirected

Top hubs:
  1. Reservation (degree 528, community 4 Community 4, app/models/reservation.py)
  2. HotelConfiguration (degree 512, community 10 Community 10, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 463, community 8 Community 8, app/models/reservation.py)
  4. Base (degree 452, community 7 Community 7, app/database.py)
  5. Room (degree 355, community 8 Community 8, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 696 nodes, 1077 internal edges, density 0.0045; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 453 nodes, 862 internal edges, density 0.0084; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  3. Community 2 - Community 2: 428 nodes, 23328 internal edges, density 0.2553; top nodes: 150ca64 Reduce PMS request load and keep analytics facts fresh, codex/allocation-history-localization-20261107, codex/allocation-latest-query
  4. Community 3 - Community 3: 378 nodes, 777 internal edges, density 0.0109; top nodes: client.ts, session.tsx, SettingsHotelPage.tsx
  5. Community 4 - Community 4: 359 nodes, 1829 internal edges, density 0.0285; top nodes: Reservation, ReservationError, ReservationSourceEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-qa-fixes-round-20261108.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
