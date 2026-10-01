# Resumen Graphify

Generado: 2026-10-01T11:56:39.634861+00:00
Commit: `51738e1be471cca6ad6164adca7ec0af93bbf83c`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 13083 nodes, 39755 edges, 631 communities, density 0.0005, average degree 6.0774, undirected

Top hubs:
  1. HotelConfiguration (degree 555, community 14 Community 14, app/models/hotel_config.py)
  2. Reservation (degree 553, community 18 Community 18, app/models/reservation.py)
  3. ReservationStatusEnum (degree 472, community 14 Community 14, app/models/reservation.py)
  4. Base (degree 422, community 8 Community 8, app/database.py)
  5. SecurityAuditLog (degree 421, community 0 Community 0, app/models/security_audit_log.py)

Key communities:
  1. Community 0 - Community 0: 237 nodes, 1473 internal edges, density 0.0527; top nodes: SecurityAuditLog, HotelRoleVisibilityWindow, Permission
  2. Community 1 - Community 1: 232 nodes, 254 internal edges, density 0.0095; top nodes: bf4a21f Fix day 0 and day 1 hotel simulation findings, SettingsSecurityPage.tsx, MfaSettingsCard.tsx
  3. Community 3 - Community 3: 225 nodes, 615 internal edges, density 0.0244; top nodes: StaffInvitation, User, GoogleLoginDisabled
  4. Community 2 - Community 2: 225 nodes, 556 internal edges, density 0.0221; top nodes: fix/hotel-sim-day0-day1, main, 4e1faae feat(auth): harden hotel-scoped authorization
  5. Community 4 - Community 4: 208 nodes, 365 internal edges, density 0.017; top nodes: BaseModel, auth.py, Replace the public pricing table.      The landing page renders exactly what thi

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/hotel-sim-day0-day1/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
