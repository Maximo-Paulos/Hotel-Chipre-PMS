# Resumen Graphify

Generado: 2026-10-17T22:02:52.523268+00:00
Commit: `32cc441ec2c84cd1c48674aea33624d4ba671432`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15729 nodes, 48528 edges, 707 communities, density 0.0004, average degree 6.1705, undirected

Top hubs:
  1. HotelConfiguration (degree 661, community 7 Community 7, app/models/hotel_config.py)
  2. Reservation (degree 637, community 3 Community 3, app/models/reservation.py)
  3. ReservationStatusEnum (degree 515, community 3 Community 3, app/models/reservation.py)
  4. Base (degree 448, community 11 Community 11, app/database.py)
  5. Room (degree 441, community 3 Community 3, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 341 nodes, 494 internal edges, density 0.0085; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, 81a7ffe Fix hotel simulation day 0 and day 1 findings
  2. Community 1 - Community 1: 295 nodes, 521 internal edges, density 0.012; top nodes: f45e8eb Implement Google onboarding and staff aliases, 4e1faae feat(auth): harden hotel-scoped authorization, ed918c6 Make the whole app one visual system and fix what the e2e journeys exposed
  3. Community 2 - Community 2: 292 nodes, 404 internal edges, density 0.0095; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  4. Community 3 - Community 3: 287 nodes, 1266 internal edges, density 0.0308; top nodes: Reservation, ReservationStatusEnum, Room
  5. Community 4 - Community 4: 268 nodes, 429 internal edges, density 0.012; top nodes: config.py, 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] graph.json built from fa941f7 but HEAD is 32cc441
[graphify check-update] Run the graphify skill with --update to refresh semantic data.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
