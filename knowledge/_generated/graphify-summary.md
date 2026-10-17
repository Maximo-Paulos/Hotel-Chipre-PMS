# Resumen Graphify

Generado: 2026-10-17T21:13:06.067779+00:00
Commit: `f85e793ef029489fcd9eea28f12fe3c75e861b7e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15689 nodes, 48257 edges, 698 communities, density 0.0004, average degree 6.1517, undirected

Top hubs:
  1. HotelConfiguration (degree 650, community 4 Community 4, app/models/hotel_config.py)
  2. Reservation (degree 632, community 0 Community 0, app/models/reservation.py)
  3. ReservationStatusEnum (degree 515, community 0 Community 0, app/models/reservation.py)
  4. Base (degree 448, community 9 Community 9, app/database.py)
  5. Room (degree 436, community 0 Community 0, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 291 nodes, 1457 internal edges, density 0.0345; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 252 nodes, 1425 internal edges, density 0.0451; top nodes: Company, ReservationSourceEnum, TransactionTypeEnum
  3. Community 2 - Community 2: 247 nodes, 315 internal edges, density 0.0104; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, 81a7ffe Fix hotel simulation day 0 and day 1 findings, 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback
  4. Community 3 - Community 3: 246 nodes, 430 internal edges, density 0.0143; top nodes: ed918c6 Make the whole app one visual system and fix what the e2e journeys exposed, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup, business-journey.spec.ts
  5. Community 4 - Community 4: 239 nodes, 1658 internal edges, density 0.0583; top nodes: HotelConfiguration, RoomCategory, Guest

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
