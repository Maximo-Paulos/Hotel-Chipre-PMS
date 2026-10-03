# Resumen Graphify

Generado: 2026-10-02T23:25:38.417439+00:00
Commit: `68712923d80953a67de23672547156ceb5512e1e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12821 nodes, 35185 edges, 663 communities, density 0.0004, average degree 5.4887, undirected

Top hubs:
  1. Base (degree 403, community 2 Community 2, app/database.py)
  2. Reservation (degree 342, community 10 Community 10, app/models/reservation.py)
  3. HotelConfiguration (degree 325, community 8 Community 8, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 272, community 10 Community 10, app/models/reservation.py)
  5. Room (degree 249, community 10 Community 10, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 358 nodes, 532 internal edges, density 0.0083; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e14db5b Harden hotel operations, payments and privacy retention
  2. Community 1 - Community 1: 257 nodes, 575 internal edges, density 0.0175; top nodes: router.tsx, a585307 Implement PMS audit remediation workflows, d7e130f Merge the Hotels-PMS landing page rebuild
  3. Community 2 - Community 2: 243 nodes, 590 internal edges, density 0.0201; top nodes: Base, Base, str
  4. Community 3 - Community 3: 200 nodes, 1692 internal edges, density 0.085; top nodes: codex/day2-feedback, fix/day0-day1-final-patches, fix/day0-day1-simulation-feedback
  5. Community 4 - Community 4: 199 nodes, 754 internal edges, density 0.0383; top nodes: SecurityAuditLog, TransactionTypeEnum, Transaction

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/hotel-day2-feedback.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
