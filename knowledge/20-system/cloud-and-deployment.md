# Cloud y despliegue

Estado: `confirmed` para los dominios actuales y archivos declarativos; `needs-verification` para variables privadas de proveedor y previews hasta aprovisionamiento externo.

Superficies canónicas:

- `https://app.hotels-pms.com` — aplicación.
- `https://hotels-pms.com` — marketing.
- `https://api.hotels-pms.com` — API/`/health`; un primer intento del 2026-07-18 agotó 20 s, pero el reintento con 60 s devolvió HTTP 200. Tratarlo como posible cold start y vigilarlo en previews.

La configuración actual usa `render.yaml` para el backend y `vercel.json`/`frontend/vercel.json` para Vite. El diseño de preview obligatorio es Vercel por rama → Render backend por rama → Supabase Branch aislada. Render debe recibir `DATABASE_URL`, secretos QA, `FRONTEND_URL` y CORS únicos; frontend debe construirse con su `VITE_API_URL` exacta. Si no existe Supabase Branch, se bloquea hasta tener una segunda DB aislada.

Evidencia de proveedor del 2026-07-18: Vercel Production usa `VITE_API_URL=https://api.hotels-pms.com/api` y se redeployó correctamente; esa variable no se asigna a Preview. Los checks Git de PR están asociados a otro espacio Vercel (`maximo-paulos-projects`) que debe reconciliarse con el espacio Production verificado (`maximopaulos1-4687s-projects`) antes de aprobar previews. Render tiene healthcheck `/health` y está en plan Free (posible cold start). `needs-verification`: el start command real de Render no ejecuta Alembic aunque el Blueprint sí lo declara; no cambiarlo hasta validar el PR #24 de reparación de enums en PostgreSQL aislado. Render PR Previews sigue `Off` hasta disponer de DB QA aislada.

Ver [superficies generadas](../_generated/cloud-surfaces.md) y `30-operations/cloud-surface-manifest.md`.
