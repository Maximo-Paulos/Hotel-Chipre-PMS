# Resumen Graphify

Generado: 2026-10-12T06:02:18.266266+00:00
Commit: `150ca6456402a4215ed4fb378b00ac433f16947c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 14202 nodes, 48407 edges, 768 communities, density 0.0005, average degree 6.8169, undirected

Top hubs:
  1. Reservation (degree 530, community 1 Community 1, app/models/reservation.py)
  2. HotelConfiguration (degree 507, community 3 Community 3, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 457, community 1 Community 1, app/models/reservation.py)
  4. Room (degree 417, community 27 Community 27, app/models/room.py)
  5. Base (degree 412, community 5 Community 5, app/database.py)

Key communities:
  1. Community 0 - Community 0: 420 nodes, 677 internal edges, density 0.0077; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness
  2. Community 1 - Community 1: 253 nodes, 1326 internal edges, density 0.0416; top nodes: Reservation, ReservationStatusEnum, Transaction
  3. Community 2 - Community 2: 243 nodes, 442 internal edges, density 0.015; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 204 nodes, 1818 internal edges, density 0.0878; top nodes: HotelConfiguration, RoomCategory, Company
  5. Community 4 - Community 4: 198 nodes, 346 internal edges, density 0.0177; top nodes: BaseModel, auth.py, cash_register.py

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/combined-remediation-review/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
