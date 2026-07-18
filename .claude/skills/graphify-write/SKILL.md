---
name: graphify-write
description: Actualiza y verifica Graphify después de cambios de código.
---

# graphify-write

Úsala después de modificar archivos de código, migraciones o rutas relevantes.

Ejecuta `graphify update . --scope all --no-description --no-label`, luego `graphify portable-check` y `graphify check-update`. Registra el resultado y el commit en el handoff o context pack afectado.

No introduzcas secretos, llamadas LLM ni exportaciones masivas de nodos al vault.
