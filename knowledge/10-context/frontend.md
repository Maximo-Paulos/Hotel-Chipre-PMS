---
scope: React, Vite, rutas, formularios, estado y UX de aplicación
owner: frontend-engineer
last_verified_commit: 50abb05
canonical_sources: [frontend/src/router.tsx, frontend/src/config/publicUrls.ts, frontend/src/views/, knowledge/_generated/frontend-routes.md]
graphify_minimum: graphify minimal-context frontend/src/router.tsx
required_validation: npm run lint + npm run typecheck + npm run build + Playwright focal
---
# Context pack — Frontend

`frontend/src/router.tsx` separa host de aplicación y marketing. `app.hotels-pms.com` sirve operaciones y master-admin; `hotels-pms.com` sirve marketing y redirecciones hacia la app. Consultar el inventario generado antes de cambiar rutas.

Todo cambio visible debe cubrir carga, vacío, error, permisos, teclado/foco y responsive básico; la prueba de navegador debe usar el rol correcto sobre preview aislado.
