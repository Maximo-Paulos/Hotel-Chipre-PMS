# Puertas de entrega

Una tarea funcional no está terminada hasta que se cumpla todo:

1. Tests locales relevantes, lint/typecheck/build, migración limpia y Playwright focal.
2. `render_agents.py --check`, sincronía de skills, enlaces vault e inventarios válidos.
3. Actualización AST, `graphify flows build`, normalización portable, `graphify portable-check` y `graphify check-update` fresco cuando hubo código.
4. Revisión de auth/tenancy/integraciones proporcional al cambio.
5. Preview aislado: DB propia, migraciones/seed QA, Render `/health`, CORS/`FRONTEND_URL`, Vercel con `VITE_API_URL` exacta.
6. Matriz cloud completa de cinco personas y evidencia posterior al último `code_sha` funcional.

La evidencia versionada queda ligada por hash a un único
`validated-preview-manifest.json` hermano y a una `attestation.json` Ed25519 del
operador. La firma cubre bytes exactos, task/code SHA, metadatos proveedor, timestamp
y todos los hashes de artefactos comprobados localmente. Usa SHA completos y conserva
IDs de run y artefacto. Cambios posteriores en producto, migraciones, workflows, bootstrap,
`scripts/agent_ops/`, catálogo QA, tests o definiciones de agentes invalidan la
evidencia anterior.

La autoridad permanente es `.github/workflows/trusted-release-gate.yml`, ejecutada
con `pull_request_target` desde el SHA base inmutable. Lee los JSON del head como
blobs, nunca hace checkout ni ejecuta código del head, verifica por API el run y el
artefacto proveedor, exige bytes idénticos y valida la firma con
`qa/trust/qa-evidence-public-key.pem` del checkout base; nunca confía en una clave
aportada por el head. `summary.json`, manifiesto y atestación deben cambiar juntos.
Además, el SHA que ejecutó `verify-preview-providers.yml` debe ser ancestro del SHA
base actual y el blob exacto de ese workflow debe coincidir con el del base; no se
aceptan marcadores de texto como sustituto de procedencia histórica.
El workflow `release-gate.yml` se
mantiene como diagnóstico local/no autoritativo. Ninguna de las dos puertas recibe
tokens de proveedores; la puerta confiable entrega su token GitHub sólo al script
del base y al action oficial de descarga, con permisos de sólo lectura.

La evidencia proveedor se produce en una única ejecución serializada de
`.github/workflows/verify-preview-providers.yml` desde la rama por defecto. Ese
ciclo adquiere un lease aleatorio en el servicio Render QA, verifica GitHub,
Render, Supabase y Vercel, emite la capacidad Ed25519 sólo en el runner, ejecuta
bootstrap, elimina la capacidad de Render, vuelve a consultar los proveedores,
comprueba health, CORS y el bundle frontend, publica sólo el manifiesto final y
libera el lease con `always()`. No existe un workflow separado de provisión ni un
artefacto de token.

Render QA debe observar `EMAIL_PROVIDER=null`, `CONNECTIONS_ENABLED=false`,
PayPal sandbox e IA/Gemma deshabilitadas, sin credenciales live ni workers/cron
en el mismo entorno. El manifiesto y la capacidad ligan además el fingerprint
combinado de run, cinco personas, master-admin y política de migración; cualquier
drift bloquea antes de conectar a la base.

Estado operativo: `needs-verification` hasta que los workflows confiables y
`qa/trust/qa-evidence-public-key.pem` existan en la rama por defecto; un workflow
`pull_request_target` nuevo no puede proteger la misma PR que lo introduce antes
de ese bootstrap.

Si Supabase Branch no está disponible o falta una URL/credencial QA aislada, el gate queda **bloqueado**, no degradado. La primera línea baseline se construye por separado; una vez verde, se aplica a cada cambio.
