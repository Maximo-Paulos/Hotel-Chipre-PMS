# Vault operativo — Hotel Chipre PMS

Este directorio es el vault Obsidian versionado y la memoria curada del repositorio. Abrir `knowledge/` directamente como vault; no hay que sincronizar ni copiar notas a una ubicación externa.

Orden de lectura: `00-control/TASK_ROUTER.md` → context pack del rol → fuentes canónicas mínimas → artefactos reproducibles de `_generated/`. La jerarquía de verdad es runtime/configuración y código > tests > Graphify > documentación histórica.

Nunca guardar credenciales, cookies, OTPs, tokens, PII, screenshots privados o layouts de Obsidian. La configuración portable vive en `knowledge/.obsidian/`; cualquier `.obsidian/` en la raíz es sólo el workspace local de esta laptop y está ignorado por Git. Ejecutar `.venv/bin/python scripts/knowledge/generate_inventories.py` cuando cambien rutas, OpenAPI, migraciones o el grafo.
