# Resumen Graphify

Generado: 2026-09-26T17:17:10.124144+00:00
Commit: `616a398f1ae1a203b2c6b98c0e7bc8c7d1151c2a`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11299 nodes, 29884 edges, 579 communities, density 0.0005, average degree 5.2897, undirected

Top hubs:
  1. Base (degree 378, community 2 Community 2, app/database.py)
  2. Reservation (degree 285, community 5 Community 5, app/models/reservation.py)
  3. HotelConfiguration (degree 267, community 4 Community 4, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 225, community 5 Community 5, app/models/reservation.py)
  5. Room (degree 212, community 5 Community 5, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 299 nodes, 484 internal edges, density 0.0109; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  2. Community 1 - Community 1: 215 nodes, 388 internal edges, density 0.0169; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts
  3. Community 2 - Community 2: 213 nodes, 459 internal edges, density 0.0203; top nodes: Base, Base, str
  4. Community 3 - Community 3: 202 nodes, 1127 internal edges, density 0.0555; top nodes: main, feature/secure-auth-marketing-release-20260926, codex/production-render-qa
  5. Community 4 - Community 4: 177 nodes, 398 internal edges, density 0.0256; top nodes: HotelConfiguration, AuditActionEnum, f45e8eb Implement Google onboarding and staff aliases

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
