---
scope: analítica, gráficos, filtros, métricas y accesibilidad de datos
owner: data-visualization
last_verified_commit: 71cb80e
canonical_sources: [frontend/src/views/protected/analytics/, app/api/analytics.py, app/services/analytics_service.py]
graphify_minimum: graphify affected-flows --files app/api/analytics.py
required_validation: reconciliación de métrica + filtros + permisos + estado vacío/error
---
# Context pack — Visualización de datos

Cada gráfico debe declarar fuente, rango, zona horaria, filtros, unidad y permiso. Validar que totales concilien con datos de origen y que el significado sobreviva a un lector de pantalla o estado vacío.
