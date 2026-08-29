# Resumen Graphify

Generado: 2026-08-28T23:49:05.213704+00:00
Commit: `16e8a3e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11493 nodes, 63468 edges, 423 communities, density 0.001, average degree 11.0446, undirected

Top hubs:
  1. Reservation (degree 1157, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1146, community 6 Community 6, app/models/reservation.py)
  3. HotelConfiguration (degree 1129, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 976, community 7 Community 7, app/models/room.py)
  5. Guest (degree 881, community 10 Community 10, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 537 nodes, 2769 internal edges, density 0.0192; top nodes: Reservation, HotelConfiguration, Transaction
  2. Community 1 - Community 1: 431 nodes, 18093 internal edges, density 0.1953; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  3. Community 2 - Community 2: 426 nodes, 784 internal edges, density 0.0087; top nodes: database.py, config.py, main.py
  4. Community 3 - Community 3: 402 nodes, 2959 internal edges, density 0.0367; top nodes: CategoryPricing, DailyRate, ReservationChannelCodeEnum
  5. Community 4 - Community 4: 383 nodes, 740 internal edges, density 0.0101; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, dc4b68a ojooooo

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
