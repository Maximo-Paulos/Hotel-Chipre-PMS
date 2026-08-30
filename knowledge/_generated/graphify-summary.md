# Resumen Graphify

Generado: 2026-08-29T23:59:06.930827+00:00
Commit: `666c024`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 11543 nodes, 64043 edges, 421 communities, density 0.001, average degree 11.0964, undirected

Top hubs:
  1. Reservation (degree 1166, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 1155, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 1138, community 13 Community 13, app/models/hotel_config.py)
  4. Room (degree 985, community 0 Community 0, app/models/room.py)
  5. Guest (degree 890, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 601 nodes, 3162 internal edges, density 0.0175; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 443 nodes, 836 internal edges, density 0.0085; top nodes: database.py, config.py, main.py
  3. Community 2 - Community 2: 431 nodes, 18089 internal edges, density 0.1952; top nodes: feat/tech0063-oltp-performance, feature/mobile-first-operations, feat/tech0111-secrets-audit
  4. Community 3 - Community 3: 406 nodes, 1866 internal edges, density 0.0227; top nodes: Transaction, TransactionTypeEnum, PaymentMethodEnum
  5. Community 4 - Community 4: 392 nodes, 752 internal edges, density 0.0098; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, dc4b68a ojooooo

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
