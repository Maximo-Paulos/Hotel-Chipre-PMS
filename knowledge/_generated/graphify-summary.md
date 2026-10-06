# Resumen Graphify

Generado: 2026-10-06T03:19:30.893267+00:00
Commit: `bf76e8c22174fb0f1904b57fe72b340fa9e1b278`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13045 nodes, 40702 edges, 659 communities, density 0.0005, average degree 6.2402, undirected

Top hubs:
  1. Base (degree 403, community 4 Community 4, app/database.py)
  2. Reservation (degree 351, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 332, community 11 Community 11, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 279, community 14 Community 14, app/models/reservation.py)
  5. Room (degree 253, community 7 Community 7, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 486 nodes, 6811 internal edges, density 0.0578; top nodes: fix/pms-save-read-latency, codex/day2-feedback, codex/fix-ronda-2-week-simulation
  2. Community 1 - Community 1: 295 nodes, 386 internal edges, density 0.0089; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, reservation-company-group-journey.spec.ts
  3. Community 2 - Community 2: 222 nodes, 325 internal edges, density 0.0132; top nodes: 6871292 Fix day 0 and day 1 simulation findings (#113), 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback, 712d6ee Fix simulation day 0 and day 1 findings
  4. Community 3 - Community 3: 209 nodes, 1057 internal edges, density 0.0486; top nodes: Reservation, ReservationSourceEnum, TransactionTypeEnum
  5. Community 4 - Community 4: 164 nodes, 301 internal edges, density 0.0225; top nodes: Base, Base, ota_core.py

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /private/tmp/hotel-pms-save-read-latency.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
