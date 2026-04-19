# Hotel Chipre PMS — Instrucciones para Claude Code

## Stack
- **Backend:** FastAPI + SQLAlchemy 2 + Alembic (SQLite en tests, PostgreSQL en prod)
- **Frontend:** React 18 + TypeScript + Vite 5 + TanStack Query v5
- **AI:** Gemma/Ollama — runtime local privado en `http://127.0.0.1:11434`
- **OTAs:** Booking, Expedia, Despegar
- **Pagos:** MercadoPago, PayPal, Stripe (pro/ultra)
- **Mercado:** Argentina (ARS), expansión LATAM futura

## Vault de memoria
El proyecto tiene una base de conocimiento persistente en `C:\Users\macap\vault\`.
- `vault/hotel-chipre-pms/` — decisiones, arquitectura, features, logs de sesión
- `vault/CLAUDE.md` — instrucciones globales y comandos `/resume`, `/save`, `/status`
- Para cargar contexto de sesión anterior: usar `/resume`
- Para guardar sesión: usar `/save`

## Estado actual de milestones
Leer `docs/orchestrator-status.md` y `docs/milestone-acceptance-log.md` para estado actualizado.

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
