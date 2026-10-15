# Notas de auditoría de consumo — parte OPS (CI/CD, despliegue, scripts, QA, agent-ops, dependencias)

- Fecha de lectura: 2026-10-15. Repo `/home/user/Hotel-Chipre-PMS` (rama `claude/modest-goldberg-5dd5am`, HEAD `d1a5ce7`).
- Alcance: los 119 archivos de la lista `ops-files.txt` (21.132 líneas según la columna de líneas), todos leídos con Read en tramos ≤ 700 líneas. Los JSON/MD grandes también se leyeron completos (no por resumen): `non-certified-local-preview-static.json` (3.080 líneas, 6 tramos), `regression-catalog.json` (2.159), `shared-sandbox-catalog.json` (1.024), `observations.json` de agosto (838).
- No se modificó ningún archivo del repositorio salvo este. No se ejecutó npm/pip/docker/alembic/tests/scripts del repo.
- Mediciones propias (solo lectura): `wc`, `grep`, `ls`, `du`, `git log/ls-files` y consultas GET a la API JSON pública de PyPI para tamaños de wheels (no instala nada). Etiquetas: [P0] pérdida de datos/seguridad/caída, [P1] impacto alto en consumo o correctitud, [P2] mejora menor, [info]. "(verificado: archivo:línea)" = leído/medido; "(inferido, no verificado)" = deducción; "estimado" = cifra con su origen declarado.
- Entorno de auditoría: Linux, Python 3.13, sin `.venv` ni Node; por eso no se midió tiempo real de CI ni de build. Las únicas duraciones "verificadas" salen de los reportes versionados en `qa/`.

## 0. Hechos transversales medidos

- Repo trackeado: 1.931 archivos, 61,2 MB (`git ls-files` + tamaños): `frontend` 45,1 MB (de los cuales `frontend/ios` 21 MB + `frontend/android` 16 MB, `du`), `app` 3,9 MB, `tests` 3,8 MB, `docs` 2,7 MB, `knowledge` 1,95 MB, `.graphify` 1,7 MB, `qa` 0,46 MB, `scripts` 0,46 MB.
- CORREGIDO (verificación): el clon es shallow (`git rev-parse --is-shallow-repository` = true; el commit más antiguo es a142c70, 2026-09-26), así que los 132 commits cubren solo 2026-09-26 → 2026-10-15 (HEAD d1a5ce7), no "desde 2026-07-01" (las 19 "de septiembre" son del 26 al 30). Además 21 de los 132 son merges (lista de archivos vacía en `git log --name-only`): los 63 son sobre 111 commits no-merge, o sea 57 % (no 48 %); contando los merges como no-runtime serían 84/132 = 64 %. El desglose 35/26/12/7/3 sí se confirma. Original: Historial local: 132 commits desde 2026-07-01 (19 en septiembre, 113 en los primeros 15 días de octubre). De esos 132, **63 (48 %) no tocan** `app/`, `alembic/`, `requirements.txt`, `render.yaml`, `runtime.txt`, `app.py`, `start.sh` ni `Procfile` (35 tocan `docs/`, 26 `.graphify/`, 12 `frontend/`, 7 `knowledge/`, 3 `qa/`; verificado con `git log --name-only`).
- 173 migraciones Alembic (`git ls-files alembic/versions`, sin `__init__`).
- No existe `gunicorn` en ningún archivo (grep = 0): todos los arranques son 1 worker de uvicorn.
- No hay filtros `paths`/`paths-ignore`, ni `concurrency` (salvo `verify-preview-providers.yml:19`), ni `size-limit`/Lighthouse en `.github` (grep = 0). `timeout-minutes` solo en 3 jobs (`pr-validation.yml:74`, `trusted-release-gate.yml:16`, `verify-preview-providers.yml:30`). `cache:` solo en `pr-validation.yml:18,49,86,96`.
- `render.yaml` no contiene `disk:`, `buildFilter`, `region:` ni `PYTHON_VERSION` (grep -c = 0 cada uno).

---

## 1. `.github/workflows/` (6 archivos, 599 líneas)

- `.github/workflows/pr-validation.yml` (118) — CI principal de cada PR: job `backend` (Python 3.11, `alembic upgrade head` sobre SQLite, `pytest -q`, contrato GCP), job `frontend` (npm ci, lint, typecheck, test, build) y job `e2e` (Python 3.12 + Node 20 + Playwright Chromium, 4 proyectos) · hallazgos:
  - [P1] Los 3 jobs corren en paralelo en cada `opened/synchronize/reopened` (L3-4) sin `concurrency`/`cancel-in-progress` (verificado: el archivo completo no tiene bloque `concurrency`): cada push durante una revisión deja terminar hasta tres jobs ya obsoletos.
  - CORREGIDO (verificación): la ausencia de `paths`/`paths-ignore` está confirmada (grep = 0 en `.github`; L3-4 solo declaran `pull_request:`), pero la proporción de commits sin tocar runtime es 63 de 111 no-merge (57 %), no 63/132 (48 %), sobre un clon shallow que empieza el 2026-09-26 (ver sección 0). [P1] Sin `paths-ignore` (L3-4): un PR que solo cambia `docs/`, `knowledge/`, `qa/` o `.graphify/` ejecuta igualmente backend + frontend + e2e. Con 63 de 132 commits sin tocar código runtime (sección 0), la proporción de CI "inútil" puede ser cercana a la mitad (estimado: depende de cuántos van en PR propios).
  - CORREGIDO (verificación): ≈16,1 min (`report.md:63`) y `workers: 1` (`frontend/playwright.config.ts:95`, comentario L92-94) se confirman, pero "el intento 1 tuvo 6 fallos por selectores ambiguos" mezcla dos reportes: `performance-cloud-retest-20261005/report.md:63` dice "seis fallos E2E" sin indicar causa; los "selectores ambiguos de habitaciones" figuran en `postmerge-performance-cloud-20261005-790d7a/report.md:4` y son 2 fallos (174 aprobadas, 6 omitidas) en un run. No se puede afirmar que sean los mismos ni que los 6 fallos fueran por selectores. [P1] El job `e2e` tarda ≈16,1 min (verificado: `qa/operational/runs/performance-cloud-retest-20261005/report.md:63`, "176 E2E passed y 6 skipped (16,1 min)") y es secuencial por diseño (`workers: 1`, `frontend/playwright.config.ts:95`). El reintento del mismo PR repite los 16 min (el intento 1 tuvo 6 fallos por selectores ambiguos y el 2 pasó: `…/performance-cloud-retest-20261005/report.md:63`).
  - [P1] `npx playwright install --with-deps chromium` (L102-103) corre en cada ejecución sin caché de `~/.cache/ms-playwright`: descarga Chromium (≈150 MB, estimado) y paquetes apt del sistema cada vez.
  - [P2] `npm ci` se ejecuta dos veces por PR (job frontend L52-53 y job e2e L99-100); `setup-node cache: npm` solo cachea `~/.npm`, no `node_modules`.
  - [P2] Versión de Python dispar: backend 3.11 (L17), e2e 3.12 (L85), `runtime.txt` 3.11.9, Dockerfile `python:3.11-slim`, local 3.12 (CLAUDE.md). El E2E ejercita un intérprete distinto del de pytest/producción, y hay dos cachés pip separados (L18, L86).
  - [P2] Sin `timeout-minutes` en `backend` y `frontend` (L7-65): tope por defecto 360 min por job.
  - [P2] El paso `validate_gcp_readiness.py` (L32-33) es un gate estático para un "futuro despliegue en Google Cloud" (exige `docs/runbooks/gcp-migration.md` y `OBJECT_STORAGE_GCS_*` en `.env.example`, `validate_gcp_readiness.py:11-40`): puede bloquear un PR por un destino que el piloto no usa.
  - [info] No hay trigger `push` a `main` en este workflow: tras el merge no se re-ejecutan tests; solo corre `build-and-push`.
  - [info] No hay presupuesto de tamaño de bundle ni Lighthouse en CI (grep = 0): una regresión de peso del frontend no hace fallar nada.

- `.github/workflows/build-and-push.yml` (100) — en cada push a `main` (y manual): construye imágenes backend y frontend con `docker build` plano, verifica la etiqueta OCI de revisión, genera `release-manifest.json`, sube ambas imágenes a GHCR con tag = SHA y sube el manifiesto como artifact (30 días) · hallazgos:
  - [P1] Nadie consume esas imágenes: `grep ghcr.io` solo encuentra este workflow y `tests/test_release_sha_validator.py` (verificado). Render despliega con runtime Python nativo (`render.yaml:11`) y Vercel construye desde fuente. Cada merge paga dos builds completos **sin caché de capas** (sin buildx/`cache-from`, L37-51) + push: estimado 7–11 min por merge (backend: apt `build-essential` + `pip install` completo ≈ 4–6 min; frontend: `npm ci` + `vite build` ≈ 2–3; push ≈ 1–2; sin medición propia).
  - [P1] GHCR acumula una imagen backend por merge sin ninguna política de retención (no hay workflow de limpieza). Tamaño estimado ≈ 1 GB por imagen (base slim + `build-essential` + ortools/pandas/numpy/cassandra/etc.); si el repo es privado cuenta contra el almacenamiento de Packages (needs-verification: visibilidad del repo).
  - [P2] `if: github.ref_name == github.event.repository.default_branch` (L13) es redundante con `branches: ["main"]` (L5), salvo en `workflow_dispatch`.
  - [P2] Sin `timeout-minutes` (default 360). Usa `python` del runner sin `setup-python` (L61, L81), versión no fijada.

- `.github/workflows/preview-qa.yml` (39) — "Preview QA untrusted contract": en cada PR instala el runtime hash-locked (`requirements-qa-trusted.txt`) y valida JSON de QA, `validate_preview_manifest --skip-freshness`, `render_agents --check` y `sync_skills --check` · hallazgos:
  - [P2] Mínimo 1 min facturable por cada push de PR (checkout + setup-python + pip sin `cache: pip`, L21-27) aunque el PR no toque `qa/`, `agent-ops/` ni `.agents/` (sin filtro `paths`).
  - [P2] Solapa con `release-gate.yml`: `validate_setup.py` (L27) repite `render_agents --check` y `sync_skills --check` y valida los mismos dos JSON (`validate_setup.py:31-39`).

- `.github/workflows/release-gate.yml` (41) — con etiqueta `require-provider-qa` ejecuta `validate_setup.py` + `check_release_evidence.py` · hallazgos:
  - [P2] El workflow se dispara con 6 tipos de evento (`opened, synchronize, reopened, ready_for_review, labeled, unlabeled`, L5); sin la etiqueta el job se omite (L12) y cuesta 0 min, pero cada evento crea un run vacío. Con la etiqueta: `fetch-depth: 0` (L17) clona toda la historia y reinstala el runtime hash-locked sin caché (L22-25).
  - [P2] Con la etiqueta puesta, los dos gates fallan por "cero resúmenes QA elegibles" (verificado: `qa/operational/runs/performance-cloud-retest-20261005/report.md:65`; `…/postmerge-performance-cloud-20261005-790d7a/report.md:41`): consumen minutos para producir un rojo ya conocido.

- `.github/workflows/trusted-release-gate.yml` (64) — `pull_request_target` (con etiqueta): usa el código del SHA base y la API de GitHub para validar la evidencia QA del PR, descarga el artifact del proveedor y compara bytes · hallazgos:
  - [P2] Misma estructura de costo: checkout + pip hash-locked sin caché (L27-30), 6 tipos de evento (L5), `timeout-minutes: 15` (L16). `prepare` hace ≥ 10 llamadas REST por ejecución (repo, pull, árbol recursivo base/head/evidencia/workflow, blobs, compare ×2, artifact, run, workflow: `trusted_release_gate.py:342-434`): consume cuota de API, no minutos.
  - [info] `release-gate.yml` y este workflow responden la misma pregunta ("¿hay evidencia QA válida?") con dos implementaciones distintas (`check_release_evidence.py` vs `trusted_release_gate.py`).

- `.github/workflows/verify-preview-providers.yml` (237) — solo manual (`workflow_dispatch`, L3-13): lease en Render QA → 3 verificaciones de proveedores (Render/Supabase/Vercel/GitHub) → token Ed25519 → instala capacidad en Render QA y fuerza redeploy → health/CORS/bundle → sube evidencia (7 días) → libera lease · hallazgos:
  - [P2] 0 min/mes si no se ejecuta; cuando se ejecuta: hasta 45 min (L30), serializado (L19-21), y cada ciclo provoca un `POST /deploys` en Render QA (`provision_qa_bootstrap.py:542-544`) con su propio `pip install` de `requirements.txt` completo (needs-verification de cuota de build en Render).
  - [P2] `verify_preview_providers.py` se invoca 3 veces por ciclo (L91, L127, L200; `grep -c` = 3): cada una repagina env-vars de 2 servicios Render y consulta GitHub/Supabase/Vercel (≈10–25 requests, estimado).
  - [info] Según la evidencia versionada este workflow nunca produjo una ejecución en nube: "`gh run list` devolvió cero ejecuciones" (`qa/history/observations/shared-production-20260724.md:174`) y las corridas de octubre declaran "No se configuró ni utilizó Render QA" (`…/postmerge-performance-cloud-20261005-790d7a/report.md:41`).

---

## 2. Dockerfiles, arranque, despliegue y archivos raíz

- `Dockerfile.backend` (29) — imagen `python:3.11-slim`, usuario no-root `appuser` (uid 10001), `uvicorn` de 1 worker con `--timeout-graceful-shutdown 30` · hallazgos:
  - [P2] Una sola etapa: `apt-get install build-essential libpq-dev` (L10) queda en la imagen final (≈250 MB, estimado) y no hace falta: todas las dependencias con extensión nativa publican wheel cp311 manylinux x86_64 (verificado en PyPI: psycopg2-binary 2.9.9, cassandra-driver 3.29.2, pymongo 4.9.2, ortools 9.12.4544, Pillow 12.3.0, cryptography 50.0.1).
  - [P2] `requirements.txt` completo se instala en runtime: incluye pytest/pytest-asyncio/pytest-cov (`requirements.txt:15-17`), ortools+pandas+numpy, celery, pymongo, cassandra-driver, neo4j (ver anexo D).
  - [P2] `chown -R appuser:appuser /app` (L20) duplica `/app` en una capa nueva (≈4,7 MB de `app/`+`alembic/`, trivial): usar `COPY --chown`.
  - [P2] `ENV DATABASE_URL=sqlite:///./dev.db` (L25): sin `DATABASE_URL` real el contenedor arranca con un SQLite efímero en vez de fallar (falla silenciosa). `CMD` fija el puerto 8000 (L29), ignora `$PORT`, no ejecuta migraciones aunque copia `alembic/` (L18-19) y no define `HEALTHCHECK`.
  - [info] Solo lo consumen `build-and-push.yml` y `docker-compose.yml`; Render no lo usa.

- `Dockerfile.frontend` (17) — build Vite en `node:20-alpine` y runtime `nginx:1.27-alpine` con `frontend/docs/nginx.conf` · hallazgos:
  - [P2] L6-8: `COPY frontend/package*.json ./` seguido de `COPY frontend ./` antes de `npm ci`: el primer COPY no aporta; cualquier cambio de código invalida la capa de `npm ci` (reinstala todo en cada build; sin `--mount=type=cache`).
  - [P2] `COPY frontend ./` copia `frontend/ios` (21 MB), `frontend/android` (16 MB), `frontend/e2e` (0,9 MB) y docs al contexto de build; `.dockerignore` (leído, no listado) solo excluye `.git`, `__pycache__`, venvs, `dist`, `node_modules`, `*.log`: no excluye `frontend/ios`, `frontend/android`, `qa`, `knowledge`, `docs`, `tests`, `.graphify`, `*.db`.
  - [P2] `ARG VITE_API_URL=http://localhost:8000` (L4) queda horneado: una imagen "release" construida sin `--build-arg` apunta a localhost.
  - [P2] `frontend/docs/nginx.conf` (leído): sin `gzip`, sin `Cache-Control` para `/assets/` y sin cabeceras de seguridad; vercel.json sí las define. Solo relevante para la ruta Docker/compose; el nginx master corre como root.

- `Procfile` (1) — `web: python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` · hallazgos:
  - [P2] Render no lee Procfile (inferido, no verificado: `render.yaml:16` usa `startCommand` propio). Si se usara, migraría en cada arranque/despertar y no lleva `--timeout-graceful-shutdown`. Solo lo referencia `tests/test_release_evidence_contract.py:288` como path "release-relevant" (borrarlo exige tocar ese test).

- `start.sh` (13) — igual que el Procfile con `set -e` y `echo` · hallazgos:
  - [P2] El comentario dice "Render startup script" (L2) pero `render.yaml` no lo invoca (L14-16): código muerto salvo `tests/test_release_evidence_contract.py:289`. Migrar en cada arranque duplicaría el `preDeployCommand` (`render.yaml:15`).

- `render.yaml` (180) — blueprint de 1 web (uvicorn 1 worker, health `/health`, `autoDeploy`) + 1 cron cada 5 min; presupuesto: sin Redis/Celery/ClickHouse/Mongo · hallazgos:
  - CORREGIDO (verificación): la divergencia contra el servicio vivo se sostiene (`hotel-backend` vs `hotel-chipre-pms-api` en todas las versiones del yaml; plan Free vs `standard`/`starter`; sin pre-deploy vs `preDeployCommand` presente ya en a142c70, 2026-09-26, primer commit del clon shallow), pero el yaml actual NO es el que existía cuando se escribieron los reportes: hasta f2a2cc5 (2026-10-04) `render.yaml` declaraba plan `standard`, un Redis `hotel-chipre-pms-redis`, `REDIS_URL` tomado de ese servicio, `DB_POOL_TIMEOUT_SECONDS="15"` y el comentario "The current live web service is on Render Free and has no Redis"; recién 9e4b357 (2026-10-12, "Reduce PMS request load…") lo reescribió a `starter`, sin Redis, `REDIS_URL ""` y pool 5 s. Por eso (a) los 15 s del pool (`postmerge-readonly…/report.md:44`, párrafo sobre el código del checkout 0174f497, no sobre el servicio vivo) coincidían con el yaml previo y con el fallback `app/database.py:287` (15.0), no contradicen un yaml de 5 s; (b) "el yaml dice false y REDIS_URL \"\"" (L62-63, L72-73) compara reportes del 09-24/10-05 con un yaml posterior a ellos. [P1] El blueprint no describe lo que corre: define `hotel-chipre-pms-api`, plan `starter`, `preDeployCommand: alembic upgrade head` (L10-15), pero los reportes observan el servicio `hotel-backend` en plan **Free** (`…/postmerge-readonly-20261005-0174f497/report.md:9,17`), "sin pre-deploy configurado y su start command no ejecuta `alembic upgrade head`" (`…/rbac-prod-main-smoke-20260924-f895899/report.md:16`), `EMAIL_PROVIDER=resend` y `CONNECTIONS_ENABLED=true` (`…/report.md:13`; el yaml dice `null`/`false`, L114-115 y L36-37) y `READ_MODEL_CACHE_ENABLED=true` efectivo con Redis desconectado (`…/performance-cloud-retest-20261005/report.md:10,45`; el yaml dice `false` y `REDIS_URL ""`, L62-63 y L72-73). El pool "permite esperar hasta 15 s" (`…/postmerge-readonly…/report.md:44`) frente a 5 s del yaml (L28-29); puede ser el default del código si la variable no está definida en el servicio vivo (no verificable sin acceso a Render). Conclusión (inferida): el blueprint no se está aplicando y casi todas las latencias medidas en `qa/` son de otra configuración.
  - CORREGIDO (verificación): `autoDeploy: true` (L134) y la ausencia de `buildFilter` (grep -c = 0) se confirman; la estadística es 63 de 111 commits no-merge (57 %), no 63/132, sobre un clon shallow desde 2026-09-26 (sección 0). [P1] `autoDeploy: true` (L134) sin `buildFilter`: cada push a la rama conectada hace `pip install` completo + `alembic upgrade head` + reinicio. Con la estadística de la sección 0 (63/132 commits sin tocar runtime) casi la mitad serían despliegues innecesarios (aplica si el servicio vivo sigue el blueprint; needs-verification).
  - CORREGIDO (verificación): (a) `render.yaml` no tiene `region:` (grep -c = 0), confirmado; (b) la cita `.env.render:12` es en realidad `.env.render:13` y es un archivo de ejemplo con placeholders ("Sample env for Render…", `postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com`), no prueba la región real de Supabase; (c) "≈50 ms/consulta" vale solo para `/operational/daily` (1966,23 ms / 39); `/operational/alerts` da 1478,76 ms / 39 ≈ 38 ms (promedio de ambas ≈ 44 ms; `production-latency-20261006-73398218/report.md:16-17`). La región real de Render y de Supabase sigue sin verificarse. [P1] Sin `region` (L9-17): Render usa Oregon por defecto (inferido), mientras `.env.render:12` apunta a Supabase `aws-0-us-east-1` y `render-no-show-cron.yaml:6` fija `oregon`. Un RTT cruzado entre regiones es consistente con ≈50 ms por consulta medidos: 39 consultas = 1.966 ms de DB (`…/production-latency-20261006-73398218/report.md:12-17`: 1966,23/39 ≈ 50 ms). Inferido; needs-verification de la región real.
  - [P1] Sin `disk:` en ningún servicio (grep = 0) y `ANALYTICS_EXPORTS_DIR=/var/exports/analytics` (L132-133) apunta al FS efímero de Render: exportaciones y comprobantes locales se pierden en cada deploy (confirmado por la auditoría previa N2, `REPORT.md`; no re-verificado aquí).
  - [P1] Cron `*/5 * * * *` (L139-148): 288 contenedores/día (8.640/mes) que cada vez importan la app y se conectan a la BD; además mantiene Supabase despierto. Cifra de ≈5,5 s de import por corrida: dato de `REPORT.md`, no re-medido. Solapa con `render-no-show-cron.yaml` y con Celery (sección Anexo B).
  - [P2] `REALTIME_EVENTS_TRANSPORT=postgresql` + `POSTGRES_EVENT_LISTENER_ENABLED=true` (L42-49): exige una conexión directa/sesión persistente (LISTEN) además del pool 4+2 contra el límite de conexiones de Supabase; `POSTGRES_EVENT_LISTENER_DATABASE_URL` es `sync:false` (L50-51) y puede quedar vacío sin que el yaml lo detecte (inferido).
  - [P2] No fija versión de Python (sin `PYTHON_VERSION` ni `.python-version`, grep = 0) y `runtime.txt` es formato Heroku (inferido: Render no lo lee): versión efectiva no determinista frente al 3.11 de Dockerfile/CI.
  - [info] `healthCheckPath: /health` (L17) es barato: el handler no toca la BD (`app/main.py:577-584`, verificado). `numInstances: 1` + `COLLABORATION_BACKEND=process` (L13, L60-61) es coherente.

- `render-no-show-cron.yaml` (27) — cron horario (`10 * * * *`) `python -m app.tasks.run_no_show_sweep` · hallazgos:
  - [P1] Referencia `fromService: name: hotel-backend` (L14-17) pero `render.yaml` nombra el servicio `hotel-chipre-pms-api` (L10): aplicado como blueprint fallaría por servicio inexistente; solo cuadra con el servicio manual `hotel-backend` que observan los reportes → es un blueprint paralelo.
  - [P1] Duplica trabajo: `scheduled_hotel_jobs_service` importa y ejecuta `sweep_no_shows` (`app/services/scheduled_hotel_jobs_service.py:13`; totales `no_shows_marked` en `app/tasks/run_scheduled_hotel_jobs.py:20-28`), que ya corre cada 5 min. Este cron agrega 24 contenedores/día (720/mes) para repetir el barrido. Los tres orquestadores (cron 5 min, este cron, Celery beat) pueden marcar no-shows.
  - [P2] `plan: 0.5c-512mb` (L5) no es un identificador de plan de Render que yo conozca (needs-verification); `region: oregon` (L6) fija una región que `render.yaml` no fija.

- `docker-compose.yml` (148) — stack local: postgres:15, redis:7, mongo:7, cassandra:4, neo4j:5, backend, worker y beat de Celery, frontend nginx · hallazgos:
  - [P2] Levanta 5 almacenes + worker + beat aunque `MONGO_ENABLED/CASSANDRA_ENABLED/NEO4J_ENABLED` están en `"false"` (L92, 95, 99) y `depends_on` los obliga a arrancar (L77-82). Cassandra y Neo4j son JVM (>1 GB de RAM cada una, estimado): el entorno local por defecto consume órdenes de magnitud más que producción (1 API + Postgres). Sin `condition: service_healthy` (L77-82) aunque define healthchecks.
  - [P2] El backend no ejecuta migraciones (CMD del Dockerfile sin alembic): `docker compose up` no inicializa el esquema con Alembic. `worker`/`beat` usan `celery -A app.tasks.celery_app` (L115, L129) aunque producción presupuesto no corre Celery (`render.yaml:7-8`).
  - [P2] `version: "3.9"` (L1) obsoleto; `postgres:15` (L5) vs PG16 en E2E y Supabase.
  - [P2] Credenciales de desarrollo en claro y puertos publicados en todas las interfaces (L9-10, 13-14, 19-20, 33-34, 47-48, 59-62, 68, 98): sin riesgo en producción; en una red compartida deja bases abiertas con contraseñas triviales.

- `vercel.json` (27) — build Vite (`npm run build` raíz), `outputDirectory: frontend/dist`, rewrite SPA global, cache inmutable para `/assets/*`, cabeceras de seguridad · hallazgos:
  - CORREGIDO (verificación): la diferencia de rewrites se confirma (`vercel.json` raíz L7-9: solo `/(.*)` → `/index.html`; `frontend/vercel.json` L5-42: los 8 rewrites a `*.html` más el catch-all; también difieren `installCommand` y `outputDirectory`), pero el impacto está mal descrito: esos `*.html` no son páginas prerenderizadas con contenido propio; `frontend/marketing-html.mjs` (cabecera L1-12 y `marketingHtmlPlugin` L132-146) emite copias de `index.html` con solo `<title>`, description, canonical y og:/twitter: cambiados, con el mismo bundle JS. Sin los rewrites no se sirve "más bundle" ni empeora el LCP: el efecto es que crawlers y unfurlers sin JS ven el mismo título/description/canonical genérico en las 8 rutas (SEO y previews de enlaces). [P1] (inferido) El `vercel.json` raíz **no tiene** los 8 rewrites de páginas de marketing prerenderizadas (`/funciones`, `/precios`, `/faq`, `/pms-hotelero`, `/software-para-hoteles`, `/terms`, `/privacy`, `/contacto` → `*.html`) que sí tiene `frontend/vercel.json` (verificado con diff de ambos JSON); además difieren `installCommand` (raíz L4) y `outputDirectory` (`frontend/dist` L6 vs `dist`). Si el proyecto Vercel usa la raíz del repo como Root Directory (lo sugiere `package.json` raíz "hotel-chipre-pms-vercel-build"), esas rutas caen en `/(.*) → /index.html` (L7-9): se sirve el bundle SPA completo en vez del HTML estático (más ancho de banda, peor LCP/SEO). Needs-verification del Root Directory real.
  - [P2] `installCommand: npm install` (L4) en raíz + `npm ci` dentro de `frontend` (`package.json:5`): dos instalaciones por build (la raíz no tiene dependencias, costo trivial). Cache inmutable solo bajo `/assets/` (L12-16); sin reglas para fuentes/iconos fuera de `/assets`.

- `package.json` (7) — un único script `build` que hace `cd frontend && npm ci && npm run build` para Vercel; sin dependencias · [info] sin hallazgos.

- `nodemon.json` (10) — recarga local con uvicorn en el puerto 8040 · hallazgos:
  - [P2] Código muerto en la práctica: `nodemon` no es dependencia de ningún `package.json` (README.md:11 y frontend/README.md:17-20 piden `npx`/global). Duplica el reload: nodemon (`watch`, `legacyWatch: true` = polling, L2 y L9) + `--reload` de uvicorn (L5) = dos watchers sobre `app/`. Puerto 8040 vs 8000 en Dockerfile/Procfile/compose (la skill `dev-up` ya avisa de la inconsistencia, `.claude/skills/dev-up/SKILL.md:21`).

- `app.py` (1) — `from app.main import app` · hallazgos:
  - [P2] Muerto/ambiguo: coexiste con el paquete `app/` en la misma carpeta (Python resuelve `import app` al paquete; inferido) y nadie referencia `app:app` ni `app.py` (grep = 0).

- `reset.py` (28) — shim de compatibilidad: delega en `scripts.seed_e2e_backend.main` y convierte `E2ESafetyError` en `SystemExit` · [info] ya no es destructivo sobre `DATABASE_URL` (solo `_e2e.db`); cubierto por `tests/test_reset_entrypoint_safety.py:21`. Nombre engañoso, sin hallazgos de consumo.

- `runtime.txt` (1) — `python-3.11.9` · [P2] formato Heroku; Render no lo lee según su documentación (inferido, no verificado) → versión de Python efectiva no determinada; CI mezcla 3.11 y 3.12.

- `requirements.txt` (35) — 33 pins directos (+2 comentarios) · hallazgos:
  - [P1] 11 de 33 son prescindibles en runtime de piloto y 4 más son condicionales a flags apagados: ver anexo D. El mayor peso real es `ortools` (24,9 MB de wheel; arrastra `numpy`, `pandas`, `absl-py`, `immutabledict` y fija `protobuf`), importado de forma perezosa por **1** módulo con fallback a asignación greedy (`app/services/allocation_engine.py:225-233`, `:541`).
  - [P2] `pytest`, `pytest-asyncio`, `pytest-cov` (L15-17) viajan en la build de producción (0 importaciones en `app/`; 219 archivos de `tests/` los usan).
  - [P2] `requests` no está declarado pero lo importan 8 módulos de `app/` (`app/services/integration_service.py:6`, `…/email/providers.py:8`, `…/payment_webhook_service.py:17`, etc.) y `app/api/auth.py:14` vía `google.auth.transport.requests`; llega solo como dependencia transitiva de `mercadopago` y `paypalrestsdk` (verificado en PyPI `requires_dist`). Quitar esos SDKs rompería el arranque.
  - [P2] `app/api/auth.py:14-15` importa `google.auth`/`google.oauth2` de forma eager aunque `GOOGLE_LOGIN_ENABLED=false` (`render.yaml:74-75`): carga google-auth + requests + urllib3 + cachetools en el arranque (RAM no medida).
  - [info] `uvicorn==0.30.6` sin extras `standard` (sin uvloop/httptools): menor RAM, algo menos de throughput. `websockets==13.1` es necesario (`app/api/collaboration.py:672`).

- `requirements-qa-trusted.txt` (15) — runtime hash-locked para los workflows de QA (cryptography, cffi, SQLAlchemy, greenlet, typing_extensions) · hallazgos:
  - [P2] Versión distinta de `cryptography` (46.0.6, L3) frente a `requirements.txt:29` (50.0.1): dos pins que mantener. Se instala sin `cache: pip` en 4 workflows (preview-qa, release-gate, trusted-release-gate, verify-preview-providers).

- `alembic.ini` (40) — configuración de Alembic · hallazgos:
  - [P2] `sqlalchemy.url = ${DATABASE_URL}` (L4) no se interpola en alembic.ini y `env.py:97` lo sobreescribe: valor muerto. `script_location = alembic` y `prepend_sys_path = .` relativos: solo funcionan desde la raíz.

- `alembic/env.py` (122) — resuelve URL, ensancha `alembic_version.version_num` a VARCHAR(128) y ejecuta migraciones online con `NullPool` · hallazgos:
  - [P2] `get_url()` cae a `sqlite:///./dev.db` si falta `DATABASE_URL` (L35): en el `preDeployCommand` (`render.yaml:15`) una variable ausente migraría un SQLite efímero y daría "éxito" sin tocar PostgreSQL (inferido).
  - [P2] Importa `app.database`, `app.models` y `app.master_admin.models` completos (L19-21) solo para que `autogenerate` tenga `target_metadata`; `upgrade` no lo necesita. Cada `alembic upgrade` (pre-deploy; y cada arranque si se usara Procfile/start.sh) carga ≈70 módulos de modelos y la configuración.
  - [P2] `_ensure_wide_version_table` (L53-92) abre 1-2 transacciones extra con introspección (`get_table_names`, `get_columns`) antes de las 173 migraciones: ≈3-6 consultas de catálogo por upgrade (estimado).
  - [info] `poolclass=pool.NullPool` (L102) es correcto para pooler. Un `upgrade head` desde cero (CI sobre SQLite, `pr-validation.yml:23-27`, y cada arranque de Playwright) ejecuta las 173 migraciones.

---

## 3. `scripts/` (39 archivos, 10.586 líneas)

### 3.1 `scripts/agent_ops/` (26 archivos, 6.862 líneas) — tooling de agentes, QA formal y gates de release

Nada de esto se importa desde `app/` ni se copia a la imagen (`Dockerfile.backend:17-19` solo copia `app/` y `alembic/`); su costo es de CI, de mantenimiento y de contexto. Los scripts de gate/QA suman 7.412 líneas de Python junto con `bootstrap_cloud_qa.py` e `issue_qa_provider_evidence.py` (suma de la lista de LOC) y tienen 17-19 archivos de prueba en `tests/` que corren dentro del `pytest` de cada PR (`ls tests | grep -E 'qa|preview|release|attest|bootstrap|lease|evidence|manifest|provider|trusted'` = 19 nombres).

- `scripts/agent_ops/build_shared_sandbox_bootstrap_sql.py` (315) — genera SQL (dry-run por defecto; `--emit-sql --ack production-labelled-shared-sandbox`) que inserta 2 hoteles QA y 2 owners en la base del "sandbox compartido" · hallazgos:
  - CORREGIDO (verificación): `PROJECT_REF` (L22) = ref de producción se confirma (coincide con `scripts/bootstrap_cloud_qa.py:104` y con `shared-sandbox-campaign-20260812/report.md:3-5`, que llama a la base "dominios compartidos con etiqueta de producción"; hoteles 16/17 en L11), pero la cita correcta es `scripts/README.qa-bootstrap.md:22` (no :23). [P1] El `PROJECT_REF` permitido es el de producción (`ezkljznogqpmrjxyvklr`, L22; el mismo que `scripts/README.qa-bootstrap.md:23` y `scripts/bootstrap_cloud_qa.py:104` tratan como "producción conocida"): el "sandbox compartido" **es** la BD productiva. Los reportes confirman datos QA mezclados con registros "de aspecto ordinario" (`qa/operational/runs/performance-cloud-retest-20261005/report.md:11,37`) y hoteles 16/17 sintéticos (`…/shared-sandbox-campaign-20260812/report.md:11`): datos de prueba en la BD que usará el piloto (sesgan conteos, `id` de hotel = `max(id)+1` en L181/L209, ocupan cupo de la BD gratuita).
  - [P2] Guardas razonables (allowlist de ref, ack textual, `pg_advisory_xact_lock` L120, aborta ante hoteles/usuarios no marcados L130-156). `on conflict (email) do update set password_hash…` (L158-176) sobrescribe contraseñas de cuentas ya marcadas.
- `scripts/agent_ops/check_cloud_surface_config.py` (54) — verifica que 7 archivos usen los hosts canónicos `hotels-pms.com` y no `hoteles-pms.com` · [info] sin hallazgos; solo corre dentro de `validate_setup.py`.
- `scripts/agent_ops/check_knowledge.py` (130) — valida la bóveda `knowledge/` (frontmatter, links locales, roles ↔ context packs) · [info] recorre `knowledge/**/*.md` y resuelve cada link (L97-104): trivial; solo corre con la etiqueta de release.
- `scripts/agent_ops/check_preview_manifest.py` (13) — shim `from validate_preview_manifest import main` · [P2] import no cualificado (L9): solo funciona ejecutado desde su carpeta; sin referencias en CI/docs (grep) → obsoleto.
- `scripts/agent_ops/check_qa_evidence.py` (457) — valida el bundle de evidencia QA (resumen + manifiesto + atestación Ed25519) contra el catálogo: 45 casos → 335 filas caso/persona/dispositivo · [info] gate formal sin uso real en nube (ver sección 5); `validate_evidence_bundle` relee el catálogo de 50 KB en cada llamada.
- `scripts/agent_ops/check_release_evidence.py` (160) — exige un bundle QA válido tras cualquier cambio "release-relevante" · hallazgos:
  - CORREGIDO (verificación): `is_release_relevant_path` L54-64 fail-closed y `EVIDENCE_OUTPUT_RE` (L23-25: solo `summary.json`, `validated-preview-manifest.json` y `attestation.json` bajo `qa/evidence/<task>/`) se confirman; el "48 %" de commits no-código es 57 % (63/111 no-merge, sección 0). [P1] `is_release_relevant_path` (L54-64) es fail-closed: todo path salvo los 3 archivos de evidencia invalida la evidencia anterior (docs, `knowledge/`, `.graphify/`, `qa/operational/` incluidos). Cualquier commit posterior al ciclo QA obliga a repetir el ciclo completo (workflow de hasta 45 min + redeploy de Render QA). Con 48 % de commits no-código (sección 0) el gate es una máquina de re-trabajo.
- `scripts/agent_ops/compare_preview_manifests.py` (88) — comprueba que el manifiesto del proveedor no derive entre sondas · [info] sin hallazgos.
- `scripts/agent_ops/context_status.py` (41) — hook de `SessionStart`/`SubagentStart` (`.claude/settings.json`) que ejecuta `graphify check-update .` con `timeout=10` (L19) · hallazgos:
  - [P2] Cada inicio de sesión y de **cada subagente** lanza un proceso Node de hasta 10 s sin caché; en flujos con muchos subagentes (como esta auditoría) se paga N veces.
- `scripts/agent_ops/generate_qa_local_env.py` (198) — genera `.env.qa.local` (0600, 7 personas, contraseñas aleatorias `secrets`) · [info] guardas fuertes, sin secretos embebidos (L84 solo un prefijo `Qa9!` para cumplir complejidad).
- `scripts/agent_ops/manage_qa_baseline_lease.py` (474) — adquiere/libera un lease exclusivo escribiendo 3 variables de entorno en el servicio Render QA (allowlist estricta) · hallazgos:
  - [P2] Cada adquisición/liberación hace 2 GET + 3 PUT/DELETE a Render; en Render, cambiar variables de entorno suele disparar un redeploy (inferido, no verificado: depende del parámetro `skipDeploy`): potencialmente 2 redeploys extra por ciclo QA solo por el lease.
- `scripts/agent_ops/normalize_graphify_portability.py` (93) — reescribe `.graphify/graph.json` para neutralizar rutas · hallazgos:
  - [P2] Lee el archivo entero con `read_text` (L57), aplica una regex y lo reescribe (L74): ≈3× el tamaño en RAM (graph.json pesa 53 MB y crece ≈20 MB/mes según `CLAUDE.md`/`.gitignore`: ≈160 MB hoy, estimado; >300 MB en ~12 meses). Es un paso obligatorio tras cada cambio de código según CLAUDE.md. Falla con `FileNotFoundError` si el grafo no existe (clon nuevo/CI).
- `scripts/agent_ops/normalize_qa_catalog.py` (195) — generador de un solo uso que escribe `qa/regression-catalog.json` y `qa/operational/shared-sandbox-catalog.json` a partir de `CASE_SPECS` (L22-68) y mueve evidencia histórica · hallazgos:
  - [P2] Obsoleto y sin guarda: sobreescribe ambos catálogos (si alguien edita el JSON a mano, la próxima ejecución lo pisa); los dos JSON (≈3.200 líneas, 77 KB) derivan de 47 líneas de Python (verificado leyendo generador y salidas). Invariante hard-codeada `(45, 173, 335)` (L188).
- `scripts/agent_ops/operational_qa.py` (269) — crea y valida corridas de QA operativa sobre dominios compartidos · hallazgos:
  - [P2] `validate` exige artefactos con SHA para toda observación no `NOT_APPLICABLE` (L228-229) y metadatos completos; de las 6 corridas versionadas con `artifact-index.json`, 4 lo tienen vacío (day2, pr117, shared-sandbox, sim-d0d1) y las otras 2 (prod-day-sim, rbac) referencian 4 archivos de texto en `artifacts/qa-operational/`, ignorado por git, que no se pueden revalidar desde el repositorio; el run de agosto lo reconoce (`shared-sandbox-campaign-20260812/report.md:76-82`): la herramienta no valida el propio contenido versionado.
- `scripts/agent_ops/provision_qa_bootstrap.py` (613) — instala el token como variable en Render QA, dispara deploy y sondea · hallazgos:
  - [P2] `for _ in range(90): … sleeper(10)` (L549-557): hasta 15 min de job bloqueado haciendo polling cada 10 s, sin backoff, dentro del timeout de 45 min del workflow. Una sola ejecución puede dejar 90 GET a la API de Render.
- `scripts/agent_ops/qa_bootstrap_contract.py` (134) — contrato compartido de claves/valores seguros del bootstrap · [info] `FORBIDDEN_QA_CREDENTIAL_KEYS` (L72-106) prohíbe `REDIS_URL`, `CELERY_*`, `MONGO_*`, `CASSANDRA_*`, `NEO4J_*`: el propio entorno QA se diseñó sin ellos, es decir, el perfil que debería ser el de producción presupuesto.
- `scripts/agent_ops/qa_evidence_attestation.py` (651) — firma/verifica Ed25519 la evidencia local (hasta 10.000 archivos / 2 GB, L54-56) · [info] 651 líneas de criptografía para un flujo manual que ninguna corrida versionada ha usado (no existe `qa/evidence/<task>/`: solo el README).
- `scripts/agent_ops/render_agents.py` (112) — genera 18 agentes Claude y 18 Codex desde `agent-ops/roles/*.json` · hallazgos:
  - [P2] Hardcodea `/Users/maximopaulos/AI-Workspace/memory/tools/memoryctl` (L40) en las instrucciones de los 36 archivos generados (18 `.claude/agents/*.md` + 18 `.codex/agents/*.toml`, verificado con grep): en cualquier otro equipo/CI cada agente intenta ejecutar una ruta inexistente. `preview-qa.yml:34` corre `--check` sobre esos archivos en cada PR.
- `scripts/agent_ops/render_skills.py` (183) — reescribe `SKILL.md` y `agents/openai.yaml` de 18 skills desde un diccionario Python · hallazgos:
  - [P2] Generador sin `--check` ni guarda: pisa ediciones manuales. Genera 18 skills pero `.agents/skills` tiene 23 (faltan `dev-up`, `new-migration`, `new-permission`, `scale-data-architecture`, `validate-all`; verificado con `ls`): la fuente de verdad es ambigua. Falla con `FileNotFoundError` si no existe `agents/` (sin `mkdir`, L173).
- `scripts/agent_ops/sync_skills.py` (58) — espeja `.agents/skills` en `.claude/skills` · hallazgos:
  - [P2] `--write` hace `shutil.rmtree(TARGET)` (L50-52): borra cualquier skill que solo exista en `.claude/skills`.
- `scripts/agent_ops/trusted_release_gate.py` (526) — gate de la rama base vía API de GitHub (árboles/blobs/compare) · [info] ver `trusted-release-gate.yml`; ≈19 llamadas REST por ejecución (estimado contando `prepare_gate`).
- `scripts/agent_ops/validate_gcp_readiness.py` (55) — chequeo estático del "futuro despliegue GCP" · [P2] gate de PR sobre un destino que el piloto no usa (ver `pr-validation.yml:32-33`); exige `OBJECT_STORAGE_GCS_BUCKET`, `OBJECT_STORAGE_GCS_PROJECT` y `REDIS_NAMESPACE` en `.env.example` (L34-36).
- `scripts/agent_ops/validate_preview_manifest.py` (531) — valida el esquema v2 del manifiesto de preview (≈100 reglas) · [info] sin hallazgos de consumo.
- `scripts/agent_ops/validate_setup.py` (44) — ejecuta 4 subprocesos Python (`render_agents`, `sync_skills`, `check_knowledge`, `check_cloud_surface_config`) + 2 validaciones JSON · [info] solo con la etiqueta de release; solapa con `preview-qa.yml`.
- `scripts/agent_ops/verify_preview_bundle.py` (226) — descarga hasta 64 JS del preview Vercel (8 MiB c/u, 32 MiB total, L17-20) y busca hosts de API · [info] límites sanos; gasta hasta 32 MiB de ancho de banda de Vercel por ciclo QA.
- `scripts/agent_ops/verify_preview_providers.py` (1115) — construye el manifiesto de evidencia leyendo Render/Supabase/Vercel/GitHub (solo GET con reintentos) · [P2] se invoca 3 veces por ciclo (ver workflow); pagina `env-vars` de 2 servicios en cada llamada (L425-466).
- `scripts/agent_ops/verify_release_sha.py` (127) — valida el manifiesto de imagen (usado por `build-and-push.yml:81`) · [info] sin hallazgos.

### 3.2 Resto de `scripts/` (13 archivos, 3.724 líneas)

- `scripts/README.qa-bootstrap.md` (142) — documentación del bootstrap de QA en nube · [info] cita el ref de producción en claro (L23, identificador no secreto) y describe un flujo de tokens Ed25519 que, según los reportes, aún no se ejecutó (L129-132 "hasta que el workflow/provider complete este intercambio… fail-closed").
- `scripts/backup/verify_local_backup_restore.py` (284) — drill local de backup→restore (SQLite `iterdump` o `pg_dump/pg_restore` en loopback, BD temporal creada y borrada) · hallazgos:
  - [P1] Es el único "drill" de respaldo y es solo local (guarda L44, L157-158): el registro histórico declara que no existe backup/restore probado contra el proveedor (`qa/history/observations/non-certified-local-preview-static.json:2910-2937`, severidad P1). Para un piloto con datos reales sobre Supabase Free (inferido, no verificado: el plan gratuito no incluye PITR ni backups gestionados con retención útil) es riesgo de pérdida de datos; no hay cron/workflow de backup en el repo (grep de `pg_dump` fuera de este script = 0 en `.github` y `render*.yaml`).
  - [info] El texto de `--table` (L256) lista "guests, reservations, payments, audit_logs" pero `DEFAULT_TABLES` (L31-42) es otra: doc desactualizada.
- `scripts/bootstrap_cloud_qa.py` (1172) — bootstrap fail-closed de 5 personas + hotel sintético en una BD QA aislada (se usa como `preDeployCommand` del servicio Render QA) · hallazgos:
  - [P2] Hardcodea el ref de producción como lista negra (L104; identificador, no secreto). No va en la imagen de producción (no se copia `scripts/`). Sin consumo en runtime de producción; 1.172 líneas casi todas de verificación de tokens/lease.
- `scripts/issue_qa_provider_evidence.py` (148) — firma el token de capacidad con clave privada leída de entorno · [info] sin hallazgos.
- `scripts/knowledge/generate_inventories.py` (124) — regenera `knowledge/_generated/*` (openapi.json, rutas, head de Alembic, resumen Graphify) · hallazgos:
  - [P2] No determinista: escribe `datetime.now(UTC)` en cada archivo (L31) → cada regeneración cambia todos los `.md` aunque nada cambie (commits espurios que disparan CI y, si aplica, autoDeploy). Importa `app.main` completo para volcar `openapi.json` (1,85 MB trackeado; L55-58); requiere Python ≥ 3.11 (`from datetime import UTC`, L10).
- `scripts/repair_analytics_facts.py` (220) — reconstruye hechos de analítica (`--hotel-id`/`--all-hotels`, `--dry-run`) · hallazgos:
  - [P2] Destructivo-idempotente (borra e inserta hechos por hotel, commit por hotel, L187-213) sin guarda de entorno: usa el `DATABASE_URL` del proceso (L174) y puede apuntar a producción; el modo seguro es opt-in (`--dry-run`) en vez de opt-out.
  - [P2] Sin `--date-from/--date-to` recalcula de golpe min(`check_in`)…max(`check_out`) de todo el historial del hotel (L95-120): filas ≈ habitaciones × días (L165) en una sola transacción por hotel.
- `scripts/report_duplicate_laundry_remitos.py` (45) — reporte de solo lectura de remitos duplicados previo a una migración; exige `MIGRATION_PREFLIGHT_DATABASE_URL` · [info] sin hallazgos (guarda explícita).
- `scripts/scale/staged_http_load.py` (152) — carga HTTP escalonada (steady 100 + burst 200 conexiones por defecto, 30 s + 10 s, L139-143) · hallazgos:
  - [P1] **No rechaza hosts de producción** (no hay `validate_target`; verificado en L1-152), a diferencia de `staged_realtime_load.py:21,55-56`: con `--base-url https://api.hotels-pms.com` y un token lanzaría 200 conexiones concurrentes contra 1 worker y pool 4+2 (`render.yaml:24-27`) → riesgo de caída del único API.
- `scripts/scale/staged_realtime_load.py` (131) — SSE/recovery de solo GET con denylist de hosts de producción (L21, L55-56) · [P2] f-string sin placeholders (L76); sin más hallazgos.
- `scripts/seed_e2e_backend.py` (619) — siembra la BD E2E (SQLite fija `_e2e.db` o PG loopback aislado con roles `*_app_runner`/`*_seed_runner`) · hallazgos:
  - [P2] Credenciales y secretos de prueba por defecto embebidos: contraseñas de owner/manager/recepción/housekeeping (L216, L225-234), contraseña y secreto TOTP base32 del owner step-up (L419-423) y JWT de test (L171, L192). Solo bajo `APP_ENV=test` y repetidos en `frontend/playwright.config.ts:57,81-84,233`; no sensibles pero fijos y públicos en el repo.
  - [P2] Crea 5 propósitos × 4 proyectos = 20 usuarios step-up + 3 de staff + owner + master (L424-455, 456-478, 584-603): ≈25 `hash_password` con argon2id de 19 MiB (`app/services/security.py:22-37`) y `E2E_RESET_DATABASE=true` (`playwright.config.ts:199`) borra y re-migra las 173 migraciones en cada arranque de Playwright: costo fijo por job e2e (estimado 5-15 s para el seed + migraciones; no medido).
  - [info] Guardas fuertes (6 candados, L41-148, L151-193); soporte vestigial de rutas Windows (L177-181).
- `scripts/seed_f003_load_scenario.py` (259) — fixture de 30 habitaciones / 45 reservas / 4 categorías para carga, solo PG loopback con rol de siembra BYPASSRLS · [info] sin hallazgos; guardas completas (L24-42, L74-112).
- `scripts/seed_marketing_demo.py` (395) — BD SQLite `demo-marketing.db` para capturas de marketing · hallazgos:
  - [P2] Contraseña demo embebida (L31, impresa en L389) y secreto JWT demo (L40). Duplica ≈60 % de la lógica de `seed_e2e_backend.py` (hotel, owner, membresía, onboarding, categorías, habitaciones). `random.seed(20260910)` global al importar (L34). Fuerza `DATABASE_URL`/`APP_ENV` (L38-39): seguro (su propio archivo SQLite).
- `scripts/serve_e2e_backend.py` (33) — siembra y sirve uvicorn en `127.0.0.1:8040` sin `reload` · [info] sin hallazgos.

---

## 4. `agent-ops/` (19 archivos, 164 líneas)

- `agent-ops/role-skill-map.json` (20) y `agent-ops/roles/*.json` (18 archivos × 8 líneas = 144): definición canónica de 18 roles de agente (nombre, título, descripción, context pack, foco, validación) y su mapa de skills · hallazgos:
  - [P2] Se materializan en 36 archivos generados (`.claude/agents` + `.codex/agents`) con la ruta macOS hardcodeada (`render_agents.py:40`). Sin impacto en consumo de la app; sí en contexto cargado por los agentes y en el paso `render_agents --check` que corre en cada PR (`preview-qa.yml:34`).
  - [info] Los 18 JSON tienen exactamente las mismas 6 claves; ningún secreto ni PII.

---

## 5. `qa/` (38 archivos, 9.082 líneas)

Resumen: `qa/` pesa 0,46 MB trackeado (38 archivos); no afecta el runtime. El valor para esta auditoría está en las **mediciones de producción** que contienen los reportes (citadas abajo) y en que documentan que la maquinaria formal de QA nunca llegó a ejecutarse en nube.

- `qa/evidence/README.md` (46) — instrucciones de evidencia QA versionable (`summary.json`, manifiesto, atestación Ed25519); el directorio `qa/evidence/<task-id>/` no existe en el repo (solo este README) · [info] el gate `operating-system`/`trusted-base-evidence` exige un bundle que nunca se creó (reportes: "cero resúmenes QA elegibles").
- `qa/operational/README.md` (27) — reglas de las corridas sobre dominios compartidos (no certificantes) · [info] sin hallazgos.
- `qa/trust/qa-evidence-public-key.pem` (3) — clave **pública** Ed25519 (no es secreto) · [info] la clave privada correspondiente no está en el repo (comprobado: ningún `BEGIN PRIVATE KEY` en el alcance).
- `qa/preview-manifest.example.json` (65) — manifiesto de ejemplo schema v2 · [info] valores ficticios (incluye un `baseline_lease_id` de forma realista, L44, y el repo `Maximo-Paulos/Hotel-Chipre-PMS`, L14).
- `qa/regression-catalog.json` (2.159, 49,8 KB) — catálogo "certificado" v2: 45 casos, 173 pares persona, 335 triplets caso/persona/dispositivo · hallazgos:
  - [P2] **Generado** (`normalize_qa_catalog.py:22-68`) y muy repetitivo: cada caso repite `preconditions`/`steps` idénticos (p. ej. L68-76). Leído completo; es estructura derivada, no conocimiento.
- `qa/operational/shared-sandbox-catalog.json` (1.024, 27 KB) — derivado del mismo generador (45 casos × 2 perfiles de dispositivo → 346 combinaciones) · [P2] duplicado de datos del catálogo anterior (misma fuente `CASE_SPECS`).
- `qa/history/observations/non-certified-local-preview-static.json` (3.080 líneas, 197.557 bytes) — **archivo histórico generado** de 90 registros de QA local/cloud de julio 2026 (leído completo en 6 tramos) · hallazgos útiles para consumo:
  - [P1] `fase14-backups-restore-gap` (L2910-2937): no existe drill de backup/restore contra proveedor.
  - [P2] `fase13-double-submit…` (L2507-2536): la creación de reservas sigue sin `Idempotency-Key` real en servidor; la guarda de doble clic es solo de cliente.
  - [P2] `fase8-analytics-exports-endpoints-have-no-ui` (L2029-2057): `/api/analytics/exports/{png,csv,xlsx}` existen en backend y no hay UI en el frontend que los llame (según grep de ese momento; no re-verificado): código con consumo de mantenimiento sin consumidor.
  - [P2] `fase12-cross-hotel-id-collision-audit` (L2383-2415): `app/api/connections.py` + `connection_service.py` son un endpoint legacy no montado (código muerto).
  - [info] Describe un pipeline de facts por Celery beat cada 5 min (L1998) que ya no coincide con el diseño actual (cron SQL).
  - [info] 197 KB de bitácora histórica en el árbol de trabajo: candidata a salir del repo/checkout (no afecta runtime).
- `qa/history/observations/shared-production-20260724.json` (377) y `.md` (236) — 9 registros y su bitácora del barrido cloud del 24-jul (mismo contenido en dos formatos) · hallazgos:
  - [P1 histórico] En el build de entonces: Reportes "Failed to fetch"/"Cargando…" >10-20 s, Analytics "Cargando analytics…" 10-14 s, cotización siempre en `Noches 0 / Total 0`, overflow del documento a 390 px (`/dashboard` 557-558 px, `.md:107`). Eran fallos de despliegue/versión (`needs-verification` del SHA, `.md:9,180-200`), no atribuibles al código local.
  - [info] `.md:173-174` confirma que el workflow de QA de nube nunca se ejecutó y que faltaban `RENDER_QA_SERVICE_ID`/`SUPABASE_QA_PROJECT_REF`.
- `qa/operational/runs/day2-live-role-retest-20261004-0ddeb59c/{artifact-index,observations,run-metadata}.json` (5+5+34) y `report.md` (58) — recorrido de solo lectura: Caja con HTTP 422 en resumen diario y 503 en tickets de colaboración (`report.md:9,16`), Reportes con primera carga lenta · [info] `observations: []` con `case_count: 45`: no certificable.
- `qa/operational/runs/performance-cloud-retest-20261005/report.md` (76) — **medidas de navegador→API** de una sola pasada sobre producción (Render Free): `/api/rooms/categories` 8.826 ms, `/api/rooms/` 4.727 ms, `/api/reservations/actions/pending` 4.430 ms, `/api/room-movement-groups/` 3.117 ms, `/api/reservations/` 1.296-2.826 ms (L42); `READ_MODEL_CACHE_ENABLED=true` efectivo con Redis desconectado (L10, L45); el fallback SSE consulta el outbox por pestaña ≈ cada 2 s (L50, no medido); pytest completo 2.851 passed (L59); gates de release rojos por falta de evidencia (L65) · [P1] la latencia medida corresponde a una configuración que no coincide con `render.yaml`.
- `qa/operational/runs/postmerge-performance-cloud-20261005-790d7a/report.md` (49) — tras el merge de PR #119: tiempos de cabecera 553 ms (Dashboard) … 3.010 ms (Planilla) (L20-27); aviso de cobro manual MP/PayPal aceptado por el endpoint sin respuesta del proveedor (L35); pendiente: "costo de los sondeos del outbox" (L49) · [info] una muestra por pantalla, sin percentiles.
- `qa/operational/runs/postmerge-readonly-20261005-0174f497/report.md` (63) — Render **Free** con aviso de spin-down de 50 s o más (L9, L17); `/health` 274-758 ms (L16); consultas por endpoint sobre SQLite (pending 12, listado ≤10, grilla ≤8, ocupación ≤3, resumen operativo 62→25; L34-40); hook `after_commit` publica a Redis caído evento por evento (L42); índices de outbox declarados en el modelo y ausentes en migraciones (L44); pool con espera de hasta 15 s sin métricas (L44) · [P1] confirma que Redis caído añade espera en el camino de escritura.
- `qa/operational/runs/pr117-postmerge-20261005-3c91a3e8/{artifact-index,observations,run-metadata}.json` (5+46+29) y `report.md` (76) — Gerencia: `/api/reservations/actions/pending` 10,8 s, `/api/auth/session/refresh` 8,2 s, `/api/reservations/` mediana 4,8 s (n=3), `/api/notifications` 182 llamadas en 49 min (p95 732 ms, máx 3,3 s) (L32) → ≈3,7 solicitudes/min por pestaña (182/49, calculado) · [P1] polling de notificaciones constante por pestaña abierta; Recepción recibía 403 en `/api/payments/summary/{id}` (L7, L19).
- `qa/operational/runs/prod-day-sim-20261001-6361f7a1/{artifact-index,observations,run-metadata}.json` (34+80+22) y `report.md` (22) — 4 fallos funcionales de simulación de un día (Empresas 500, cotización FX no disponible, reserva OTA con habitación inconsistente, "Moviendo…" >12 s mientras se refrescan consultas) · [info] el último es un coste de refresco de consultas en cliente (invalidaciones en cascada), corregido con refresco en segundo plano (`report.md:16`).
- `qa/operational/runs/production-latency-20261005-df079bd4/report.md` (37) — 0,4-2,2 s por llamada; Dashboard ≈15 solicitudes API al cargar y Caja ≈18 (L14-15); colaboración devuelve 503 mientras Redis está caído (L16); **hipótesis**: el SSE de fallback usaba un generador síncrono con `time.sleep` en el threadpool compartido (L22), sin `Server-Timing` (L18) · [P1] consistente con N9 de la auditoría previa.
- `qa/operational/runs/production-latency-20261006-73398218/report.md` (27) — Reportes envía **dos** solicitudes por carga para la misma fecha: `/operational/daily` 2.329 ms con 39 consultas y `/operational/alerts` 2.242 ms con otras 39 (L12-17); `alerts` recalcula `daily_report()` · [P1] 78 consultas por carga de Reportes de las cuales 39 son duplicadas; el parche local elimina la segunda llamada (L23).
- `qa/operational/runs/rbac-prod-main-smoke-20260924-f895899/{artifact-index,observations,run-metadata}.json` (30+54+22) y `report.md` (18) — humo de producción: Render live **sin pre-deploy ni `alembic upgrade head`** (L16); cabeza Alembic en Supabase `20260918_member_alias_auth` frente a `20260924_action_stepup_single_use` local (L15; el código local con RBAC nuevo no estaba desplegado); `EMAIL_PROVIDER=resend` y `CONNECTIONS_ENABLED=true` (L13) · [P1] deriva entre manifiesto y servicio vivo.
- `qa/operational/runs/shared-sandbox-campaign-20260812/{artifact-index,observations,run-metadata}.json` (5+838+22) y `report.md` (108) — 52 observaciones, 50 PASS y 2 FAIL (manager sin acceso a `GET /api/reservations/` por `require_roles` sin `manager`, `report.md:26-30`) · [info] sin evidencia binaria (`artifact-index` vacío, `report.md:76-82`); contiene el patrón de aislamiento por `X-Hotel-Id` verificado a nivel API (L54-57).
- `qa/operational/runs/sim-d0d1-reaudit-20261001-5538c5/{artifact-index,observations,run-metadata}.json` (5+183+53) y `report.md` (59) — reauditoría de día 0-1: cotización con tarifa vigente falla con HTTP 400 `No active prices found for rate plan` (L18, L53), cambios de categoría vendida en movimientos, tarifa de adicional sin fecha de vigencia · [info] hallazgos funcionales; la corrida declara Redis con error mientras el bloqueo distribuido figura requerido (L10).

---

## Resumen de la parte

Los 10 hallazgos más importantes por impacto en consumo/costo (todos de mi parte; detalle y referencias en las secciones 1-5 y anexos):

1. CORREGIDO (verificación): ver la corrección de la sección 2 (`render.yaml`): los reportes de `qa/` (2026-09-24 a 2026-10-06) son anteriores a la reescritura del yaml del 2026-10-12 (9e4b357) y los 15 s del pool no contradicen el yaml de entonces (decía 15); la divergencia Free / `hotel-backend` / sin pre-deploy sí se sostiene. **[P1] El blueprint `render.yaml` no describe el servicio que corre.** Define `hotel-chipre-pms-api` / plan `starter` / `preDeployCommand: alembic upgrade head` (`render.yaml:10-15`), pero los reportes versionados observan `hotel-backend` en plan **Free**, sin pre-deploy, con `EMAIL_PROVIDER=resend`, `CONNECTIONS_ENABLED=true`, Redis habilitado-desconectado y `READ_MODEL_CACHE_ENABLED=true` efectivo, y pool que espera hasta 15 s (`qa/operational/runs/rbac-prod-main-smoke-20260924-f895899/report.md:13,16`; `…/postmerge-readonly-20261005-0174f497/report.md:9,17,44`; `…/performance-cloud-retest-20261005/report.md:10,45`). Consecuencia (inferida): las latencias de 3-10 s medidas en `qa/` son de otra configuración y optimizar `render.yaml` no cambia lo que corre hasta que se alineen.
2. CORREGIDO (verificación): `.env.render:12` es `.env.render:13` y es un archivo de ejemplo con placeholders; ≈50 ms/consulta vale solo para `daily` (`alerts` ≈ 38 ms; promedio ≈ 44 ms). **[P1] Región probablemente cruzada API↔DB.** `render.yaml` no fija `region` (Oregon por defecto, inferido), `.env.render:12` apunta a Supabase `aws-0-us-east-1`. Medido: 39 consultas = 1.966 ms de DB (≈50 ms/consulta) en Reportes (`qa/operational/runs/production-latency-20261006-73398218/report.md:12-17`). Con 10-60 consultas por pantalla, la latencia de red domina. Needs-verification de la región real.
3. CORREGIDO (verificación): "63 de 132 commits" es 63 de 111 no-merge (57 %) en un clon shallow desde 2026-09-26 (sección 0). **[P1] La CI de cada PR cuesta ≈29-35 min por push** (e2e ≈16,1 min verificado en `performance-cloud-retest-20261005/report.md:63`; backend/frontend/preview-qa estimados) sin `concurrency`, sin `paths-ignore`, sin caché de navegadores Playwright y con `npm ci` duplicado (`pr-validation.yml:3-4,52,99,102`). Con 63 de 132 commits sin tocar runtime (sección 0), cerca de la mitad es evitable; en GitHub Free privado (2.000 min/mes, needs-verification) ≈60 pushes agotan la cuota.
4. **[P1] `build-and-push.yml` construye y publica 2 imágenes por cada merge a `main` que nadie consume** (ghcr.io solo aparece en el propio workflow y en un test; Render/Vercel no las usan), sin caché de capas y sin retención en GHCR (`build-and-push.yml:37-92`). ≈7-11 min por merge (estimado) + almacenamiento acumulado (≈1 GB por imagen backend, estimado).
5. CORREGIDO (verificación): "63/132" es 63/111 no-merge (57 %) en un clon shallow desde 2026-09-26 (sección 0). **[P1] `autoDeploy: true` sin `buildFilter`** (`render.yaml:134`): cada commit en la rama conectada reinstala dependencias (incluye ortools+pandas+numpy), migra y reinicia. 63/132 commits desde 2026-07-01 son de docs/.graphify/frontend/knowledge/qa (git log), es decir, despliegues innecesarios si el servicio sigue el blueprint (needs-verification).
6. **[P1] Tres orquestadores de tareas hacen el mismo barrido y uno está roto.** Cron Render `*/5` (288 contenedores/día, `render.yaml:139-143`), cron horario `render-no-show-cron.yaml` (apunta a `fromService: hotel-backend`, que no existe en `render.yaml`, L14-17, y repite lo que ya hace `scheduled_hotel_jobs_service.py:13`) y Celery beat (docker-compose `worker`/`beat`, `app/tasks/celery_app.py:167`). Costo: arranques de Python + conexiones TLS a la BD por cada corrida.
7. **[P1] Dependencias pesadas con uso mínimo en el API:** `ortools` (24,9 MB de wheel) arrastra `numpy` + `pandas` (≈30 MB más) y lo importa **1** módulo de forma perezosa con fallback greedy (`allocation_engine.py:225-233`); `celery`, `pymongo`, `cassandra-driver`, `neo4j` no se importan al arrancar el API (celery solo en `app/tasks/*` y 9 tests; los otros tres, perezosos en `app/db/*`); `pytest*` viaja a producción. 11 de 33 pins son prescindibles (≈61-62 MB de wheels comprimidos, verificado en PyPI; instalado ≈2,5-3×, estimado). Detalle en el anexo D.
8. **[P1] Las únicas mediciones reales de producción muestran trabajo duplicado y polling:** Reportes hace 2 llamadas por carga con 39 consultas cada una (78 en total, 4,6 s de app; `production-latency-20261006-73398218/report.md:12-17`), `/api/notifications` 182 llamadas en 49 min por pestaña (≈3,7/min; `pr117-postmerge-20261005-3c91a3e8/report.md:32`), Dashboard ≈15 solicitudes y Caja ≈18 al cargar (`production-latency-20261005-df079bd4/report.md:15`), `actions/pending` hasta 10,8 s.
9. **[P1] No existe backup/restore probado contra el proveedor** y no hay job/cron de backup en el repo (grep de `pg_dump|backup` en `.github`, `render*.yaml`, compose = 0). El único drill es local (`scripts/backup/verify_local_backup_restore.py:44,157-158`); el registro histórico lo marca P1 (`non-certified-local-preview-static.json:2910-2937`). Escala a P0 si el piloto carga datos reales sobre un plan sin backups gestionados (inferido, no verificado).
10. CORREGIDO (verificación): los `*.html` de marketing son copias de `index.html` con meta tags por ruta (`frontend/marketing-html.mjs`), no HTML estático alternativo: el impacto es SEO/preview de enlaces, no ancho de banda ni LCP (ver sección 2, `vercel.json`). **[P1] (inferido) `vercel.json` raíz carece de los 8 rewrites de marketing de `frontend/vercel.json`** (verificado por diff): si Vercel usa la raíz, `/precios`, `/faq`, `/funciones`, `/pms-hotelero`, `/software-para-hoteles`, `/terms`, `/privacy`, `/contacto` caen al SPA (`/index.html`) y descargan el bundle completo en vez del HTML estático. Needs-verification del Root Directory de Vercel.

Otros hallazgos relevantes no incluidos en el top-10: `staged_http_load.py` no rechaza hosts de producción (200 conexiones concurrentes contra 1 worker); `repair_analytics_facts.py` y `build_shared_sandbox_bootstrap_sql.py` operan sobre la BD productiva sin confirmación fuerte (los datos QA hoteles 16/17 ya conviven con datos reales); `check_release_evidence.py:54-64` invalida la evidencia QA con cualquier commit (incluso docs); Dockerfile backend con `build-essential` innecesario; `docker-compose.yml` levanta 5 almacenes + Celery por defecto; ruta macOS hardcodeada en 36 agentes generados y en `.mcp.json` (anexo C).

---

## Anexo A — Costo/minutos de CI por evento

Runner siempre `ubuntu-latest` (multiplicador ×1). Facturación por job con redondeo al minuto. Solo el e2e tiene duración medida (verificada); el resto es estimado.

| Evento | Workflows que corren | Jobs facturables | Minutos por evento | Base de la cifra |
|---|---|---|---|---|
| PR abierto / push al PR / reabierto (sin etiqueta) | `pr-validation` (backend, frontend, e2e) + `preview-qa` | 4 | **≈ 29-35** | e2e 16,1 min **verificado** (`performance-cloud-retest-20261005/report.md:63`); backend ≈ 8-12 (pytest 2.851 tests = 342 s en Mac según `postmerge-readonly…/report.md:60`, + setup + 173 migraciones sobre SQLite); frontend ≈ 4-6; preview-qa ≈ 1 (mínimo). Estimados |
| Reintento de un job fallido del PR | el job reintentado (p. ej. e2e) | 1 | ≈ 16 si es e2e | Hubo un reintento por flaky E2E (`performance-cloud-retest…/report.md:63`) |
| PR con etiqueta `require-provider-qa`: cada `opened/synchronize/reopened/ready_for_review/labeled/unlabeled` | `release-gate` + `trusted-release-gate` (+ `pr-validation`/`preview-qa` solo en opened/synchronize/reopened) | +2 | **+2-4** por evento (1-2 c/u; clona historia completa y reinstala runtime hash-locked sin caché) | Estimado; `label/unlabel/ready_for_review` no relanzan pr-validation pero sí estos dos |
| PR sin etiqueta: eventos `labeled/unlabeled/ready_for_review` | `release-gate`, `trusted-release-gate` | 0 (jobs omitidos por `if`) | 0 | `release-gate.yml:12`, `trusted-release-gate.yml:14` |
| Merge / push a `main` | `build-and-push` | 1 | **≈ 7-11** | Estimado (2× `docker build` sin caché + push GHCR); no ejecuta tests |
| `workflow_dispatch` de `verify-preview-providers` | ese workflow | 1 | hasta 45 (tope), típico 15-30 | `timeout-minutes: 45`; polling de deploy hasta 90×10 s (`provision_qa_bootstrap.py:549-557`); estimado |
| Build de preview Vercel / Render previews (manual) | fuera de Actions | 0 | 0 de Actions | Render previews `generation: manual` (`render.yaml:1-4`) |

Proyección ilustrativa (no medida): 40 pushes a PR/mes × ≈32 min + 15 merges × ≈9 min ≈ **1.415 min/mes**; con ≈63 pushes de PR (sin merges) ya se llega a los 2.000 min. En 15 días de octubre hubo 113 commits en el historial local (cada push a un PR consume una corrida completa).

Palancas con mayor ahorro/esfuerzo (sin implementar): (1) `concurrency` con `cancel-in-progress` en `pr-validation`; (2) `paths-ignore`/`paths` para que docs/knowledge/qa/.graphify no corran backend+e2e; (3) cachear `~/.cache/ms-playwright` o correr e2e solo cuando cambian `frontend/` o `app/`; (4) eliminar `build-and-push` o pasarlo a manual con caché; (5) `buildFilter` en Render; (6) quitar `validate_gcp_readiness.py` del PR; (7) `timeout-minutes` en los jobs sin tope.

---

## Anexo B — Solapamientos entre workflows / crons / scripts

| # | Solapamiento | Dónde |
|---|---|---|
| 1 | **Barrido de no-shows / notificaciones / reportes ×3**: cron Render `*/5` (`run_scheduled_hotel_jobs`), cron Render horario (`run_no_show_sweep`, `render-no-show-cron.yaml:7-9`) y Celery beat (`app/tasks/celery_app.py:167`, `docker-compose.yml:103-129`). El segundo apunta a un servicio inexistente en `render.yaml` (L14-17 vs `render.yaml:10`) | `render.yaml:139-148`, `render-no-show-cron.yaml`, `docker-compose.yml`, `app/services/scheduled_hotel_jobs_service.py:13` |
| 2 | **Gates de release ×2**: `release-gate.yml` (`check_release_evidence.py`) y `trusted-release-gate.yml` (`trusted_release_gate.py`) responden la misma pregunta con dos implementaciones, con la misma etiqueta y los mismos 6 tipos de evento | `.github/workflows/release-gate.yml:5,12`, `trusted-release-gate.yml:5,14` |
| 3 | **Validación de agentes/skills/JSON ×2**: `preview-qa.yml:30-35` y `validate_setup.py:31-39` (vía `release-gate.yml:27`) | idem |
| 4 | **Instalación del runtime hash-locked ×4** workflows, cada uno con su propio checkout + setup-python sin caché | `preview-qa.yml:24-27`, `release-gate.yml:22-25`, `trusted-release-gate.yml:27-30`, `verify-preview-providers.yml:53-56` |
| 5 | **Verificación de proveedores ×3 por ciclo** | `verify-preview-providers.yml:91,127,200` |
| 6 | **Arranque ×6, puertos distintos**: `render.yaml:16` (PORT/8000, 1 worker, graceful 30), `Procfile:1` y `start.sh:13` (migran en cada arranque, sin graceful), `Dockerfile.backend:29` (8000 fijo, sin migrar), `nodemon.json:5` (8040, reload doble), `docker-compose.yml` (8000 + worker + beat); sin gunicorn en ninguno | ver sección 2 |
| 7 | **Migraciones**: `preDeployCommand` (`render.yaml:15`) vs `Procfile:1`/`start.sh:10` (cada arranque) vs CI (`pr-validation.yml:23-27`) vs `QA_RUN_MIGRATIONS` (`bootstrap_cloud_qa.py:1149`) | idem |
| 8 | **Seeds ×5**: `seed_e2e_backend.py`, `seed_f003_load_scenario.py` (extiende el anterior), `seed_marketing_demo.py` (duplica ≈60 % del E2E), `bootstrap_cloud_qa.py:upsert_qa_data`, `build_shared_sandbox_bootstrap_sql.py` (otro seed, en SQL) | `scripts/` |
| 9 | **Configuración de Vercel ×2**: `vercel.json` raíz vs `frontend/vercel.json` (difieren en rewrites, `outputDirectory`, `installCommand`) | raíz y `frontend/` |
| 10 | **Dos pipelines de build del backend**: Render nativo (`pip install`) y Docker (`build-and-push`), solo el primero se despliega | `render.yaml:14`, `build-and-push.yml` |
| 11 | **Versiones de Python**: 3.11 (backend CI, `runtime.txt`, Dockerfile) vs 3.12 (e2e CI, workflows QA, local) | ver sección 1 |
| 12 | **Pins duplicados**: `requirements.txt` vs `requirements-qa-trusted.txt` (cryptography 50.0.1 vs 46.0.6) | `requirements.txt:29`, `requirements-qa-trusted.txt:3` |
| 13 | **Catálogos de QA derivados de una misma fuente**: `regression-catalog.json` y `shared-sandbox-catalog.json` salen de `CASE_SPECS` (`normalize_qa_catalog.py:22-68`); el histórico de julio está duplicado en JSON y MD (`shared-production-20260724.{json,md}`) | `qa/` |
| 14 | **Skills**: `render_skills.py` genera 18, `.agents/skills` contiene 23; `sync_skills.py --write` borra `.claude/skills` y lo copia de nuevo | `scripts/agent_ops/` |
| 15 | **Reportes de QA operativa repiten los mismos hallazgos**: 6 de los 11 `report.md` mencionan Redis desconectado/caído (grep), y varios repiten Render Free y `actions/pending` lento | `qa/operational/runs/*/report.md` |

---

## Anexo C — Rutas hardcodeadas y secretos embebidos

### C.1 Rutas del entorno del autor

| Archivo:línea | Tipo | Detalle | Impacto |
|---|---|---|---|
| `scripts/agent_ops/render_agents.py:40` | macOS | `/Users/maximopaulos/AI-Workspace/memory/tools/memoryctl` dentro de la plantilla de instrucciones | Se propaga a **36 archivos generados** (18 `.claude/agents/*.md` + 18 `.codex/agents/*.toml`, grep) y a las instrucciones de cada subagente; rompe en cualquier otro equipo/CI |
| `scripts/agent_ops/normalize_graphify_portability.py:6` | macOS (solo docstring) | menciona `/Users/...` como ejemplo | ninguno |
| *(fuera de mi parte, por grep)* `.mcp.json:4,16` | macOS | `command` apunta a `/Users/maximopaulos/.local/node/bin/npx` | **verificado**: es la causa de los `ENOENT … posix_spawn '/Users/maximopaulos/.local/node/bin/npx'` de los servidores MCP `stripe` y `supabase` en esta sesión |
| *(fuera de mi parte)* `.claude/settings.json:12,26,41`, `.codex/hooks.json:13` | macOS | hooks `memory_hook.py` en `/Users/maximopaulos/AI-Workspace/...` (SessionStart, SubagentStart, PreToolUse Glob\|Grep) | fallan en cada evento fuera del Mac del autor |
| *(fuera de mi parte)* `CLAUDE.md` (2), `AGENTS.md` (2), `knowledge/README.md`, `knowledge/00-control/{DECISION-LOG,SOURCE-OF-TRUTH}.md`, `knowledge/_generated/graphify-summary.md`, `docs/{HOTEL_PMS_MASTER_DEVELOPMENT_SPEC,mcp-and-agents-setup,mobile-first-operations-implementation,orchestrator-status}.md`, `.superpowers/sdd/*` (10 ocurrencias en 3 archivos) | macOS | referencias documentales | solo documentación |
| `docs/orchestrator-status.md:88` *(fuera de mi parte)* | Windows | cita `cwd="C:\\PROJECTO\\Hotel-Chipre-PMS"` como bug de migración (histórico) | 0 ocurrencias de `C:\PROJECTO` en código de mi parte (grep de `C:\\`, `C:/`, `PROJECTO`) |
| `scripts/seed_e2e_backend.py:177-181` | Windows (vestigial) | normaliza `\` y letra de unidad en la URL SQLite | inocuo; código de compatibilidad |

### C.2 Identificadores de proveedor fijos (no son secretos)

- CORREGIDO (verificación): las citas correctas son `scripts/README.qa-bootstrap.md:22` (no :23) y `qa/operational/runs/shared-sandbox-campaign-20260812/report.md:5` (no :7). Ref Supabase de **producción** `ezkljznogqpmrjxyvklr`: `scripts/agent_ops/build_shared_sandbox_bootstrap_sql.py:22` (allowlist del SQL de siembra), `scripts/bootstrap_cloud_qa.py:104` (lista negra), `scripts/README.qa-bootstrap.md:23`, `qa/operational/runs/shared-sandbox-campaign-20260812/report.md:7`.
- Repositorio `Maximo-Paulos/Hotel-Chipre-PMS`: `qa/preview-manifest.example.json:14`. Dominios `hotels-pms.com`/`app.`/`api.`: `scripts/agent_ops/check_qa_evidence.py:36`, `validate_preview_manifest.py:29`, `verify_preview_providers.py:53`, `verify_preview_bundle.py:21`, `qa/operational/shared-sandbox-catalog.json:5-8`.

### C.3 Secretos / credenciales embebidos (tipo y ubicación; **valores no copiados**)

Búsqueda de patrones de claves reales (`sk_live`, `AKIA…`, `ghp_`, `xox*`, JWT, `PRIVATE KEY`, `re_…`, `APP_USR-`, `AIza…`) en todo mi alcance: **0 coincidencias**. Lo que sí hay son credenciales de prueba/demo:

| Archivo:línea | Tipo | Alcance |
|---|---|---|
| `scripts/seed_e2e_backend.py:216` | contraseña de owner E2E por defecto | solo `APP_ENV=test` |
| `scripts/seed_e2e_backend.py:225,229,233` | contraseñas de manager/recepción/housekeeping E2E | idem |
| `scripts/seed_e2e_backend.py:419-423` | contraseña de owners step-up + secreto TOTP base32 de prueba | idem |
| `scripts/seed_e2e_backend.py:171,192` | secreto JWT de prueba (`setdefault`) | idem; repetido en `frontend/playwright.config.ts:57,81-84,233` |
| `scripts/seed_marketing_demo.py:31,389` (y `:40`) | contraseña del owner demo (impresa en consola) + JWT demo | BD SQLite `demo-marketing.db` |
| `docker-compose.yml:9-10,59,68,85,98,111,125` | contraseña de Postgres `pms`, `NEO4J_AUTH`/`NEO4J_PASSWORD`, DSN con credenciales | desarrollo local; puertos publicados en todas las interfaces |
| `qa/preview-manifest.example.json:44` | `baseline_lease_id` de ejemplo (ficticio, forma realista) | ejemplo versionado |
| `qa/trust/qa-evidence-public-key.pem` | clave **pública** Ed25519 | no es secreto |

---

## Anexo D — Tabla de dependencias prescindibles (`requirements.txt`, 33 pins directos)

Conteos de módulos: `grep` de `^\s*(from|import) <paquete>` sobre `app/` (incluye imports perezosos indentados). Pesos: wheel cp311 manylinux x86_64 comprimido, verificado en PyPI (no es el tamaño instalado).

**Prescindibles en runtime de piloto (11):**

| Paquete (pin) | Módulos de `app/` que lo importan | Otros usos | Peso / arrastra | Veredicto |
|---|---|---|---|---|
| `ortools==9.12.4544` | **1** (`services/allocation_engine.py:226`, import perezoso con `except ImportError → _run_allocation_greedy`) | 0 tests, 0 scripts | **24,9 MB**; `requires_dist`: absl-py, **numpy** (≈16,8 MB), **pandas** (≈13,1 MB), protobuf<5.30, immutabledict | Quitar o mover a extra opcional: sin él queda la asignación greedy. CP-SAT usa `num_workers=1` y hasta 30 s (`allocation_engine.py:498-505`) en una instancia de 0,5 CPU/512 MB |
| `celery==5.4.0` | **1** (`tasks/celery_app.py`; los otros 8 módulos de `app/tasks/` lo usan vía ese archivo); el API nunca importa tareas (único import externo: `app/scripts/run_notification_cycle.py:17`, perezoso) | 9 archivos de test importan `app.tasks` | 0,4 MB + billiard, kombu, amqp, vine, click×3, tzdata | Mover a `requirements-worker.txt`/dev; producción presupuesto no corre Celery (`render.yaml:7-8`) |
| `pymongo==4.9.2` | 1 (`db/mongo.py:22`, perezoso) | — | 1,7 MB + dnspython | Prescindible con `MONGO_ENABLED=false` |
| `cassandra-driver==3.29.2` | 1 (`db/cassandra.py:26`, perezoso) | 1 test | 3,9 MB + geomet | Prescindible con `CASSANDRA_ENABLED=false` |
| `neo4j==5.25.0` | 1 (`db/neo4j.py:22`, perezoso) | — | 0,3 MB + pytz | Prescindible con `NEO4J_ENABLED=false` |
| `pytest==9.0.3`, `pytest-asyncio==1.4.0`, `pytest-cov==7.1.0` | 0 | 219 archivos de `tests/` | 0,4 MB + coverage 0,2 MB + pluggy/iniconfig | Mover a `requirements-dev.txt`; hoy se instalan en Render y en la imagen Docker |
| `python-dateutil==2.9.0` | 0 imports directos | 0 | pequeño | Redundante: ya llega como dependencia de celery/pandas; no se importa en ningún lado |
| `protobuf==5.29.6` (pin transitivo, `requirements.txt:34`) | 0 | — | 0,2 MB | Sale junto con `ortools` |
| `pyOpenSSL==26.4.0` (pin transitivo, `requirements.txt:35`) | 0 | — | pequeño | Sale junto con `paypalrestsdk` |

Suma verificada de lo evitable con los 9 primeros ítems: ortools 24,9 + pandas 13,1 + numpy 16,8 + cassandra 3,9 + pymongo 1,7 + neo4j 0,3 + celery 0,4 ≈ **61 MB** de wheels (+ pytest/coverage ≈ 0,6 MB). Instalado, estimado ≈ 2,5-3× (≈150-180 MB en `site-packages`). Se evitan además ≈ 30 paquetes transitivos de build (pip resolve/descargas).

**Condicionales a flags apagados en el piloto (4):**

| Paquete | Módulos de `app/` | Observación |
|---|---|---|
| `mercadopago==2.2.2` | 1 (`adapters/mercadopago_adapter.py:31`, perezoso) | `CONNECTIONS_ENABLED=false` en `render.yaml:36-37`. Única fuente de `requests` junto con paypalrestsdk (verificado en PyPI) |
| `paypalrestsdk==1.13.3` | 1 (`adapters/paypal_adapter.py:39`, perezoso) | arrastra requests, six, pyOpenSSL; `PAYPAL_MODE=sandbox` |
| `google-auth==2.35.0` | 1 (`api/auth.py:14-15`, **import eager**) | `GOOGLE_LOGIN_ENABLED=false` (`render.yaml:74-75`); hacerlo perezoso evita cargar google-auth + requests + urllib3 en el arranque |
| `redis==5.1.1` | 5 (`infrastructure/redis_backend.py`, `services/{domain_events,read_model_cache,distributed_lock}.py`, `api/collaboration.py`; imports eager) | `REDIS_URL=""` en `render.yaml:72-73`; 0,3 MB, pero el servicio vivo lo tiene habilitado-desconectado (ver hallazgo 1) |

**Imprescindibles (para no confundirlos):** `fastapi` (86 módulos), `starlette` (2, pin de CVE), `uvicorn` (1), `websockets` (0 imports directos pero lo usa uvicorn para `@router.websocket("/ws")`, `api/collaboration.py:672`), `sqlalchemy` (254), `pydantic` (74), `pydantic-settings` (1), `httpx` (7), `alembic` (preDeploy/env.py), `psycopg2-binary` (1 + SQLAlchemy driver), `passlib[bcrypt]`+`bcrypt` (1) y `argon2-cffi` (0 imports directos, pero es el esquema por defecto de passlib: `services/security.py:30-37`), `PyJWT` (2), `email-validator` (2 + `EmailStr`), `cryptography` (5), `pyotp` (3), `Pillow` (3, imports eager: `payment_proof_service.py:15`, `analytics_exports.py:13`, `cash_expense_service.py:15`).

**Declaración faltante:** `requests` lo importan 8 módulos de `app/` (`services/ota/adapters/booking.py:18`, `services/integration_service.py:6`, `services/email/providers.py:8`, `services/hotel_outbound_email_service.py:9`, `services/payment_webhook_service.py:17`, `services/payment_link_test_service.py:9`, `master_admin/stripe.py:7`, y perezoso en `services/payment_link_service.py:62`) y **no figura en `requirements.txt`**: solo llega transitivamente por `mercadopago`/`paypalrestsdk`. Si se quitan esos SDKs hay que declarar `requests` (o migrar a `httpx`, que ya está).

---

## Anexo E — Archivos enormes, generados o duplicados (leídos completos)

No se resumió ninguno por estructura: los archivos grandes se leyeron enteros en tramos ≤ 700 líneas.

| Archivo | Líneas / bytes | Naturaleza | Nota |
|---|---|---|---|
| `qa/history/observations/non-certified-local-preview-static.json` | 3.080 / 197.557 B | histórico generado (90 registros, partido por `normalize_qa_catalog.py:88`) | bitácora de julio de 2026; candidato a salir del checkout; contiene los hallazgos de backup, idempotencia de reservas y exports sin UI |
| `qa/regression-catalog.json` | 2.159 / 49.828 B | generado desde `CASE_SPECS` | 45 casos / 335 triplets; texto repetido |
| `qa/operational/shared-sandbox-catalog.json` | 1.024 / 27.283 B | generado de la misma fuente | 45 casos × 2 dispositivos |
| `qa/operational/runs/shared-sandbox-campaign-20260812/observations.json` | 838 / 48.677 B | bitácora manual de 52 observaciones | sin artefactos |
| `qa/history/observations/shared-production-20260724.{json,md}` | 377 + 236 / 16.433 + 17.050 B | mismo contenido en dos formatos | duplicado |
| `scripts/agent_ops/verify_preview_providers.py` | 1.115 | código (no generado) | el archivo más largo de la parte |
| `scripts/bootstrap_cloud_qa.py` | 1.172 | código | solo QA |
