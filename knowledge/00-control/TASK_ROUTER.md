# Router de tarea

Empieza por [`START-HERE.md`](START-HERE.md). Esta tabla evita cargar el repositorio o el vault completo: cada agente lee una sola nota de control y un solo context pack.

| Si la tarea trata de | Leer primero | Rol responsable |
| --- | --- | --- |
| API, reglas hoteleras, auth, pagos u OTAs | `10-context/backend.md` | backend-engineer |
| UI, rutas, formularios o estado cliente | `10-context/frontend.md` | frontend-engineer |
| Modelo, Alembic o aislamiento de datos | `10-context/database.md` | database-migrations |
| Contenedores, despliegue o previews | `10-context/devops-containers.md` | devops-containers |
| Seguridad o proveedores externos | `10-context/security.md` | security-auditor |
| Navegación real de preview cloud | `10-context/cloud-qa-user.md` | cloud-qa-user |
| Decisiones, métricas o prioridad | `10-context/product-ceo.md` | product-ceo |
| SEO o expansión de mercado | `10-context/geo-local-seo.md` / `geo-market-expansion.md` | agente GEO correspondiente |
| UX, accesibilidad o visualización | `10-context/ux-ui.md` / `data-visualization.md` | auditor correspondiente |
| Arquitectura/impacto de código | `10-context/knowledge-graph.md` | knowledge-graph-curator |
| Cierre, merge o incidente | `10-context/release-governor.md` | release-governor |

Antes de explorar en amplitud: leer el frontmatter del pack, comprobar `last_verified_commit`, ejecutar el comando Graphify mínimo indicado y abrir las fuentes enlazadas. Si el pack no cubre la tarea, actualizarlo con evidencia; no cargar todo el vault.

## Contrato de salida

Todo trabajo debe indicar `code_sha`, fuentes consultadas, validaciones ejecutadas, estado de certeza (`confirmed`, `inferred`, `historical` o `needs-verification`) y riesgos pendientes. Si la tarea cambia código, regenerar Graphify e inventarios; si cambia comportamiento visible, adjuntar evidencia QA cloud posterior al cambio. Un fallo o una evidencia incompleta bloquea el cierre.
