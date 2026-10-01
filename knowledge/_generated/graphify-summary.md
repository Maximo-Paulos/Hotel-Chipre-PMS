# Resumen Graphify

Generado: 2026-10-01T17:15:21.416985+00:00
Commit: `6361f7a1c40b602cd4fc8c4df3f8ef7720382177`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12239 nodes, 32422 edges, 625 communities, density 0.0004, average degree 5.2981, undirected

Top hubs:
  1. Base (degree 388, community 2 Community 2, app/database.py)
  2. Reservation (degree 320, community 5 Community 5, app/models/reservation.py)
  3. HotelConfiguration (degree 295, community 24 Community 24, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 249, community 22 Community 22, app/models/reservation.py)
  5. Room (degree 223, community 27 Community 27, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 253 nodes, 344 internal edges, density 0.0108; top nodes: database.py, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, 87a469f Merge pull request #92 from Maximo-Paulos/feature/realtime-hardening-and-i18n
  2. Community 1 - Community 1: 196 nodes, 255 internal edges, density 0.0133; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, reservation-charge-journey.spec.ts
  3. Community 2 - Community 2: 194 nodes, 434 internal edges, density 0.0232; top nodes: Base, Base, ExternalEffectsDisabled
  4. Community 3 - Community 3: 179 nodes, 966 internal edges, density 0.0606; top nodes: fix/hotel-sim-day0-day1, fix/operational-task-version-cache, main
  5. Community 4 - Community 4: 177 nodes, 297 internal edges, density 0.0191; top nodes: BaseModel, auth.py, cash_register.py

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/hotel-prod-day-20261001.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
