# Bootstrap cloud QA

`bootstrap_cloud_qa.py` crea de forma idempotente un hotel sintético y cuatro
usuarios de base (`owner`, `manager`, `receptionist`, `housekeeping`). La quinta
persona, `master-admin`, no vive en la base: el script exige que su identidad QA
coincida con `MASTER_ADMIN_EMAIL`, `MASTER_ADMIN_PASSWORD` y `MASTER_ADMIN_PIN`
del backend preview.

En la creación inicial del run, el estado queda deliberadamente con
`finished=false`: el owner debe entrar por la UI visible y completar el cierre
del onboarding. Un rerun idempotente no vuelve a abrir un onboarding ya
completado ni reemplaza los datos que una persona haya guardado desde la UI.
Los cuatro usuarios se insertan activos y verificados únicamente como seed
técnico aislado. Eso no demuestra registro, entrega de email, verificación de
correo ni invitación de staff: esos flujos sólo cuentan como evidencia QA cuando
el agente los ejecuta por la interfaz y adjunta la evidencia humana requerida.

El script falla antes de conectarse si `APP_ENV` no es `qa`/`preview`, si
`QA_DATABASE_ISOLATED` no es `true`, si la identidad no secreta del DSN no
coincide con `QA_EXPECTED_DATABASE_*` (host, puerto, base y usuario), o si la
identidad contiene el project ref productivo conocido
`ezkljznogqpmrjxyvklr`. Para una Supabase branch, el productor confirma el
usuario observado. Un rol personalizado debe ser distinto del productivo; los
modos `preview` y `dedicated-qa-project` pueden usar el rol estándar `postgres`
sólo si la evidencia Ed25519 válida liga project ref, host, fingerprint,
servicio, SHA y entorno aislados. Los targets que no estén verificados por la
API de Supabase siguen necesitando un rol cuyo nombre identifique QA.

El modo con una Supabase Branch real usa
`isolation_mode=supabase-branch-per-target` y rechaza cualquier variable de
lease de baseline. El segundo proyecto gratuito compartido sólo se admite como
baseline serializado: el manifiesto/token deben usar
`isolation_mode=dedicated-qa-baseline-exclusive` y Render debe observar
`QA_BASELINE_ONLY=true`, `QA_BASELINE_LEASE_ID`,
`QA_BASELINE_LEASE_TARGET_SHA` y `QA_BASELINE_LEASE_TARGET_BRANCH` exactamente
iguales al lease firmado para ese SHA/rama. El lease es aleatorio y de alta
entropía; nunca se deriva del nombre de rama o commit. Una ausencia, reutilización
concurrente o diferencia se rechaza antes de conectar a la base.

Las variables `QA_PRODUCTION_*` autoatestadas ya no autorizan nada. Render debe
recibir un `QA_PROVIDER_EVIDENCE_TOKEN` Ed25519 de vida corta, generado a partir
de un manifiesto provider-verificado schema v2 o v3. El token liga el
fingerprint real del DSN, branch/project ref, usuario DB, SHA, service id,
environment id y deployment Vercel. La procedencia debe incluir exactamente
las APIs de Render, Supabase y Vercel.
Sin token válido, con firma incorrecta, vencido o perteneciente a otro deploy,
el bootstrap falla antes de conectar.

Variables requeridas del backend (guardar valores reales sólo en el entorno
seguro del preview, nunca en Git ni en `.env.qa.local`):

- `APP_ENV=preview`
- `EMAIL_PROVIDER=null`, `CONNECTIONS_ENABLED=false`, `PAYPAL_MODE=sandbox`
- `AI_ENABLED=false`, `AI_PROVIDER=disabled`, `GEMMA_ENABLED=false`, `GEMMA_PROVIDER=disabled`
- ausencia total de credenciales Resend/Gmail/Mercado Pago/PayPal/OTA/AI/Gemma
- `DATABASE_URL`
- `QA_DATABASE_ISOLATED=true`
- `QA_EXPECTED_DATABASE_HOST`, `QA_EXPECTED_DATABASE_PORT`, `QA_EXPECTED_DATABASE_NAME`, `QA_EXPECTED_DATABASE_USER`
- `QA_DATABASE_BRANCH_REF`
- `QA_PROVIDER_EVIDENCE_TOKEN` y `QA_PROVIDER_EVIDENCE_PUBLIC_KEY`
- built-ins Render `RENDER_SERVICE_ID` y `RENDER_GIT_COMMIT`
- `QA_RUN_ID`, `QA_EMAIL_DOMAIN` y `QA_EMAIL_DOMAIN_IS_DEDICATED=true`
- email/contraseña para `QA_OWNER`, `QA_MANAGER`, `QA_RECEPTION` y `QA_HOUSEKEEPING`
- `QA_MASTER_ADMIN_EMAIL`, `QA_MASTER_ADMIN_PASSWORD`, `QA_MASTER_ADMIN_PIN`
- las tres variables runtime `MASTER_ADMIN_*` con los mismos valores QA
- `QA_RUN_MIGRATIONS=true` sólo si el job debe ejecutar Alembic antes del seed

El proveedor observa todos esos valores y publica únicamente un hash combinado
`bootstrap_configuration_fingerprint` (`qa-bootstrap-config-v2`). El token lo
firma y Render lo recalcula antes de instalar la capacidad; cambiar un email,
password, PIN, run id, migraciones o switch de integración invalida el bootstrap
sin revelar hashes individuales ni valores sensibles.

Las cinco identidades sintéticas locales se generan una vez, sin imprimir sus
secretos, mediante:

```bash
python scripts/agent_ops/generate_qa_local_env.py
```

El archivo `.env.qa.local` queda ignorado y con modo `0600`; contiene solamente
las URLs y variables declaradas por `.env.qa.example`. No acepta el dominio
productivo raíz, no escribe DSN, tokens o claves, y no reemplaza un archivo
existente salvo una rotación explícita con `--rotate`.

## Producción de evidencia

La integración puede usar un rol exclusivo de la branch, por ejemplo
`hotel_pms_qa_bootstrap`, o el rol Supabase estándar `postgres` cuando todas
las identidades aisladas estén verificadas por proveedor. Luego:

1. Generar el manifiesto con APIs Render/Supabase y validarlo con
   `scripts/agent_ops/validate_preview_manifest.py`.
2. Calcular `database.connection_fingerprint` como SHA-256 según
   `fingerprint_method=sha256` y
   `fingerprint_payload_version=supabase-connection-v1`. El payload exacto es
   `project_ref + "\x1f" + canonical_host + "\x1f" + decimal_port + "\x1f" + db_user`.
   `canonical_host` es IDNA ASCII, lowercase y sin punto final. La salida es
   `sha256:<hex>`. Password y nombre de base no participan; aun así el
   consumidor exige que la base sea exactamente `postgres`. La autenticidad
   no depende de este hash: proviene de la firma Ed25519 del token.
3. Generar una clave Ed25519, guardar `QA_PROVIDER_EVIDENCE_PRIVATE_KEY` sólo
   en el productor confiable y provisionar únicamente su correspondiente
   `QA_PROVIDER_EVIDENCE_PUBLIC_KEY` en Render. Ejecutar el emisor con la clave
   privada; el DSN permanece dentro de la consulta provider-verificada y nunca
   se exporta al proceso emisor. Ambas variables de clave aceptan PEM o base64
   estricto de los 32 bytes raw Ed25519:

```bash
python scripts/issue_qa_provider_evidence.py provider-manifest.json \
  --output "$RUNNER_TEMP/qa-provider-evidence.token"
```

4. El workflow confiable conserva el archivo sólo en `$RUNNER_TEMP`, provisiona
   su contenido como `QA_PROVIDER_EVIDENCE_TOKEN` del servicio Render preview y
   lo elimina de Render al terminar el deploy, también ante fallos. Nunca cruza
   workflows ni se publica como artefacto. La clave privada nunca existe en
   Render y la pública no permite emitir tokens. La capacidad vence como máximo
   en una hora (`QA_PROVIDER_EVIDENCE_TTL_SECONDS`, default 900 segundos).

Antes de instalar el token, el provisionador relee por API el servicio, sus
variables y el deploy verificado. Exige service/environment IDs, repo, rama,
health path, `preDeployCommand=python scripts/bootstrap_cloud_qa.py`, URLs,
lease, `APP_ENV` e identidad/fingerprint de `DATABASE_URL` ligados al manifiesto.
Cualquier drift aborta sin PUT ni POST. Después sólo acepta como exitoso el
deploy creado para el commit exacto cuando Render informa `live` y fecha de
finalización; `pre_deploy_failed` es terminal y nunca cuenta como bootstrap.

El emisor acepta schema v2/v3 con procedencia v2 y los campos provider estables,
incluidos los modos `preview` y `dedicated-qa-project`. Hasta que el
workflow/provider complete este intercambio, el comportamiento esperado es
fail-closed.

Ejecución:

```bash
python scripts/bootstrap_cloud_qa.py
```

La salida sólo informa el `run_id` y conteos de personas. Nunca muestra DSN,
emails, contraseñas ni PIN. El bootstrap marca el hotel en `extra_policies` y se
niega a modificar hoteles o usuarios que no pertenezcan al mismo run sintético.
