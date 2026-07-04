# Hotel Chipre PMS — Instrucciones para Claude Code

## Stack
- **Backend:** FastAPI + SQLAlchemy 2 + Alembic (SQLite en tests, PostgreSQL en prod)
- **Frontend:** React 18 + TypeScript + Vite 5 + TanStack Query v5
- **AI:** Gemma/Ollama — runtime local privado en `http://127.0.0.1:11434`
- **OTAs:** Booking, Expedia, Despegar
- **Pagos:** MercadoPago, PayPal, Stripe (pro/ultra)
- **Mercado:** Argentina (ARS), expansión LATAM futura

## Base de conocimiento
- `docs/orchestrator-status.md` — estado del proyecto, log de sesiones del orquestador semanal, deuda técnica y riesgos abiertos. **Leerlo al inicio de cada sesión de trabajo.**
- (Histórico) El vault de Obsidian en `C:\Users\macap\vault\` pertenecía al entorno Windows anterior a la migración de julio 2026 y ya no está disponible en esta máquina.

## Entorno local (macOS, desde julio 2026)
- El repo se migró de Windows (`C:\PROJECTO\Hotel-Chipre-PMS`) a macOS. Si aparece una ruta `C:\...` hardcodeada en código, tests o docs, es un bug de migración: corregirla con rutas relativas o `Path(__file__)`.
- Python del sistema es 3.9 (insuficiente): usar el venv del repo `.venv/` (Python 3.12, creado con `uv`). Ej.: `.venv/bin/python -m pytest -q`.
- Node 20 standalone en `~/.local/node/bin` (agregarlo al PATH para `npm`).

## Estado actual de milestones
Leer `docs/orchestrator-status.md` para estado actualizado.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)

## Navegación de contexto (3 capas)
1. **Primero:** consultar `graphify-out/graph.json` o `graphify-out/GRAPH_REPORT.md` para estructura del código
2. **Segundo:** consultar el vault de Obsidian para decisiones, progreso y contexto del proyecto
3. **Tercero:** leer archivos de código solo cuando se va a editar o las capas 1-2 no tienen la respuesta
