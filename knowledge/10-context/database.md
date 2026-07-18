---
scope: SQLAlchemy, Alembic, datos sintéticos y aislamiento multi-hotel
owner: database-migrations
last_verified_commit: 50abb05
canonical_sources: [app/models/, alembic/versions/, app/database.py, knowledge/_generated/migration-head.md]
graphify_minimum: graphify affected-flows app/models
required_validation: alembic upgrade head en base limpia + tests focales
---
# Context pack — Database

El dominio usa SQLAlchemy y Alembic. El aislamiento operativo se modela principalmente con `hotel_id` y el contexto autenticado; cada consulta nueva debe confirmar alcance de hotel explícitamente.

Toda migración debe ser forward/backward segura, con índices/constraints adecuados, y debe probarse sobre una base vacía aislada. Los previews nunca comparten datos de QA ni producción.
