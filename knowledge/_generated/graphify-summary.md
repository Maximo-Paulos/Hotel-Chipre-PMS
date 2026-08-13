# Resumen Graphify

Generado: 2026-08-13T22:45:57.329045+00:00
Commit: `46a90d5`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 9071 nodes, 39609 edges, 343 communities, density 0.001, average degree 8.7331, undirected

Top hubs:
  1. Reservation (degree 879, community 0 Community 0, app/models/reservation.py)
  2. ReservationStatusEnum (degree 875, community 0 Community 0, app/models/reservation.py)
  3. HotelConfiguration (degree 870, community 2 Community 2, app/models/hotel_config.py)
  4. Room (degree 716, community 0 Community 0, app/models/room.py)
  5. Guest (degree 686, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 444 nodes, 2339 internal edges, density 0.0238; top nodes: Reservation, ReservationStatusEnum, Room
  2. Community 1 - Community 1: 405 nodes, 5890 internal edges, density 0.072; top nodes: worktree-agent-af404149f1b835229, worktree-agent-aa90c760fab5d7651, codex/fix/full-functional-qa
  3. Community 2 - Community 2: 350 nodes, 1858 internal edges, density 0.0304; top nodes: HotelConfiguration, Transaction, TransactionTypeEnum
  4. Community 3 - Community 3: 332 nodes, 1489 internal edges, density 0.0271; top nodes: codex/feature/pms-e2e-scale-hardening, main, claude/feature/pms-roles-housekeeping-qa
  5. Community 4 - Community 4: 321 nodes, 487 internal edges, density 0.0095; top nodes: dc4b68a ojooooo, database.py, config.py

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Pending semantic updates in /Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-mobile-first.
[graphify check-update] graph was rebuilt by the fast git hook without descriptions/labels (.graphify_describe_pending)
[graphify check-update] Fill the batch-*.json / communities.json files and re-run `graphify update` to ingest.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
