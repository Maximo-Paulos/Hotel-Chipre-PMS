# Resumen Graphify

Generado: 2026-10-16T20:52:53.087539+00:00
Commit: `532a3524b6393739737cc6c18b97524d7a0e8a78`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15152 nodes, 45467 edges, 677 communities, density 0.0004, average degree 6.0015, undirected

Top hubs:
  1. Reservation (degree 551, community 3 Community 3, app/models/reservation.py)
  2. HotelConfiguration (degree 525, community 9 Community 9, app/models/hotel_config.py)
  3. ReservationStatusEnum (degree 442, community 9 Community 9, app/models/reservation.py)
  4. Base (degree 431, community 8 Community 8, app/database.py)
  5. Room (degree 404, community 9 Community 9, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 324 nodes, 497 internal edges, density 0.0095; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 291 nodes, 393 internal edges, density 0.0093; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  3. Community 2 - Community 2: 221 nodes, 1467 internal edges, density 0.0603; top nodes: RoomCategory, RoomStatusEnum, Company
  4. Community 3 - Community 3: 212 nodes, 901 internal edges, density 0.0403; top nodes: Reservation, Transaction, TransactionTypeEnum
  5. Community 4 - Community 4: 212 nodes, 298 internal edges, density 0.0133; top nodes: 81a7ffe Fix hotel simulation day 0 and day 1 findings, 6871292 Fix day 0 and day 1 simulation findings (#113), e14db5b Harden hotel operations, payments and privacy retention

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
