# Resumen Graphify

Generado: 2026-10-05T06:29:32.892001+00:00
Commit: `0174f497cc615550c21ba5c78bac0b6893729c7b`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12941 nodes, 37595 edges, 666 communities, density 0.0004, average degree 5.8102, undirected

Top hubs:
  1. Base (degree 403, community 1 Community 1, app/database.py)
  2. Reservation (degree 376, community 3 Community 3, app/models/reservation.py)
  3. HotelConfiguration (degree 353, community 10 Community 10, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 305, community 19 Community 19, app/models/reservation.py)
  5. Room (degree 277, community 13 Community 13, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 256 nodes, 337 internal edges, density 0.0103; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, reservation-company-group-journey.spec.ts
  2. Community 1 - Community 1: 251 nodes, 568 internal edges, density 0.0181; top nodes: Base, Base, OTAIntegrationService
  3. Community 2 - Community 2: 216 nodes, 336 internal edges, density 0.0145; top nodes: ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, 0ddeb59 Fix day 2 hotel simulation findings (#114), 8da4739 Fix day 2 hotel simulation findings
  4. Community 3 - Community 3: 214 nodes, 1108 internal edges, density 0.0486; top nodes: Reservation, ReservationSourceEnum, TransactionTypeEnum
  5. Community 4 - Community 4: 196 nodes, 339 internal edges, density 0.0177; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/codex-pms-performance/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
