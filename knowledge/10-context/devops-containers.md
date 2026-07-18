---
scope: Render, Vercel, Supabase, contenedores, CI y previews
owner: devops-containers
last_verified_commit: 50abb05
canonical_sources: [render.yaml, vercel.json, frontend/vercel.json, .github/workflows/, knowledge/20-system/cloud-and-deployment.md]
graphify_minimum: graphify affected-flows app/main.py
required_validation: preview manifest + backend health + frontend VITE_API_URL exacta
---
# Context pack — DevOps y contenedores

La producción actual declara backend Render en `render.yaml` y frontend Vercel. Los previews deben ser por PR: base Supabase Branch aislada, backend Render con URL/secretos QA propios y frontend Vercel construido contra la URL exacta del backend.

Si Supabase Branches no está disponible, no se degrada a una base compartida: se bloquea y se solicita segunda base QA aislada. Ningún documento contiene secretos de proveedor.
