# Resumen Graphify

Generado: 2026-10-06T04:24:25.160399+00:00
Commit: `73398218f9ac118df53ccfd5780322be688519a6`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13063 nodes, 40878 edges, 677 communities, density 0.0005, average degree 6.2586, undirected

Top hubs:
  1. Base (degree 403, community 2 Community 2, app/database.py)
  2. Reservation (degree 351, community 6 Community 6, app/models/reservation.py)
  3. HotelConfiguration (degree 332, community 11 Community 11, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 279, community 33 Community 33, app/models/reservation.py)
  5. Room (degree 253, community 13 Community 13, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 489 nodes, 6790 internal edges, density 0.0569; top nodes: codex/fix-ronda-2-week-simulation, fix/pms-save-read-latency, codex/day2-feedback
  2. Community 1 - Community 1: 392 nodes, 541 internal edges, density 0.0071; top nodes: database.py, config.py, main.py
  3. Community 2 - Community 2: 285 nodes, 670 internal edges, density 0.0166; top nodes: Base, Base, OTAIntegrationService
  4. Community 3 - Community 3: 281 nodes, 389 internal edges, density 0.0099; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, LocalizedDateField.tsx
  5. Community 4 - Community 4: 206 nodes, 359 internal edges, density 0.017; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /private/tmp/hotel-pms-save-read-latency.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
