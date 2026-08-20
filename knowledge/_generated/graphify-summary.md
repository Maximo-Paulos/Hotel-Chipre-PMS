# Resumen Graphify

Generado: 2026-08-20T19:29:48.182529+00:00
Commit: `897b057`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 10177 nodes, 49801 edges, 383 communities, density 0.001, average degree 9.787, undirected

Top hubs:
  1. Reservation (degree 943, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 0 Community 0, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 719 nodes, 3948 internal edges, density 0.0153; top nodes: Reservation, ReservationStatusEnum, HotelConfiguration
  2. Community 1 - Community 1: 392 nodes, 12130 internal edges, density 0.1583; top nodes: feature/mobile-first-operations, feat/rbac-permission-metadata, feat/feat-temp-permission-grant
  3. Community 2 - Community 2: 390 nodes, 592 internal edges, density 0.0078; top nodes: database.py, dc4b68a ojooooo, main.py
  4. Community 3 - Community 3: 316 nodes, 1843 internal edges, density 0.037; top nodes: RoomCategory, ReservationSourceEnum, CategoryPricing
  5. Community 4 - Community 4: 284 nodes, 1458 internal edges, density 0.0363; top nodes: Transaction, TransactionTypeEnum, PaymentMethodEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-tech0022-auth-hardening.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
