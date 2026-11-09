# Resumen Graphify

Generado: 2026-11-09T05:27:30.723307+00:00
Commit: `344c23451537a9e3cbc05e97f212a78627f5881e`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 16142 nodes, 73937 edges, 815 communities, density 0.0006, average degree 9.1608, undirected

Top hubs:
  1. Reservation (degree 572, community 5 Community 5, app/models/reservation.py)
  2. HotelConfiguration (degree 543, community 6 Community 6, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 507, community 5 Community 5, app/models/reservation.py)
  4. Base (degree 452, community 10 Community 10, app/database.py)
  5. Room (degree 383, community 6 Community 6, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 742 nodes, 1180 internal edges, density 0.0043; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings
  2. Community 1 - Community 1: 491 nodes, 27991 internal edges, density 0.2327; top nodes: codex/allocation-post-timeout, 150ca64 Reduce PMS request load and keep analytics facts fresh, codex/qa-fixes-round-20261108
  3. Community 2 - Community 2: 446 nodes, 831 internal edges, density 0.0084; top nodes: ReservationsPage.tsx, reservations.ts, ReservationDetailDrawer.tsx
  4. Community 3 - Community 3: 391 nodes, 768 internal edges, density 0.0101; top nodes: client.ts, session.tsx, SettingsHotelPage.tsx
  5. Community 4 - Community 4: 334 nodes, 421 internal edges, density 0.0076; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, HousekeepingTodayPage.tsx

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /private/tmp/hcpms-qa-fixes-round-20261108.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
