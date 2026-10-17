# Resumen Graphify

Generado: 2026-10-17T02:04:41.467189+00:00
Commit: `6022c36f40285209de120e78905ea486ec7a10c0`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15237 nodes, 45910 edges, 669 communities, density 0.0004, average degree 6.0261, undirected

Top hubs:
  1. Reservation (degree 568, community 14 Community 14, app/models/reservation.py)
  2. HotelConfiguration (degree 551, community 2 Community 2, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 455, community 14 Community 14, app/models/reservation.py)
  4. Base (degree 435, community 9 Community 9, app/database.py)
  5. Room (degree 408, community 2 Community 2, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 334 nodes, 514 internal edges, density 0.0092; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 293 nodes, 402 internal edges, density 0.0094; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  3. Community 2 - Community 2: 274 nodes, 1889 internal edges, density 0.0505; top nodes: HotelConfiguration, Room, RoomCategory
  4. Community 3 - Community 3: 231 nodes, 315 internal edges, density 0.0119; top nodes: 87a469f Merge pull request #92 from Maximo-Paulos/feature/realtime-hardening-and-i18n, ed9a72c Harden realtime sync, fix room-status/data bugs, add settings + i18n, d82558f Harden RBAC and add auditable privacy retention
  5. Community 4 - Community 4: 229 nodes, 1018 internal edges, density 0.039; top nodes: ReservationSourceEnum, Transaction, TransactionTypeEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
