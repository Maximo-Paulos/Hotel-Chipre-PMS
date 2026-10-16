# Resumen Graphify

Generado: 2026-10-16T19:58:14.602871+00:00
Commit: `56a22308d894c33c459605e9d8fa6ae49bb582e3`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15151 nodes, 45458 edges, 662 communities, density 0.0004, average degree 6.0007, undirected

Top hubs:
  1. Reservation (degree 551, community 4 Community 4, app/models/reservation.py)
  2. HotelConfiguration (degree 525, community 7 Community 7, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 442, community 7 Community 7, app/models/reservation.py)
  4. Base (degree 431, community 9 Community 9, app/database.py)
  5. Room (degree 404, community 7 Community 7, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 323 nodes, 495 internal edges, density 0.0095; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 284 nodes, 385 internal edges, density 0.0096; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  3. Community 2 - Community 2: 231 nodes, 967 internal edges, density 0.0364; top nodes: feature/secure-auth-marketing-release-20260926, codex/production-render-qa, codex/public-site-inquiries
  4. Community 3 - Community 3: 221 nodes, 1467 internal edges, density 0.0603; top nodes: RoomCategory, RoomStatusEnum, Company
  5. Community 4 - Community 4: 212 nodes, 901 internal edges, density 0.0403; top nodes: Reservation, Transaction, TransactionTypeEnum

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
