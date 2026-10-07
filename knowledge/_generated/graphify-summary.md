# Resumen Graphify

Generado: 2026-10-07T08:27:42.758992+00:00
Commit: `3cfba65a783f6cbdca1022e952f1d53e72ba4741`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 14297 nodes, 48667 edges, 711 communities, density 0.0005, average degree 6.808, undirected

Top hubs:
  1. Reservation (degree 578, community 1 Community 1, app/models/reservation.py)
  2. HotelConfiguration (degree 535, community 2 Community 2, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 487, community 1 Community 1, app/models/reservation.py)
  4. Room (degree 440, community 13 Community 13, app/models/room.py)
  5. Base (degree 410, community 6 Community 6, app/database.py)

Key communities:
  1. Community 0 - Community 0: 254 nodes, 456 internal edges, density 0.0142; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  2. Community 1 - Community 1: 252 nodes, 1527 internal edges, density 0.0483; top nodes: Reservation, ReservationStatusEnum, Transaction
  3. Community 2 - Community 2: 217 nodes, 2357 internal edges, density 0.1006; top nodes: HotelConfiguration, RoomCategory, Company
  4. Community 3 - Community 3: 204 nodes, 321 internal edges, density 0.0155; top nodes: bf4a21f Fix day 0 and day 1 hotel simulation findings, 6871292 Fix day 0 and day 1 simulation findings (#113), 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback
  5. Community 4 - Community 4: 203 nodes, 355 internal edges, density 0.0173; top nodes: BaseModel, auth.py, cash_register.py

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
