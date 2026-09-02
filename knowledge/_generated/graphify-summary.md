# Resumen Graphify

Generado: 2026-09-01T12:32:26.282009+00:00
Commit: `c50af40`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12189 nodes, 68837 edges, 461 communities, density 0.0009, average degree 11.2949, undirected

Top hubs:
  1. Reservation (degree 1322, community 4 Community 4, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1298, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1253, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 1147, community 0 Community 0, app/models/room.py)
  5. RoomCategory (degree 1022, community 14 Community 14, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 750 nodes, 3893 internal edges, density 0.0139; top nodes: ReservationStatusEnum, HotelConfiguration, Room
  2. Community 1 - Community 1: 627 nodes, 1266 internal edges, density 0.0065; top nodes: database.py, 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2
  3. Community 2 - Community 2: 460 nodes, 18732 internal edges, density 0.1774; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  4. Community 3 - Community 3: 411 nodes, 3095 internal edges, density 0.0367; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate
  5. Community 4 - Community 4: 368 nodes, 1281 internal edges, density 0.019; top nodes: Reservation, ReservationError, BillingAdjustment

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/worktrees/Hotel-Chipre-PMS-realtime-collaboration.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] graph.json built from 393ea8c but HEAD is c50af40
[graphify check-update] Run the graphify skill with --update to refresh semantic data.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
