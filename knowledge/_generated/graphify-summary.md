# Resumen Graphify

Generado: 2026-10-17T05:19:42.715107+00:00
Commit: `8ddc10dda4d6e660a49cf832a5b34b087d90d419`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15425 nodes, 46987 edges, 672 communities, density 0.0004, average degree 6.0923, undirected

Top hubs:
  1. HotelConfiguration (degree 605, community 5 Community 5, app/models/hotel_config.py)
  2. Reservation (degree 602, community 2 Community 2, app/models/reservation.py)
  3. ReservationStatusEnum (degree 484, community 44 Community 44, app/models/reservation.py)
  4. Base (degree 438, community 10 Community 10, app/database.py)
  5. Room (degree 431, community 4 Community 4, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 334 nodes, 514 internal edges, density 0.0092; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 295 nodes, 404 internal edges, density 0.0093; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  3. Community 2 - Community 2: 279 nodes, 1609 internal edges, density 0.0415; top nodes: Reservation, ReservationSourceEnum, TransactionTypeEnum
  4. Community 3 - Community 3: 239 nodes, 978 internal edges, density 0.0344; top nodes: feature/secure-auth-marketing-release-20260926, codex/production-render-qa, codex/public-site-inquiries
  5. Community 4 - Community 4: 230 nodes, 830 internal edges, density 0.0315; top nodes: Room, AuditActionEnum, RoomStatusEnum

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
