# Resumen Graphify

Generado: 2026-08-20T15:30:03.659553+00:00
Commit: `4ef3eca`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 9896 nodes, 44700 edges, 378 communities, density 0.0009, average degree 9.034, undirected

Top hubs:
  1. Reservation (degree 943, community 4 Community 4, app/models/reservation.py)
  2. ReservationStatusEnum (degree 939, community 4 Community 4, app/models/reservation.py)
  3. HotelConfiguration (degree 915, community 0 Community 0, app/models/hotel_config.py)
  4. Room (degree 769, community 0 Community 0, app/models/room.py)
  5. Guest (degree 725, community 0 Community 0, app/models/guest.py)

Key communities:
  1. Community 0 - Community 0: 422 nodes, 1875 internal edges, density 0.0211; top nodes: HotelConfiguration, Room, Guest
  2. Community 1 - Community 1: 415 nodes, 7868 internal edges, density 0.0916; top nodes: feature/mobile-first-operations, fix/rls-missing-tenant-tables, worktree-agent-af404149f1b835229
  3. Community 2 - Community 2: 383 nodes, 1999 internal edges, density 0.0273; top nodes: ReservationSourceEnum, CategoryPricing, DailyRate
  4. Community 3 - Community 3: 331 nodes, 626 internal edges, density 0.0115; top nodes: 8d88259 Merge pull request #29 from Maximo-Paulos/codex/fix/full-functional-qa, f1644f3 feat(security): fail-closed external effects, RBAC narrowing, QA catalog v2, config.py
  5. Community 4 - Community 4: 330 nodes, 1782 internal edges, density 0.0328; top nodes: Reservation, ReservationStatusEnum, Transaction

Next best action: Start with get_neighbors on "Reservation", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /Users/maximopaulos/AI-Workspace/projects/hcp-worktrees/feat-argon2id.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
