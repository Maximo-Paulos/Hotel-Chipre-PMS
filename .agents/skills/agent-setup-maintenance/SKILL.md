---
name: agent-setup-maintenance
description: Mantiene roles, skills y hooks sincronizados y seguros.
---

# agent-setup-maintenance

Edita roles canónicos en `agent-ops/roles/`, ejecuta `scripts/agent_ops/render_agents.py --write --check` y sincroniza `.agents/skills` hacia Claude.

Valida TOML/Markdown, enlaces, discoverability y hooks deterministas. Conserva los roles existentes y evita copias divergentes.

Los hooks no pueden enviar secretos, modificar código silenciosamente, lanzar LLMs ni ejecutar QA cloud.
