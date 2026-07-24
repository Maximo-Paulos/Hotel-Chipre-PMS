# Entorno de desarrollo y tooling — Hotel Chipre PMS

Setup profesional de la máquina de desarrollo (macOS) y de Claude Code. Última actualización: 2026-07-04.

---

## 1. Toolchain local (macOS, sin brew/Docker)
Instalado fuera del sistema para no depender de admin:

| Herramienta | Versión | Ubicación | Uso |
| --- | --- | --- | --- |
| Python | 3.12+ (via `uv`) | `.venv312/` or explicit `E2E_PYTHON` | `/path/to/python3.12 -m pytest -q` |
| Node | 20.19.6 | `~/.local/node/bin` | `export PATH="$HOME/.local/node/bin:$PATH"` |
| uv | 0.11.x | `~/.local/bin` | gestor de venvs/paquetes Python |
| gh CLI | 2.63.2 | `~/.local/bin/gh` | autenticado como Maximo-Paulos |
| Redis | 8.8.0 | `~/.local/bin` | `redis-server --daemonize yes` (opcional) |
| Playwright | chromium | `~/Library/Caches/ms-playwright` | e2e (`E2E_PYTHON=/path/to/python3.12 npm run e2e`) |
| Claude Code CLI | 2.1.x | `~/.local/node/bin/claude` | gestión de plugins/skills |
| graphify | 0.17.x | `~/.local/node/bin/graphify` | `graphify update .` → `.graphify/` |
| HTTPie | 3.2.4 | `.venv/bin/http` | pruebas de API |

PATH persistido en `~/.zshrc`. **No instalable sin admin**: Docker (no hace falta — deploy es Render/Vercel).

## 2. Claude Code — plugins (user scope, `~/.claude/`)
Instalados desde sus marketplaces oficiales con `claude plugin install`:

- **ponytail** v4.8.4 (`DietrichGebert/ponytail`) — "modo senior vago": fuerza la solución más simple que funciona (YAGNI, stdlib primero, sin abstracciones no pedidas). Aporta 6 skills (`ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`) y 3 hooks (SessionStart/SubagentStart/UserPromptSubmit). ~676 tok always-on.
- **caveman** (`JuliusBrussee/caveman`) — reduce ~65% de tokens "hablando como caveman"; hooks SessionStart/UserPromptSubmit + statusline. Activá con `/caveman` o "caveman mode"; medí con `/caveman-stats`.

Gestión: `claude plugin list`, `claude plugin details <n>`, `claude plugin disable <n>`, `claude plugin uninstall <n>`.

## 3. Claude Code — agentes de proyecto (`.claude/agents/`)
8 subagentes con contexto del proyecto (ver `docs/mcp-and-agents-setup.md`): backend-engineer, frontend-engineer, database-migrations, security-auditor, qa-testing, performance-analyst, docs-writer, architecture-reviewer.

## 4. Claude Code — skills de proyecto (`.claude/skills/`)
Workflows reales de este stack, con las rutas correctas:
- **validate-all** — puerta de validación pre-push (pytest + lint + tsc + build + migración dry-run).
- **new-migration** — crear/verificar una migración Alembic segura (multi-tenant, Numeric, sin NOT NULL sin default, reversible).
- **dev-up** — arrancar backend/frontend/redis local con venv y node correctos.

## 5. Claude Code — hooks
- **Proyecto** (`.claude/settings.json`): PreToolUse en Glob/Grep recuerda leer `.graphify/GRAPH_REPORT.md` antes de buscar en archivos crudos.
- **Global**: los que aportan ponytail y caveman (steering de contexto, harness-only, sin costo de contexto del modelo).

## 6. MCP servers (`.mcp.json`)
Supabase (read-only), Stripe, Render — esperan credenciales en env. Detalle en `docs/mcp-and-agents-setup.md`.

## 7. Repos de referencia
Clonados en `~/claude-reference/` (fuera del repo, no se commitean) para estudiar patrones:
`anthropics/skills`, `anthropics/claude-code`, `anthropics/claude-agent-sdk-python`, `anthropics/claude-cookbooks`, `openai/openai-cookbook`, `openai/openai-agents-python`, más los fuentes de `caveman` y `ponytail`.
> Nota: `openai-cookbook` pesa ~1.6 GB. Borralos con `rm -rf ~/claude-reference/<repo>` si necesitás espacio; no afectan al proyecto.
