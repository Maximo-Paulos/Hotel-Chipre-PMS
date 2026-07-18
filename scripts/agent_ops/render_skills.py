#!/usr/bin/env python3
"""Write the concise, shared Skill docs created through skill-creator.

The files remain canonical in .agents/skills.  This renderer only prevents
drift in their common metadata and is intentionally dependency-free.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = {
    "graphify-read": (
        "Lee el grafo técnico sin modificarlo.",
        """Usa esta skill para preguntas de arquitectura, dependencias, hotspots o impacto de código.

1. Lee `.graphify/GRAPH_REPORT.md` y ejecuta `graphify check-update`.
2. Si el grafo está fresco, usa sólo la consulta mínima: `summary`, `query`, `minimal-context` o `affected-flows`.
3. Marca toda conclusión con la frescura del grafo y distingue evidencia de inferencia.

No ejecutes `graphify update`, no exportes miles de nodos a Obsidian y no sustituyas la inspección del código cuando el grafo esté desactualizado.""",
    ),
    "graphify-load-context": (
        "Carga el mínimo contexto técnico para una tarea.",
        """Antes de editar código, lee el context pack indicado por `knowledge/00-control/TASK_ROUTER.md`.

Con el símbolo, archivo o flujo objetivo, usa `graphify minimal-context` o `graphify affected-flows`; complementa sólo con los archivos que el resultado señale. Confirma `graphify check-update` primero.

No cargues el repositorio entero ni conviertas el grafo en documentación duplicada.""",
    ),
    "graphify-write": (
        "Actualiza y verifica Graphify después de cambios de código.",
        """Úsala después de modificar archivos de código, migraciones o rutas relevantes.

Ejecuta `graphify update . --scope all --no-description --no-label`, luego `graphify portable-check` y `graphify check-update`. Registra el resultado y el commit en el handoff o context pack afectado.

No introduzcas secretos, llamadas LLM ni exportaciones masivas de nodos al vault.""",
    ),
    "obsidian-read": (
        "Lee memoria curada del vault sin cargarlo completo.",
        """Usa esta skill cuando la tarea dependa de decisiones, estado, operación o contexto del producto.

Parte de `knowledge/00-control/TASK_ROUTER.md`, abre sólo el pack asignado y sus fuentes canónicas enlazadas. Respeta los estados `confirmed`, `inferred`, `historical` y `needs-verification`.

El vault orienta el trabajo; el runtime/configuración y código vigente siguen teniendo prioridad.""",
    ),
    "obsidian-load-context": (
        "Selecciona el pack Obsidian correcto antes de trabajar.",
        """Para un agente generalista, consulta `knowledge/00-control/TASK_ROUTER.md`; para uno especializado, abre su `knowledge/10-context/*.md` preasignado.

Verifica el frontmatter, `last_verified_commit`, fuentes y validación indicada. Si está obsoleto, usa las fuentes canónicas y deja una nota de actualización.

No leas todo `knowledge/` ni uses notas históricas como evidencia actual.""",
    ),
    "obsidian-write": (
        "Actualiza memoria curada con evidencia trazable.",
        """Úsala cuando cambien comportamiento, arquitectura, decisiones, riesgos, operación o evidencia QA.

Actualiza la nota mínima necesaria, enlaza artefactos reproducibles de `knowledge/_generated/`, anota commit/fuentes/estado de certeza y conserva español claro. Nunca incluyas secretos, sesiones, PII, capturas privadas ni credenciales.

No copies el contenido masivo de Graphify o OpenAPI; enlázalo.""",
    ),
    "cloud-user-qa": (
        "Prueba un preview cloud como una persona usuaria real.",
        """Usa navegador visible y `.env.qa.local` ignorado; primero lee el catálogo y manifest de QA.

Recorre la matriz completa con owner, manager, recepción, housekeeping y master-admin usando selectores accesibles. Para cada fila registra URL de preview, precondición, acción humana, esperado, observado, evidencia y `code_sha` en `qa/evidence/<task-id>/`.

No accedas al correo, no pagues, no envíes emails, no dispares webhooks/OTAs y no toques datos de terceros. Un fallo, URL inaccesible o evidencia incompleta bloquea el cierre.""",
    ),
    "qa-persona-bootstrap": (
        "Prepara las cinco identidades QA sintéticas una única vez.",
        """Sigue `knowledge/30-operations/qa-personas-and-bootstrap.md`.

Crea únicamente hotel y usuarios sintéticos aislados; la verificación de correo la hace una persona mediante buzón dedicado. Master-admin usa variables Render separadas `MASTER_ADMIN_EMAIL`, `MASTER_ADMIN_PASSWORD`, `MASTER_ADMIN_PIN`.

Guarda sólo metadatos no sensibles. Nunca escribas contraseñas, cookies, OTPs, tokens ni capturas en Git o vault.""",
    ),
    "release-gate": (
        "Aplica la puerta de entrega antes de cerrar o fusionar.",
        """Comprueba validación local, paridad de agentes/skills, inventarios/vault, Graphify fresco, revisión de seguridad, preview aislado saludable y evidencia QA posterior al último cambio funcional.

Usa `knowledge/40-delivery/release-gates.md` y el verificador de evidencia. Si falta un requisito, declara el bloqueo con reproducción y no marques la tarea como terminada.

No reduzcas la matriz QA ni aceptes una base compartida como preview.""",
    ),
    "deploy-preview-check": (
        "Comprueba que un preview sea aislado y apunte al backend correcto.",
        """Antes de QA cloud, verifica manifest de preview, health del backend, `VITE_API_URL`, `FRONTEND_URL`, CORS y que cada preview use su `DATABASE_URL`/secrets QA aislados.

Lee `knowledge/20-system/cloud-and-deployment.md` y `knowledge/30-operations/cloud-surface-manifest.md`. Si Supabase Branches no está disponible, bloquea el preview y solicita una segunda base aislada.

No despliegues, rotes secretos ni modifiques proveedores desde esta skill.""",
    ),
    "secure-integration-review": (
        "Revisa límites de seguridad de integraciones externas.",
        """Traza autenticación, autorización, validación, secretos, webhooks, reintentos, PII y efectos externos en el cambio propuesto.

Exige configuración por entorno, verificación de firmas, logs redactados y pruebas de denegación. Evalúa pagos, OTAs, email y APIs de terceros con `knowledge/10-context/security.md`.

No pruebes pagos reales ni ejecutes efectos externos; documenta contratos o adapters usados.""",
    ),
    "ux-ui-audit": (
        "Audita UX/UI visible, accesibilidad y estados de error.",
        """Revisa el flujo real en navegador y el context pack `ux-ui.md`.

Comprueba jerarquía visual, feedback, carga/error/vacío, teclado/foco, etiquetas accesibles, contraste, responsive básico y consistencia de permisos. Aporta pasos y evidencia reproducible; separa defecto visual de defecto funcional.

No declares UX aprobada si el flujo no se recorrió con la persona adecuada.""",
    ),
    "product-ceo-review": (
        "Evalúa decisiones por valor de producto y riesgo operativo.",
        """Lee `knowledge/10-context/product-ceo.md`, personas, métricas y riesgos antes de priorizar.

Formula el problema, quién se beneficia, impacto en operación hotelera, métrica de éxito, costes/riesgos y decisión reversible. Mantén decisiones auditables en `DECISION-LOG.md`.

No redefine requisitos técnicos ni aprueba cambios críticos sin validación de seguridad y QA.""",
    ),
    "geo-market-expansion": (
        "Evalúa expansión geográfica y localización de mercado.",
        """Usa `geo-market-expansion.md` para analizar país/segmento, idioma, moneda, impuestos, pagos, canales, soporte y obligaciones operativas.

Separa hechos confirmados, investigación pendiente y supuestos. Propón experimentos reversibles y criterios de salida.

No habilites mercados, precios ni integraciones regulatorias sin aprobación y verificación especializada.""",
    ),
    "geo-local-seo": (
        "Revisa SEO local y superficies públicas por mercado.",
        """Audita rutas públicas, metadatos, canonicals, hreflang, schema, contenido local, rendimiento y conversiones según `geo-local-seo.md`.

Usa evidencia rastreable y conserva compatibilidad con el router/marketing actual. Valida enlaces y experiencia móvil.

No inventes claims, reviews, ubicaciones ni resultados de búsqueda.""",
    ),
    "data-visualization-review": (
        "Revisa gráficos y métricas para decisiones hoteleras claras.",
        """Contrasta cada visualización con la fuente de datos, periodo, zona horaria, filtros, unidades y permisos; usa `data-visualization.md`.

Exige estados vacíos/error, accesibilidad textual, escalas no engañosas y definiciones de métricas. Prueba como las personas que la consumen.

No certifiques un dashboard si sus totales no pueden reconciliarse con la fuente.""",
    ),
    "agent-setup-maintenance": (
        "Mantiene roles, skills y hooks sincronizados y seguros.",
        """Edita roles canónicos en `agent-ops/roles/`, ejecuta `scripts/agent_ops/render_agents.py --write --check` y sincroniza `.agents/skills` hacia Claude.

Valida TOML/Markdown, enlaces, discoverability y hooks deterministas. Conserva los roles existentes y evita copias divergentes.

Los hooks no pueden enviar secretos, modificar código silenciosamente, lanzar LLMs ni ejecutar QA cloud.""",
    ),
    "incident-triage": (
        "Triage seguro y reproducible de incidentes.",
        """Clasifica impacto, alcance, datos afectados, tiempo, evidencia y mitigación usando `incident-and-recovery.md`.

Preserva logs sin secretos, reproduce de forma controlada, propone mitigación reversible y registra decisiones. Escala de inmediato ante seguridad, pagos, integridad de reservas o exposición de PII.

No borres evidencia, no cambies producción sin autorización y no atribuyas causa sin prueba.""",
    ),
}


def main() -> None:
    for name, (description, body) in SKILLS.items():
        skill_dir = ROOT / ".agents" / "skills" / name
        skill_path = skill_dir / "SKILL.md"
        ui_path = skill_dir / "agents" / "openai.yaml"
        skill_path.write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{body}\n",
            encoding="utf-8",
        )
        ui_path.write_text(
            "interface:\n"
            f"  display_name: \"{name.replace('-', ' ').title()}\"\n"
            f"  short_description: \"{description}\"\n",
            encoding="utf-8",
        )
        print(skill_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
