# Resumen Graphify

Generado: 2026-11-06T18:05:38.623924+00:00
Commit: `0a1b545f2aaf621b62058142d47d167b18ed7eab`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15675 nodes, 50070 edges, 829 communities, density 0.0004, average degree 6.3885, undirected

Top hubs:
  1. Reservation (degree 528, community 3 Community 3, app/models/reservation.py)
  2. HotelConfiguration (degree 512, community 7 Community 7, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 463, community 3 Community 3, app/models/reservation.py)
  4. Base (degree 451, community 9 Community 9, app/database.py)
  5. Room (degree 355, community 7 Community 7, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 508 nodes, 694 internal edges, density 0.0054; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], database.py, 9e4b357 Reduce PMS request load and complete simulation remediation
  2. Community 1 - Community 1: 464 nodes, 698 internal edges, density 0.0065; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 81a7ffe Fix hotel simulation day 0 and day 1 findings
  3. Community 2 - Community 2: 424 nodes, 7318 internal edges, density 0.0816; top nodes: codex/qa-findings-integration, codex/allocation-latest-query, codex/allocation-lock-errors
  4. Community 3 - Community 3: 284 nodes, 1656 internal edges, density 0.0412; top nodes: Reservation, ReservationStatusEnum, ReservationSourceEnum
  5. Community 4 - Community 4: 275 nodes, 422 internal edges, density 0.0112; top nodes: af78e58 Consolidate PMS scenario and quality work, ReservationDetailDrawer.tsx, edc799f Add FX payment currency and hotel-currency change flow (#130)

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-qa-findings-integration.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
