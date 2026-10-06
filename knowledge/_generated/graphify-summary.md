# Resumen Graphify

Generado: 2026-10-06T16:44:24.711228+00:00
Commit: `e172ceb84dba26180f34ef2adad30df5d65ae21c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13072 nodes, 41318 edges, 679 communities, density 0.0005, average degree 6.3216, undirected

Top hubs:
  1. Base (degree 403, community 3 Community 3, app/database.py)
  2. Reservation (degree 352, community 6 Community 6, app/models/reservation.py)
  3. HotelConfiguration (degree 333, community 10 Community 10, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 280, community 34 Community 34, app/models/reservation.py)
  5. Room (degree 254, community 12 Community 12, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 480 nodes, 7128 internal edges, density 0.062; top nodes: codex/fix-ronda-2-week-simulation, codex/day2-feedback, codex/postmerge-day2-fixes
  2. Community 1 - Community 1: 339 nodes, 509 internal edges, density 0.0089; top nodes: database.py, config.py, 958fce2 Merge pull request #31 from Maximo-Paulos/feature/mobile-first-operations
  3. Community 2 - Community 2: 295 nodes, 400 internal edges, density 0.0092; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, LocalizedDateField.tsx
  4. Community 3 - Community 3: 280 nodes, 665 internal edges, density 0.017; top nodes: Base, Base, OTAIntegrationService
  5. Community 4 - Community 4: 219 nodes, 329 internal edges, density 0.0138; top nodes: 6871292 Fix day 0 and day 1 simulation findings (#113), 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback, 712d6ee Fix simulation day 0 and day 1 findings

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/pms-latency-retest.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
