# Orchestrator Status — Hotel Chipre PMS

Registro vivo del orquestador técnico semanal. Cada sesión agrega una entrada arriba.
Complementa (no reemplaza) a `docs/roadmap.md`, `docs/business-requirements-master-v72.md` y `AGENTS.md`.

---

## Sesión 2026-07-03/04 — Auditoría semanal #1 (post-migración a macOS)

### Contexto
Primera corrida del orquestador semanal después de migrar el repo de Windows
(`C:\PROJECTO\Hotel-Chipre-PMS`) a macOS (`~/Desktop/Hotel-Chipre-PMS`).
Branch de trabajo: `chore/weekly-orchestrator-2026-07-03`.

### Estado general
- **Backend**: 749 tests pasando (2 estaban rotos por la migración/regla BR; corregidos en esta sesión), 16 skipped, 12 xfailed. Suite corre en ~100 s con Python 3.12.
- **Frontend**: ESLint 0 warnings, `tsc --noEmit` limpio, build Vite OK (1.14 s).
- **Migraciones**: cadena Alembic lineal y completa; `alembic upgrade head` sobre SQLite virgen termina sin errores en `20260626_repair_reservation_unique_constraint`.
- **Seguridad**: `validate_runtime_security()` en `app/config.py` hace fail-closed en producción para JWT débil, PIN default, Fernet key bundled y URLs no-https. Los defaults inseguros (`MASTER_ADMIN_PIN=1234`) son solo dev, por diseño.

### Toolchain local (macOS) — decisión técnica
- La máquina no tenía Python 3.11+, Node, npm, brew ni Docker.
- Se instaló **uv** en `~/.local/bin` (sin tocar el perfil del shell) y se creó `.venv/` con **Python 3.12.13**; `requirements.txt` instala completo sin conflictos.
- Se instaló **Node 20.19.6 standalone** en `~/.local/node` (agregar `~/.local/node/bin` al PATH para npm).
- `graphify` CLI **no está instalado** en esta máquina → `graphify update .` no se puede correr; el grafo en `graphify-out/` quedó congelado al 2026-06-27 (aún con rutas `C:\`). Regenerarlo cuando se reinstale la CLI.

### Bugs encontrados y corregidos
1. `tests/test_datastores_health.py` — subprocess con `cwd="C:\\PROJECTO\\Hotel-Chipre-PMS"` hardcodeado (bug de migración). Fix: root del repo derivado con `Path(__file__)`.
2. `tests/test_api_scaffolding.py::test_booking_status_and_overlap` — el test forzaba `status=FULLY_PAID` sin registrar pago; la regla BR de checkout (commit `bed8c5c`) rechaza checkout con saldo pendiente (HTTP 400, con `force` como escape). El test quedó desactualizado respecto del cambio intencional; ahora también salda `amount_paid`.
3. `app/adapters/rate_limiter.py` — `datetime.utcnow()` deprecado (Python 3.12) reemplazado por equivalente naive-UTC explícito, sin cambio de semántica.

### Limpieza aplicada
- Destrackeados de git: logs viejos (`backend.err`, `backend.local.err`, `frontend.err`, `frontend/frontend.local.err`, `pytest-full.out`), gitlinks rotos de submodules inexistentes (`graphify_repo`, dos worktrees bajo `.claude/worktrees/`) y **backups de DB de desarrollo** (`backups/*.backup` — posible PII de huéspedes; los archivos siguen en disco, solo salen de git).
- `.gitignore` ampliado: `*.err`, `pytest-full.out`, `backups/`, `.claude/worktrees/`.
- Borrados del disco: worktrees huérfanos (limpios, mismo commit que main) y logs `.err`.

### Documentación actualizada
- `CLAUDE.md`: vault de Windows marcado como histórico; instrucciones de entorno macOS; referencias apuntan a este archivo (que antes no existía).
- `README.md`: paso de activación de venv ahora cubre macOS/Linux y Windows.
- `.env.example`: +45 variables que `app/config.py` soporta y no estaban documentadas (JWT avanzado, master admin, datastores opcionales, read-model cache, OTA URLs, identidad del hotel); `ANALYTICS_EXPORTS_DIR` dejó de apuntar a una ruta `C:\`.

### Tooling agregado (2026-07-04, a pedido)
- **MCP servers del stack** en `.mcp.json` (sin secretos, con `${VAR}`): `supabase` (`@supabase/mcp-server-supabase` en read-only), `stripe` (`@stripe/mcp` — corregido: v0.3.3 solo acepta `--api-key`, no `--tools`), `render` (remoto `https://mcp.render.com/mcp`). Ambos paquetes npm verificados y con arranque probado. Falta que el usuario exporte `SUPABASE_ACCESS_TOKEN`/`SUPABASE_PROJECT_REF`, `STRIPE_SECRET_KEY` (usar `rk_*`), `RENDER_API_KEY`.
- **8 subagentes especializados** en `.claude/agents/` (backend, frontend, database-migrations, security-auditor, qa-testing, performance-analyst, docs-writer, architecture-reviewer), con contexto del proyecto y del entorno macOS.
- **PATH persistido** en `~/.zshrc` (node + uv). Guía: `docs/mcp-and-agents-setup.md`.
- **graphify reinstalado** (`@sentropic/graphify` v0.17.x en `~/.local/node/bin/graphify`). Grafo regenerado con rutas macOS (5448 nodos, 263 comunidades) en `.graphify/`; el layout viejo `graphify-out/` (34MB, rutas `C:\`, 917 archivos trackeados) se eliminó. Hook y docs repunteados a `.graphify/`. Solo se commitea el core portable del grafo; el estado local (cache, instrucciones, worktree/branch json) va gitignoreado.
- **gh CLI** v2.63.2 en `~/.local/bin/gh` — **autenticado** como Maximo-Paulos; git usa gh como credential helper. Rama pusheada y **PR #20 abierto** (https://github.com/Maximo-Paulos/Hotel-Chipre-PMS/pull/20).
- **HTTPie** en el venv (`.venv/bin/http`), prereq del README.
- **Redis 8.8.0** compilado desde fuente e instalado en `~/.local/bin` (server + cli). Smoke-test OK. Levantar con `redis-server --daemonize yes`.
- **Playwright chromium** instalado. Para e2e (`npm run e2e`) activar el venv primero (`source .venv/bin/activate`); el webServer usa `python scripts/serve_e2e_backend.py`.
- **No instalable sin admin/sudo** (documentado, no bloqueante): Docker (deploy compose), servidores Mongo/Cassandra/Neo4j (opcionales, off por defecto; drivers Python presentes).

### Deuda técnica pendiente (priorizada)
1. **Naive vs aware datetimes**: `RateLimitEvent.created_at` usa default timezone-aware pero columnas `DateTime` sin timezone y comparaciones naive. Quedan ~11 usos de `utcnow()` en `app/`. Unificar criterio (naive-UTC en todo o `DateTime(timezone=True)` en todo) — riesgo bajo hoy, molesto de arrastrar.
2. **Bundle frontend único de 755 kB** (gzip 182 kB): sin code-splitting. Separar vendor chunks / lazy routes con `manualChunks` o `React.lazy`.
3. **Serialización Decimal→float**: warnings de Pydantic (`Expected float but got Decimal`) en schemas de reservas — los montos deberían declararse `Decimal` en los schemas de lectura.
4. **Deprecaciones**: Pydantic class-based `Config` (migrar a `ConfigDict`), `pytest-asyncio` sin `asyncio_default_fixture_loop_scope`, passlib usa `crypt` (removido en Python 3.13 — bloquea upgrade futuro).
5. **Historial de git contiene backups de DB** (`backups/*.backup` en commits viejos). Si esos dumps tienen datos reales de huéspedes, evaluar reescritura de historial antes de abrir el repo.
6. **`graphify-out/` desactualizado** (2026-06-27, rutas Windows).

### Riesgos abiertos
- **Límite de sesión del plan** cortó la corrida multi-agente **dos veces** (intento 1: ~755k tokens, 39 min; intento 2 tras el reset: ~763k tokens en 4 min — la cuota restante no alcanzaba para un fan-out de 9 agentes). La auditoría profunda por agentes quedó **pendiente**; script del workflow guardado en la sesión (`weekly-orchestrator-audit-wf_be237abb-7f4.js`). Esta sesión cubrió lo equivalente con auditoría directa del orquestador, pero con menor profundidad por área.
  - **Lección para la próxima corrida**: lanzar el workflow al inicio de una ventana de cuota fresca, o por etapas (2-3 agentes por vez) en vez de 9 simultáneos.
  - Corroborado por el agente de DB antes de morir: cadena de migraciones con un solo head y merges resueltos (coincide con la validación local de `alembic upgrade head`).
- El agente de seguridad alcanzó a señalar como foco: verificación de firma de webhooks Stripe y secretos de webhooks OTA — **verificar la próxima semana**.
- Deploy (Render/Vercel/Docker) no se validó en esta sesión (sin Docker local).

### Validaciones ejecutadas (2026-07-04)
| Comando | Resultado |
| --- | --- |
| `.venv/bin/python -m pytest -q` (baseline, pre-fixes) | 2 failed, 747 passed, 16 skipped, 12 xfailed (99.7 s) |
| `.venv/bin/python -m pytest -q` (post-fixes) | ver entrada de commit — corrida final completa |
| `npm run lint` (frontend) | 0 errores/warnings |
| `npx tsc --noEmit` (frontend) | limpio |
| `npm run build` (frontend) | OK — chunk 755 kB (warning de tamaño) |
| `alembic upgrade head` (SQLite virgen) | OK hasta head `20260626_repair_reservation_unique_constraint` |

### Próximos pasos recomendados (semana del 2026-07-06)
1. Re-correr la auditoría multi-agente completa (workflow reanudable) fuera del horario de límite.
2. Revisar verificación de firmas de webhooks (Stripe, MercadoPago IPN, OTA) — foco heredado del agente de seguridad.
3. Decidir política de datetimes (naive-UTC vs aware) y migrar los 13 `utcnow()`.
4. Code-splitting del frontend.
5. Reinstalar `graphify` y regenerar `graphify-out/` con rutas macOS.
6. Evaluar limpieza de historial de git por los backups de DB.
