# Puertas de entrega

Una tarea funcional no está terminada hasta que se cumpla todo:

1. Tests locales relevantes, lint/typecheck/build, migración limpia y Playwright focal.
2. `render_agents.py --check`, sincronía de skills, enlaces vault e inventarios válidos.
3. `graphify portable-check`, actualización AST y `graphify check-update` fresco cuando hubo código.
4. Revisión de auth/tenancy/integraciones proporcional al cambio.
5. Preview aislado: DB propia, migraciones/seed QA, Render `/health`, CORS/`FRONTEND_URL`, Vercel con `VITE_API_URL` exacta.
6. Matriz cloud completa de cinco personas y evidencia posterior al último `code_sha` funcional.

Si Supabase Branch no está disponible o falta una URL/credencial QA aislada, el gate queda **bloqueado**, no degradado. La primera línea baseline se construye por separado; una vez verde, se aplica a cada cambio.
