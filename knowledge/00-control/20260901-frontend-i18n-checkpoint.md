---
kind: checkpoint
scope: project
status: needs-verification
agent: frontend-engineer
created_at: 2026-09-01
project: hotel-chipre-pms
---

# Bloque 9 i18n: infraestructura y auth

## Decisiones

- `es` es la fuente de verdad y `en` se genera junto con cada namespace migrado.
- Esta tanda crea únicamente `auth` y `common`; migra `LoginPage`, `RegisterOwnerPage` y los controles compartidos visibles de autenticación.
- `AppShell` solo carga el idioma configurado del hotel y ejecuta `changeLanguage`; `DashboardPage` y el resto de pantallas quedan fuera de la migración por la instrucción adicional de alcance.
- `languages` continúa representando los idiomas hablados por el hotel y no se reemplaza.

## Estado

Se ejecutaron el context pack frontend, el contexto mínimo Graphify y `alembic heads`. El worktree ya tenía cambios paralelos en configuración, `SettingsHotelPage` y pruebas; se conservaron. La instalación de npm no pudo completarse porque el registry no resolvió (`ENOTFOUND`); `package-lock.json` sigue sin las dos entradas nuevas. El gate Node de locales pasó 2/2, la prueba backend de configuración pasó 10/10 y el ciclo SQLite de migración upgrade/downgrade/upgrade pasó. Lint, TypeScript y build quedan bloqueados por los módulos no instalados. Playwright no pudo iniciar el backend local porque el sandbox rechazó el bind de `127.0.0.1:8040`; la verificación Render no pudo comenzar porque faltan variables de proveedor y el DNS externo está bloqueado.

Graphify AST, flows, normalización portable y `portable-check` pasaron. `graphify check-update` sigue reportando el marcador semántico `.graphify_describe_pending` heredado del hook paralelo; no se eliminó manualmente.

## Próximo paso

Completar la instalación/lockfile cuando el registry o una caché válida estén disponibles; repetir lint, TypeScript, build y Playwright, y recorrer el gate cloud después de un deploy de `main` cuyo SHA incluya estos cambios.
