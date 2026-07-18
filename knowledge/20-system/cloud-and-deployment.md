# Cloud y despliegue

Estado: `confirmed` para URLs actuales y archivos declarativos; `needs-verification` para previews hasta aprovisionamiento externo.

Superficies canónicas:

- `https://app.hotels-pms.com` — aplicación.
- `https://hotels-pms.com` — marketing.
- `https://api.hotels-pms.com` — API/`/health`.

La configuración actual usa `render.yaml` para el backend y `vercel.json`/`frontend/vercel.json` para Vite. El diseño de preview obligatorio es Vercel por rama → Render backend por rama → Supabase Branch aislada. Render debe recibir `DATABASE_URL`, secretos QA, `FRONTEND_URL` y CORS únicos; frontend debe construirse con su `VITE_API_URL` exacta. Si no existe Supabase Branch, se bloquea hasta tener una segunda DB aislada.

Ver [superficies generadas](../_generated/cloud-surfaces.md) y `30-operations/cloud-surface-manifest.md`.
