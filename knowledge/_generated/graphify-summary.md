# Resumen Graphify

Generado: 2026-10-17T00:49:00.550711+00:00
Commit: `817c9d4b9bfd01848aee8f503daa69a53e367440`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15220 nodes, 45647 edges, 668 communities, density 0.0004, average degree 5.9983, undirected

Top hubs:
  1. Reservation (degree 555, community 15 Community 15, app/models/reservation.py)
  2. HotelConfiguration (degree 538, community 2 Community 2, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 442, community 15 Community 15, app/models/reservation.py)
  4. Base (degree 435, community 8 Community 8, app/database.py)
  5. Room (degree 408, community 12 Community 12, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 326 nodes, 502 internal edges, density 0.0095; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 293 nodes, 393 internal edges, density 0.0092; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  3. Community 2 - Community 2: 251 nodes, 1705 internal edges, density 0.0543; top nodes: HotelConfiguration, RoomCategory, RoomStatusEnum
  4. Community 3 - Community 3: 231 nodes, 967 internal edges, density 0.0364; top nodes: feature/secure-auth-marketing-release-20260926, codex/production-render-qa, codex/public-site-inquiries
  5. Community 4 - Community 4: 228 nodes, 853 internal edges, density 0.033; top nodes: Transaction, TransactionTypeEnum, TransactionStatusEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
