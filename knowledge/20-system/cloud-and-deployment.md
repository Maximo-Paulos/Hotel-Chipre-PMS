# Cloud y despliegue

Estado: `confirmed` para los dominios actuales y archivos declarativos; `needs-verification` para variables privadas de proveedor y el SHA live de cada deploy.

Superficies canónicas:

- `https://app.hotels-pms.com` — aplicación.
- `https://hotels-pms.com` — marketing.
- `https://api.hotels-pms.com` — API/`/health`; un primer intento del 2026-07-18 agotó 20 s, pero el reintento con 60 s devolvió HTTP 200. Tratarlo como posible cold start y vigilarlo en previews.

La configuración actual usa `render.yaml` para el backend y `vercel.json`/`frontend/vercel.json` para Vite. La QA funcional cloud usa el deploy normal de `main` en Render producción y el hotel de prueba autorizado. El workflow `Production Render QA cycle` sólo lee la API de Render, espera el SHA exacto, verifica health, CORS, Redis y el perfil sin efectos externos, y no despliega ramas ni cambia configuración.

Evidencia histórica del 2026-07-18: Vercel Production usaba `VITE_API_URL=https://api.hotels-pms.com/api` y Render tenía healthcheck `/health`. Esa observación no prueba el SHA actual ni sustituye el manifiesto generado por Render después de cada merge. Las pruebas cloud funcionales no deben usar previews ni tocar datos compartidos fuera del hotel autorizado.

Ver [superficies generadas](../_generated/cloud-surfaces.md) y `30-operations/cloud-surface-manifest.md`.
