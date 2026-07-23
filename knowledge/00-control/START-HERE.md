# Memoria operativa — leer primero

Este es el punto de entrada para cualquier agente que trabaje en Hotel Chipre PMS. La memoria está dividida en dos capas:

- `knowledge/`: memoria curada, breve y orientada a decisiones.
- `.graphify/`: mapa técnico generado desde el código; se consulta sólo para impacto, dependencias y contexto mínimo.

No leer todo el vault ni todo Graphify. Seguir este flujo:

1. Leer esta nota y `TASK_ROUTER.md`.
2. Elegir un único pack en `knowledge/10-context/` según la tarea.
3. Verificar `last_verified_commit`, las fuentes canónicas y el comando `graphify_minimum` del frontmatter.
4. Ejecutar ese comando y abrir sólo las fuentes que el resultado señale.
5. Para cambios, validar el área, actualizar la nota mínima y registrar evidencia con el `code_sha`.

## Estado rápido al `71cb80e`

| Área | Estado | Evidencia mínima |
| --- | --- | --- |
| Código local y tests del setup | `confirmed` | scripts de `agent_ops`, tests previos y configuración versionada |
| Vault, roles y skills | `confirmed` | `scripts/agent_ops/validate_setup.py`, paridad de agentes y espejo de skills |
| Graphify AST/portabilidad | `confirmed` | `GRAPH_REPORT.md`, `portable-check`, `flows.json` |
| Producción pública | `confirmed` sólo para disponibilidad HTTP | `knowledge/_generated/cloud-surfaces.*` y comprobaciones públicas |
| Preview aislado Vercel + Render + Supabase | `needs-verification` | faltan proyecto QA, servicio QA y ciclo confiable real |
| QA humano de owner/manager/recepción/housekeeping/master-admin | `needs-verification` | requiere bootstrap sintético y catálogo completo en preview |

El sistema no se considera terminado mientras la última fila siga en `needs-verification`.

## Router rápido

| Necesidad | Pack |
| --- | --- |
| FastAPI, reservas, auth, pagos u OTAs | [`backend.md`](../10-context/backend.md) |
| React, rutas, formularios o UX de aplicación | [`frontend.md`](../10-context/frontend.md) |
| SQLAlchemy, Alembic o multi-tenancy | [`database.md`](../10-context/database.md) |
| Vercel, Render, Supabase, CI o previews | [`devops-containers.md`](../10-context/devops-containers.md) |
| Seguridad, roles, secretos o webhooks | [`security.md`](../10-context/security.md) |
| Navegación cloud como usuario real | [`cloud-qa-user.md`](../10-context/cloud-qa-user.md) |
| Producto, prioridad o decisión | [`product-ceo.md`](../10-context/product-ceo.md) |
| Graphify, impacto o arquitectura | [`knowledge-graph.md`](../10-context/knowledge-graph.md) |
| Cierre, evidencia o merge | [`release-governor.md`](../10-context/release-governor.md) |

## Fuentes y comandos

La verdad se resuelve en este orden: runtime/configuración y código → tests → Graphify fresco → vault histórico. Los estados permitidos son `confirmed`, `inferred`, `historical` y `needs-verification`; una inferencia no autoriza un cambio riesgoso.

Comandos de memoria y grafo:

```sh
.venv/bin/python scripts/agent_ops/check_knowledge.py
.venv/bin/python scripts/agent_ops/render_agents.py --check
.venv/bin/python scripts/agent_ops/sync_skills.py --check
graphify check-update .
graphify portable-check
```

Después de modificar código, migraciones o rutas:

```sh
graphify update . --scope all --no-description --no-label
graphify flows build
.venv/bin/python scripts/agent_ops/normalize_graphify_portability.py
graphify portable-check
graphify check-update .
.venv/bin/python scripts/knowledge/generate_inventories.py
```

Los inventarios reproducibles están en [`knowledge/_generated/`](../_generated/README.md): OpenAPI, rutas frontend, head de Alembic, superficies cloud y resumen Graphify. No copiar esos listados a notas curadas.

## Regla de cierre

Un agente puede terminar su implementación local sólo cuando el área está validada y documentada. El coordinador no puede marcar la tarea como finalizada si falta preview aislado saludable, regresión cloud completa con personas QA, evidencia posterior al último `code_sha` o revisión de seguridad. Nunca guardar contraseñas, tokens, cookies, OTPs, PII, capturas privadas o URLs secretas en esta vault.
