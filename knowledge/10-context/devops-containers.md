---
scope: Render producción, Vercel, Supabase, contenedores y CI
owner: devops-containers
last_verified_commit: bf14bf5
canonical_sources: [render.yaml, vercel.json, frontend/vercel.json, .github/workflows/, knowledge/20-system/cloud-and-deployment.md]
graphify_minimum: graphify affected-flows --files app/main.py
required_validation: production Render manifest + backend health + SHA + CORS/FRONTEND_URL + Redis
---
# Context pack — DevOps y contenedores

La producción actual declara backend Render en `render.yaml` y frontend Vercel. La QA funcional cloud usa el deploy normal de `main` sobre Render producción y el hotel de prueba autorizado; el workflow sólo verifica el SHA, el perfil seguro, CORS, health y Redis.

No se requiere un servicio Render QA ni una base de preview separada para esta campaña. Ningún documento contiene secretos de proveedor; los cambios de infraestructura siguen requiriendo revisión y rollback.
