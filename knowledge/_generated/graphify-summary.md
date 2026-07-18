# Resumen Graphify

Generado: 2026-07-18T16:03:47.906809+00:00
Commit: `50abb05`

`graphify summary .`:
```text
Graphify First-Hop Summary
Graph: 5519 nodes, 17071 edges, 281 communities, density 0.0011, average degree 6.1863, undirected

Top hubs:
  1. ReservationStatusEnum (degree 398, community 7 Community 7, app/models/reservation.py)
  2. Reservation (degree 393, community 5 Community 5, app/models/reservation.py)
  3. HotelConfiguration (degree 337, community 9 Community 9, app/models/hotel_config.py)
  4. Base (degree 303, community 4 Community 4, app/database.py)
  5. Room (degree 301, community 5 Community 5, app/models/room.py)

Key communities:
  1. Community 0 - Community 0: 191 nodes, 628 internal edges, density 0.0346; top nodes: main, chore/weekly-orchestrator-2026-07-03, codex/feature/agent-ops-knowledge
  2. Community 1 - Community 1: 178 nodes, 248 internal edges, density 0.0157; top nodes: dc4b68a ojooooo, main.py, e34785c prueba
  3. Community 2 - Community 2: 143 nodes, 639 internal edges, density 0.0629; top nodes: TransactionTypeEnum, PaymentMethodEnum, Transaction
  4. Community 3 - Community 3: 128 nodes, 171 internal edges, density 0.021; top nodes: database.py, e202fdd feat(db): v72 gaps phase 1+2 — Numeric precision, new tables, search indexes, OTA dedup, c580b56 ojala si
  5. Community 4 - Community 4: 123 nodes, 211 internal edges, density 0.0281; top nodes: Base, Base, PaymentLink

Next best action: Start with get_neighbors on "ReservationStatusEnum", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/Desktop/Hotel-Chipre-PMS.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Run `graphify update --fill-missing` to add descriptions + salient labels.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
