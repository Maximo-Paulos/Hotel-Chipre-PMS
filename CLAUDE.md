# Hotel Chipre PMS — Instrucciones para Claude Code

## Stack
- **Backend:** FastAPI + SQLAlchemy 2 + Alembic (SQLite en tests, PostgreSQL en prod)
- **Frontend:** React 18 + TypeScript + Vite 5 + TanStack Query v5
- **AI:** Gemma/Ollama — runtime local privado en `http://127.0.0.1:11434`
- **OTAs:** Booking, Expedia, Despegar
- **Pagos:** MercadoPago, PayPal, Stripe (pro/ultra)
- **Mercado:** Argentina (ARS), expansión LATAM futura

## Base de conocimiento
- `knowledge/00-control/TASK_ROUTER.md` — elegir el context pack mínimo antes de explorar código.
- `knowledge/00-control/STATUS-TODAY.md` — reporte curado del estado actual, riesgos y brechas.
- `knowledge/00-control/SOURCE-OF-TRUTH.md` — jerarquía de evidencia y estados de certeza.
- `docs/orchestrator-status.md` — histórico operativo útil, pero no reemplaza las fuentes anteriores.

## Memoria local compartida
- La memoria persistente vive en `/Users/maximopaulos/AI-Workspace/memory` y en esta vault `knowledge/`.
- Antes de iniciar una tarea, ejecutar `/Users/maximopaulos/AI-Workspace/memory/tools/memoryctl context --agent claude`.
- Crear checkpoints locales en decisiones, cambios relevantes, validaciones y bloqueos.
- Si una nota contradice una instrucción actual o una fuente canónica, marcar `needs-verification` y consultar.

## Entorno local (macOS, desde julio 2026)
- El repo se migró de Windows (`C:\PROJECTO\Hotel-Chipre-PMS`) a macOS. Si aparece una ruta `C:\...` hardcodeada en código, tests o docs, es un bug de migración: corregirla con rutas relativas o `Path(__file__)`.
- Python del sistema es 3.9 (insuficiente): usar el venv del repo `.venv/` (Python 3.12, creado con `uv`). Ej.: `.venv/bin/python -m pytest -q`.
- Node 20 standalone en `~/.local/node/bin` (agregarlo al PATH para `npm`).

## Estado actual de milestones
Leer `docs/orchestrator-status.md` para estado actualizado.

## graphify

This project has a portable Graphify knowledge graph at `.graphify/` (regenerado 2026-07-04 con `@sentropic/graphify` v0.17.x).

Rules:
- Before answering architecture or codebase questions, read `.graphify/GRAPH_REPORT.md` for god nodes and community structure
- If `.graphify/wiki/index.md` exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update . --scope all --no-description --no-label`, `graphify flows build`, `.venv/bin/python scripts/agent_ops/normalize_graphify_portability.py`, then `graphify portable-check` and `graphify check-update`. El binario está en `~/.local/node/bin/graphify`.

## Navegación de contexto (3 capas)
1. **Primero:** consultar `knowledge/00-control/TASK_ROUTER.md` y el context pack asignado para decidir el mínimo contexto.
2. **Segundo:** consultar `.graphify/GRAPH_REPORT.md` / `.graphify/wiki/index.md` y `minimal-context` o `affected-flows` para estructura del código.
3. **Tercero:** leer archivos de código solo cuando se va a editar o las capas 1-2 no tienen la respuesta
