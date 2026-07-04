# MCP servers & agentes especializados — setup

Instalado por el orquestador (2026-07-04). Cubre los MCP del stack (Supabase, Stripe, Render)
y los subagentes de desarrollo. **Ningún secreto vive en el repo**: `.mcp.json` referencia
variables de entorno que resolvés localmente.

---

## 1. Toolchain (ya instalado en esta Mac)
- **Python 3.12** en `.venv/` (via `uv`, en `~/.local/bin`). Correr backend: `.venv/bin/python ...`.
- **Node 20** en `~/.local/node`. Persistido en `~/.zshrc` (`export PATH="$HOME/.local/node/bin:$PATH"`).
- No hay brew ni Docker en la máquina.

Si abrís una terminal nueva, `~/.zshrc` ya deja `node`/`npx`/`uv` en el PATH. `.mcp.json` igual
llama a `npx` por ruta absoluta (`/Users/maximopaulos/.local/node/bin/npx`) para que funcione
aunque Claude Code se lance sin ese PATH.

---

## 2. MCP servers (`.mcp.json`, project-scoped)

Los tres se activan **solo cuando exportás sus credenciales** en el entorno desde donde arranca
Claude Code. Sin la variable, ese server simplemente no levanta (el resto sí).

Agregá esto a `~/.zshrc` (o a tu gestor de secretos) con valores reales:

```sh
# Supabase — Personal Access Token (Account > Access Tokens) + ref del proyecto
export SUPABASE_ACCESS_TOKEN="sbp_xxx"
export SUPABASE_PROJECT_REF="abcdefghijklmnop"   # el project-ref de tu URL de Supabase

# Stripe — usá una RESTRICTED key (rk_...), no la secreta sk_...
export STRIPE_SECRET_KEY="rk_live_xxx"           # o rk_test_xxx para probar

# Render — API key (Account Settings > API Keys)
export RENDER_API_KEY="rnd_xxx"
```

Después reiniciá Claude Code para que tome los MCP.

### Decisiones de seguridad tomadas (podés cambiarlas en `.mcp.json`)
- **Supabase corre en `--read-only`**: el MCP solo puede leer la base de producción. Si necesitás
  que ejecute migraciones/escrituras, quitá `--read-only` (con criterio — es la DB de prod).
- **Stripe pide clave restringida** (`rk_*`): el propio server lo recomienda. Creá una en
  https://docs.stripe.com/keys#create-restricted-api-keys con solo los permisos que uses.
- **Render es remoto** (`https://mcp.render.com/mcp`, Bearer). No corre nada local.

### Verificación
```sh
export PATH="$HOME/.local/node/bin:$PATH"
npx -y @supabase/mcp-server-supabase@latest --version   # -> 0.8.2
npx -y @stripe/mcp --api-key=$STRIPE_SECRET_KEY          # -> "✅ Stripe MCP Server running on stdio" (Ctrl-C)
```
Dentro de Claude Code, los tools aparecen como `mcp__supabase__*`, `mcp__stripe__*`, `mcp__render__*`.

---

## 3. Agentes de desarrollo especializados (`.claude/agents/`)

Subagentes con contexto del proyecto ya cargado. Invocá con el Task tool (o el orquestador
semanal puede spawnearlos por `agentType`):

| Agente | Rol | Modo |
| --- | --- | --- |
| `backend-engineer` | Endpoints, servicios, schemas, flujos de pago/reserva/caja | escribe + testea |
| `frontend-engineer` | React/TS/TanStack Query, views, forms | escribe + lint/tsc/build |
| `database-migrations` | Modelos SQLAlchemy + Alembic | escribe + verifica upgrade |
| `security-auditor` | Auth, multi-tenant, webhooks, secretos | solo lectura |
| `qa-testing` | Cobertura, regresiones, flaky, e2e | escribe tests + corre |
| `performance-analyst` | N+1, índices, paginación, bundle | solo lectura |
| `docs-writer` | README/docs/.env, drift, features nuevas | escribe docs |
| `architecture-reviewer` | Boundaries, duplicación, alineación con BR v72 | solo lectura |

Cada uno conoce el entorno macOS (venv, node en `~/.local/node`), las reglas de `AGENTS.md`
(routers finos, multi-tenant por `hotel_id`, dinero en `Decimal`, deny-by-default) y cómo validar.
