# Resumen Graphify

Generado: 2026-10-17T03:05:39.828552+00:00
Commit: `f399380b0fdafc98ee5a91bc848d0983e9249b3a`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 15362 nodes, 46707 edges, 673 communities, density 0.0004, average degree 6.0808, undirected

Top hubs:
  1. HotelConfiguration (degree 599, community 13 Community 13, app/models/hotel_config.py)
  2. Reservation (degree 591, community 2 Community 2, app/models/reservation.py)
  3. ReservationStatusEnum (degree 478, community 2 Community 2, app/models/reservation.py)
  4. Base (degree 438, community 9 Community 9, app/database.py)
  5. Room (degree 431, community 26 Community 26, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 334 nodes, 514 internal edges, density 0.0092; top nodes: d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings, e752208 Merge pull request #115 from Maximo-Paulos/fix/day2-runtime-followup
  2. Community 1 - Community 1: 295 nodes, 404 internal edges, density 0.0093; top nodes: ef0aa41 Merge PR #125: week-two remediation [skip render], 9e4b357 Reduce PMS request load and complete simulation remediation, d96fa51 Fix week two hotel simulation failures
  3. Community 2 - Community 2: 233 nodes, 1000 internal edges, density 0.037; top nodes: Reservation, ReservationStatusEnum, AuditActionEnum
  4. Community 3 - Community 3: 225 nodes, 956 internal edges, density 0.0379; top nodes: TransactionTypeEnum, Transaction, TransactionStatusEnum
  5. Community 4 - Community 4: 224 nodes, 976 internal edges, density 0.0391; top nodes: feature/secure-auth-marketing-release-20260926, codex/production-render-qa, codex/public-site-inquiries

Next best action: Start with get_neighbors on "HotelConfiguration", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
