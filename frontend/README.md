# Frontend (Vite + React + TS)

## Instalación
```bash
cd frontend
npm install
```

## Scripts
- `npm run dev` -> Vite en `http://localhost:5173` con proxy a `$VITE_BACKEND_URL` (por defecto `http://127.0.0.1:8040`) para `/api` y `/health`.
- `npm run build` -> Genera `frontend/dist` (base `/`). Los assets se sirven desde `/assets` y el backend intenta devolver el `index.html` de `frontend/dist` si existe.
- `npm run preview` -> Preview del build.
- `npm run lint` -> ESLint sobre `src`.

## Arranque único (backend + UI nueva)
1. Asegurate de tener el build listo (`cd frontend && npm run build`).
2. En la raíz del repo ejecutá `nodemon`. Usa `./.venv/bin/python -m uvicorn app.main:app --reload` (ver `nodemon.json`) y sirve `frontend/dist`.
   - UI y API en `http://127.0.0.1:8040`.
   - `DEMO_MODE` queda desactivado por defecto (configurado en `nodemon.json`). Si necesitás las rutas de seed/reset, exportá `DEMO_MODE=true` antes de correr `nodemon`.
   - Si no tenés nodemon instalado, podés usar `npx nodemon` o instalarlo global/localmente (`npm i -g nodemon`).

## Headers/Contexto
- Todas las peticiones incluyen `X-User-Id` y `X-Hotel-Id` (persisten en `localStorage`).
- Selector de hotel en el header; persiste la selección y cae a `1` si el valor es inválido.

## App nativa (Capacitor)
- Workflow: `npm run build && npx cap sync` (copia `dist/` a `ios/` y `android/`), luego `npx cap open ios` / `npx cap open android`.
- Detalle completo, config de API para dispositivo real, y pasos manuales para publicar en las stores: ver `CAPACITOR_RELEASE.md`.

## Build
`npm run build` corre limpio en el entorno macOS actual (Node 20 en `~/.local/node/bin`).
La sección de `spawn EPERM` con esbuild que vivía acá era un artefacto del host Windows
anterior (OneDrive/antivirus bloqueando pipes) y ya no aplica.
