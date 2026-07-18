# Patrones de tooling adoptados

Se adoptan patrones públicos, no configuraciones privadas de terceros:

- [Codex: custom agents, skills y hooks](https://learn.chatgpt.com/docs/customization/overview): roles especializados, skills bajo demanda y hooks deterministas.
- [Claude Code: subagents](https://code.claude.com/docs/en/sub-agents): responsabilidades delimitadas y contexto específico.
- [Claude Code: hooks](https://code.claude.com/docs/en/hooks): automatización local, observable y sin efectos ocultos.

Implementación local: roles canónicos en `agent-ops/roles/`, renderizados a `.claude/agents/` y `.codex/agents/`; skills canónicas en `.agents/skills/` y espejo verificado en `.claude/skills/`; hooks solamente recuerdan el contexto y validan paridad. Ningún hook transmite secretos, cambia código, ejecuta LLMs o inicia QA cloud.
