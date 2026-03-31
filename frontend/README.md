# Frontend (Vite + React + TS)

## Instalación
```bash
cd frontend
npm install
```

> En este entorno Windows, el antivirus/OneDrive bloquea procesos hijo con `stdio` en modo pipe, lo que impide que esbuild pueda arrancar el servicio. Ver más abajo para workaround.

## Scripts
- `npm run dev` -> Vite en `http://localhost:5173` con proxy a `http://127.0.0.1:8000` para `/api` y `/health`.
- `npm run build` -> Genera `frontend/dist` (base `/`). Los assets se sirven desde `/assets` y el backend intenta devolver el `index.html` de `frontend/dist` si existe.
- `npm run preview` -> Preview del build.
- `npm run lint` -> ESLint sobre `src`.

## Arranque único (backend + UI nueva)
1. Asegurate de tener el build listo (`cd frontend && npm run build`). Si el build falla por `EPERM`, ver el workaround más abajo.
2. En la raíz del repo ejecutá `nodemon`. Usa `.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload` y sirve `frontend/dist`.
   - UI y API en `http://127.0.0.1:8000`.
   - `DEMO_MODE` queda desactivado por defecto (configurado en `nodemon.json`). Si necesitás las rutas de seed/reset, exportá `DEMO_MODE=true` antes de correr `nodemon`.
   - Si no tenés nodemon instalado, podés usar `npx nodemon` o instalarlo global/localmente (`npm i -g nodemon`).

## Headers/Contexto
- Todas las peticiones incluyen `X-User-Id` y `X-Hotel-Id` (persisten en `localStorage`).
- Selector de hotel en el header; persiste la selección y cae a `1` si el valor es inválido.

## Problema conocido (build en este host)
- `npm run build` falla con `spawn EPERM` al intentar levantar esbuild con `stdio` en modo pipe (restricción del host). Ejemplo reproducible:
  - `spawnSync(esbuild.exe, ['--version'])` -> `EPERM`
  - `spawnSync(esbuild.exe, ['--version'], { stdio: 'inherit' })` -> OK
- Vite/esbuild necesitan pipes para el servicio, por lo que en este host no es posible completar el build.
- Workarounds:
  1) Ejecutar el build fuera de OneDrive/área protegida o en WSL/Linux/Mac.
  2) Autorizar esbuild en el antivirus/Controlled Folder Access para permitir pipes.
  3) Copiar el repo a una ruta local no sincronizada y rerun `npm install && npm run build`.

El código ya está listo; sólo falta correr el build en un entorno sin la restricción anterior.
