# Resumen Graphify

Generado: 2026-10-05T05:14:13.290085+00:00
Commit: `72573a3408c6c7823ca900c50c34588bf998a9f7`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12921 nodes, 37324 edges, 659 communities, density 0.0004, average degree 5.7773, undirected

Top hubs:
  1. Base (degree 403, community 2 Community 2, app/database.py)
  2. Reservation (degree 376, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 353, community 10 Community 10, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 305, community 20 Community 20, app/models/reservation.py)
  5. Room (degree 277, community 14 Community 14, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 261 nodes, 564 internal edges, density 0.0166; top nodes: router.tsx, a585307 Implement PMS audit remediation workflows, d7e130f Merge the Hotels-PMS landing page rebuild
  2. Community 1 - Community 1: 252 nodes, 334 internal edges, density 0.0106; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, google-invitation-access.spec.ts
  3. Community 2 - Community 2: 249 nodes, 564 internal edges, density 0.0183; top nodes: Base, Base, OTAIntegrationService
  4. Community 3 - Community 3: 227 nodes, 294 internal edges, density 0.0115; top nodes: database.py, main.py, 5616166 Merge pull request #90 from Maximo-Paulos/feature/realtime-collaboration
  5. Community 4 - Community 4: 214 nodes, 1108 internal edges, density 0.0486; top nodes: Reservation, ReservationSourceEnum, TransactionTypeEnum

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/codex-pms-performance/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
