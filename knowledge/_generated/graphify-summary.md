# Resumen Graphify

Generado: 2026-09-27T04:43:19.204728+00:00
Commit: `7d81967d02b2887bf1baf3a823ee0c4f2b1c4561`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11403 nodes, 30291 edges, 579 communities, density 0.0005, average degree 5.3128, undirected

Top hubs:
  1. Base (degree 381, community 1 Community 1, app/database.py)
  2. Reservation (degree 291, community 21 Community 21, app/models/reservation.py)
  3. HotelConfiguration (degree 274, community 3 Community 3, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 229, community 21 Community 21, app/models/reservation.py)
  5. Room (degree 221, community 22 Community 22, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 197 nodes, 1105 internal edges, density 0.0572; top nodes: main, feature/secure-auth-marketing-release-20260926, codex/production-render-qa
  2. Community 1 - Community 1: 163 nodes, 294 internal edges, density 0.0223; top nodes: Base, Base, 8845d08 Fix eight real defects found auditing the whole project
  3. Community 2 - Community 2: 160 nodes, 274 internal edges, density 0.0215; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts
  4. Community 3 - Community 3: 154 nodes, 753 internal edges, density 0.0639; top nodes: HotelConfiguration, RoomCategory, RoomStatusEnum
  5. Community 4 - Community 4: 149 nodes, 219 internal edges, density 0.0199; top nodes: f45e8eb Implement Google onboarding and staff aliases, 4e1faae feat(auth): harden hotel-scoped authorization, ed918c6 Make the whole app one visual system and fix what the e2e journeys exposed

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
