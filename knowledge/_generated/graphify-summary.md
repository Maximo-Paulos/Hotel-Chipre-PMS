# Resumen Graphify

Generado: 2026-10-01T01:42:29.347324+00:00
Commit: `24957e5a4d018b451ab7b27bd072431e91450bf9`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12669 nodes, 36990 edges, 645 communities, density 0.0005, average degree 5.8395, undirected

Top hubs:
  1. HotelConfiguration (degree 486, community 1 Community 1, app/models/hotel_config.py)
  2. Reservation (degree 486, community 14 Community 14, app/models/reservation.py)
  3. Base (degree 413, community 9 Community 9, app/database.py)
  4. ReservationStatusEnum (degree 407, community 14 Community 14, app/models/reservation.py)
  5. SecurityAuditLog (degree 397, community 13 Community 13, app/models/security_audit_log.py)

Key communities:
  1. Community 0 - Community 0: 251 nodes, 567 internal edges, density 0.0181; top nodes: router.tsx, a585307 Implement PMS audit remediation workflows, d7e130f Merge the Hotels-PMS landing page rebuild
  2. Community 1 - Community 1: 240 nodes, 961 internal edges, density 0.0335; top nodes: HotelConfiguration, Transaction, TransactionTypeEnum
  3. Community 2 - Community 2: 200 nodes, 2204 internal edges, density 0.1108; top nodes: AuditActionEnum, PaymentError, ReservationOperationsError
  4. Community 3 - Community 3: 195 nodes, 339 internal edges, density 0.0179; top nodes: ReservationsPage.tsx, reservations.ts, useReservations.ts
  5. Community 4 - Community 4: 194 nodes, 1761 internal edges, density 0.0941; top nodes: RoomCategory, Room, Guest

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/hotel-sim-day0-day1/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
