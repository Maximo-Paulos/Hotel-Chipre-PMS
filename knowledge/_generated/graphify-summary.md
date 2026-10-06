# Resumen Graphify

Generado: 2026-10-06T03:53:48.902984+00:00
Commit: `2ef0dd8f0c354b9a10c4f6e536072821d47a1b24`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13767 nodes, 44936 edges, 699 communities, density 0.0005, average degree 6.5281, undirected

Top hubs:
  1. Reservation (degree 464, community 6 Community 6, app/models/reservation.py)
  2. HotelConfiguration (degree 431, community 10 Community 10, app/models/hotel_config.py)
  3. Base (degree 408, community 3 Community 3, app/database.py)
  4. ReservationStatusEnum (degree 375, community 10 Community 10, app/models/reservation.py)
  5. Room (degree 338, community 8 Community 8, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 528 nodes, 827 internal edges, density 0.0059; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 6871292 Fix day 0 and day 1 simulation findings (#113)
  2. Community 1 - Community 1: 507 nodes, 7048 internal edges, density 0.0549; top nodes: codex/fix-ronda-2-week-simulation, fix/pms-save-read-latency, fix/pending-actions-bounded
  3. Community 2 - Community 2: 330 nodes, 576 internal edges, density 0.0106; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 241 nodes, 548 internal edges, density 0.0189; top nodes: Base, Base, OTAIntegrationService
  5. Community 4 - Community 4: 238 nodes, 460 internal edges, density 0.0163; top nodes: client.ts, session.tsx, SettingsHotelPage.tsx

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/ronda2-week-simulation/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
