# Resumen Graphify

Generado: 2026-10-06T03:21:45.813655+00:00
Commit: `a2011b5157c5a8a4321b5373259cd273d66e4c9f`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13689 nodes, 44083 edges, 726 communities, density 0.0005, average degree 6.4406, undirected

Top hubs:
  1. Reservation (degree 444, community 3 Community 3, app/models/reservation.py)
  2. HotelConfiguration (degree 411, community 26 Community 26, app/models/hotel_config.py)
  3. Base (degree 408, community 2 Community 2, app/database.py)
  4. ReservationStatusEnum (degree 355, community 8 Community 8, app/models/reservation.py)
  5. Room (degree 318, community 7 Community 7, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 522 nodes, 7080 internal edges, density 0.0521; top nodes: codex/fix-ronda-2-week-simulation, fix/pending-actions-bounded, codex/day2-feedback
  2. Community 1 - Community 1: 419 nodes, 678 internal edges, density 0.0077; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 0ddeb59 Fix day 2 hotel simulation findings (#114)
  3. Community 2 - Community 2: 250 nodes, 561 internal edges, density 0.018; top nodes: Base, Base, OTAIntegrationService
  4. Community 3 - Community 3: 247 nodes, 1206 internal edges, density 0.0397; top nodes: Reservation, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 239 nodes, 397 internal edges, density 0.014; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
