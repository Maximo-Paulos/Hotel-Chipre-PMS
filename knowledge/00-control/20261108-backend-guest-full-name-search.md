---
kind: checkpoint
scope: project
status: confirmed
agent: backend-engineer
created_at: 2026-11-08T04:32:25Z
project: hotel-chipre-pms
code_sha: 062b7caf
---

# Búsqueda de huéspedes por nombre completo

## Hallazgo

La lista de huéspedes filtraba por nombre y apellido en columnas separadas. La búsqueda del nombre sintético completo no encontraba el registro aunque la interfaz promete buscar por nombre.

## Cambio y evidencia

- `app/services/guest_service.py` agrega el nombre completo al conjunto de campos consultados; la consulta conserva `hotel_id`.
- `tests/test_guest_full_name_search_postgres.py` verifica la frase completa con distinto uso de mayúsculas y dos hoteles sintéticos.
- La prueba falló antes del cambio y pasó después en PostgreSQL 16.15 aislado, perfil local `hcpms-codex-qa`, con efectos externos desactivados.
- Commit local de código: `062b7caf`.

## Validación y límites

- `ruff check --ignore UP017` pasó para los dos archivos del cambio. El chequeo normal sigue señalando UP017 preexistente en `guest_service.py:25`; `ruff format --check` también informa formato preexistente en otras líneas de ese servicio.
- Graphify no tenía `graph.json` al cargar el worktree; `graphify update . --scope all --no-description --no-label` lo reconstruyó localmente. El extractor no dispone de gramática para tres archivos Swift. La regeneración amplia de Graphify e inventarios se dejó fuera del commit funcional.
- La búsqueda cloud requiere retest después de integrar y desplegar este SHA.
