# Resumen Graphify

Generado: 2026-10-01T21:43:59.957847+00:00
Commit: `377196c6ba076e14525c5bd79edfec7eab1f1c46`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 12489 nodes, 34649 edges, 648 communities, density 0.0004, average degree 5.5487, undirected

Top hubs:
  1. Base (degree 395, community 1 Community 1, app/database.py)
  2. Reservation (degree 372, community 13 Community 13, app/models/reservation.py)
  3. HotelConfiguration (degree 357, community 7 Community 7, app/models/hotel_config.py)
  4. ReservationStatusEnum (degree 302, community 15 Community 15, app/models/reservation.py)
  5. Room (degree 263, community 13 Community 13, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 295 nodes, 392 internal edges, density 0.009; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, google-invitation-access.spec.ts
  2. Community 1 - Community 1: 236 nodes, 565 internal edges, density 0.0204; top nodes: Base, Base, str
  3. Community 2 - Community 2: 220 nodes, 1141 internal edges, density 0.0474; top nodes: Company, Transaction, TransactionTypeEnum
  4. Community 3 - Community 3: 181 nodes, 303 internal edges, density 0.0186; top nodes: BaseModel, auth.py, cash_register.py
  5. Community 4 - Community 4: 177 nodes, 1274 internal edges, density 0.0818; top nodes: fix/day1-company-fx-routes, test/operational-prod-day-20261001, fix/hotel-sim-day0-day1

Next best action: Start with get_neighbors on "Base", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/.codex/worktrees/hotel-prod-day-20261001.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
