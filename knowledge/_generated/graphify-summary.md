# Resumen Graphify

Generado: 2026-11-09T18:13:21.595944+00:00
Commit: `feb513011e6c8d96d098e36ccfed980f20ba88a3`

`graphify summary .graphify/graph.json`:
```text
Graphify First-Hop Summary
Graph: 16187 nodes, 64364 edges, 1154 communities, density 0.0005, average degree 7.9526, undirected

Top hubs:
  1. useSession() (degree 77, community 34 Community 34, frontend/src/state/session.tsx)
  2. _client() (degree 61, community 19 Community 19, tests/test_rbac_sensitive_route_permissions.py)
  3. _close() (degree 61, community 19 Community 19, tests/test_rbac_sensitive_route_permissions.py)
  4. hasValidSession() (degree 59, community 64 Community 64, frontend/src/api/client.ts)
  5. apiFetch() (degree 56, community 219 Community 219, frontend/src/api/client.ts)

Key communities:
  1. Community 0 - Community 0: 492 nodes, 31766 internal edges, density 0.263; top nodes: edc799f Add FX payment currency and hotel-currency change flow (#130), 150ca64 Reduce PMS request load and keep analytics facts fresh, 56a2230 Merge pull request #127 from Maximo-Paulos/refactor/pms-efficiency-remediation
  2. Community 1 - Community 1: 217 nodes, 330 internal edges, density 0.0141; top nodes: BaseModel, laundry_vendor.py, cash_register.py
  3. Community 2 - Community 2: 183 nodes, 299 internal edges, density 0.018; top nodes: af78e58 Consolidate PMS scenario and quality work, d908400 Merge pull request #107 from Maximo-Paulos/fix/hotel-sim-day0-day1, bf4a21f Fix day 0 and day 1 hotel simulation findings
  4. Community 3 - Community 3: 106 nodes, 139 internal edges, density 0.025; top nodes: Base, ota_core.py, models.py
  5. Community 4 - Community 4: 99 nodes, 131 internal edges, density 0.027; top nodes: stock.ts, StockPage.tsx, EditStockItemModal.tsx

Next best action: Start with get_neighbors on "useSession()", then use query_graph for the user's specific question.
```
`graphify check-update .`:
```text
[graphify check-update] Graph state looks current for /private/tmp/hcpms-whatsapp-pilot-main.
```
Fuente técnica: `.graphify/`. Este artefacto no reemplaza `GRAPH_REPORT.md`.
