# Resumen Graphify

Generado: 2026-10-12T22:23:08.311704+00:00
Commit: `7e0daf928027d69f425f5c1b91b4920621320d05`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 14204 nodes, 48585 edges, 676 communities, density 0.0005, average degree 6.841, undirected

Top hubs:
  1. Reservation (degree 530, community 2 Community 2, app/models/reservation.py)
  2. HotelConfiguration (degree 507, community 5 Community 5, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 457, community 2 Community 2, app/models/reservation.py)
  4. Room (degree 417, community 27 Community 27, app/models/room.py)
  5. Base (degree 412, community 6 Community 6, app/database.py)

Key communities:
  1. Community 0 - Community 0: 529 nodes, 7810 internal edges, density 0.0559; top nodes: fix/lock-paid-room-reservations, codex/day2-feedback, codex/fix-ronda-2-week-simulation
  2. Community 1 - Community 1: 260 nodes, 343 internal edges, density 0.0102; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, action_step_up_service.py
  3. Community 2 - Community 2: 248 nodes, 1346 internal edges, density 0.0439; top nodes: Reservation, ReservationStatusEnum, Transaction
  4. Community 3 - Community 3: 243 nodes, 442 internal edges, density 0.015; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  5. Community 4 - Community 4: 234 nodes, 492 internal edges, density 0.018; top nodes: HotelMembership, 6871292 Fix day 0 and day 1 simulation findings (#113), 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/combined-remediation-review/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
