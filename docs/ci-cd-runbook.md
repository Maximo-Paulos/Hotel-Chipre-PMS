# CI/CD y ambientes seguros

Estado de TECH-0112 al 2026-08-21: `BLOCKED` para el cierre completo. El
contrato versionado tiene controles verificables, pero staging, las
protecciones de rama y la configuración de ambientes/secrets de los
proveedores todavía requieren una acción humana autorizada.

## Pipeline objetivo

```text
feature branch
  -> PR
  -> tests + lint/build + migraciones en DB descartable
  -> preview aislado y QA trusted con evidencia ligada a SHA
  -> staging aislado + verificación humana/proveedor
  -> aprobación protegida
  -> main
  -> build de artefactos inmutables con tag SHA
  -> producción sólo con el mismo SHA y aprobación humana
```

Un agente puede preparar código, tests y evidencia. No puede hacer un cutover
a usuarios reales ni operar secretos de proveedor.

## Qué queda cerrado en esta PR

- `.github/workflows/pr-validation.yml` aplica `alembic upgrade head` sobre
  `sqlite:///./ci-migrations.db` descartable antes de ejecutar los tests. No
  toca ninguna base compartida.
- `.github/workflows/preview-qa.yml` sigue siendo un contrato no confiable: no
  tiene secrets, artifacts de proveedor ni permisos `actions: read`.
- `.github/workflows/verify-preview-providers.yml` ya limita el ciclo trusted a
  la rama default, exige IDs QA distintos de producción, usa un lease serial y
  valida el mismo `target_sha` antes/después del bootstrap y antes de subir
  evidencia.
- `.github/workflows/release-gate.yml` y
  `.github/workflows/trusted-release-gate.yml` mantienen la evidencia ligada al
  PR head/base y al workflow trusted de la rama default.
- `.github/workflows/build-and-push.yml` sólo ejecuta desde la rama default,
  publica imágenes con tag completo `GITHUB_SHA`, verifica el label
  `org.opencontainers.image.revision` y no publica `latest`. Produce un
  `release-manifest.json` versionado como artifact de CI.
- `scripts/agent_ops/verify_release_sha.py` rechaza un manifest cuyo commit,
  ambiente, repositorio o referencias de artifacts no coincidan, y rechaza
  tags mutables (`latest`, `main`). Es una verificación local; no despliega.
- `render.yaml` conserva `preDeployCommand: python -m alembic upgrade head`.
  No se automatiza `alembic downgrade`: un rollback de schema sin backup y
  compatibilidad comprobada puede causar pérdida de datos.

## Auditoría de gaps

| Requisito | Estado | Evidencia / pendiente |
| --- | --- | --- |
| Feature branch -> PR -> tests | Cerrado en código | `pr-validation.yml`, `release-gate.yml`, `trusted-release-gate.yml` |
| Preview aislado | Parcialmente cerrado | El contrato y el ciclo trusted existen; la evidencia cloud depende de la configuración humana del entorno `preview-qa`. |
| Staging formal | Pendiente humano | No existe un servicio, DB, environment ni workflow de staging confirmado en este checkout. No se inventa uno en esta PR. |
| DB separadas | Parcialmente cerrado | El preview trusted compara recursos QA/prod; staging y producción deben ser confirmados por proveedor. |
| Secrets separados | Parcialmente cerrado | Los nombres/configuración son versionables y los valores quedan fuera de Git; falta configurar y auditar scopes por environment. |
| Migraciones controladas | Cerrado en código, operación pendiente | PR usa DB descartable y Render declara pre-deploy Alembic; falta ejecutar y registrar un drill real por ambiente. |
| Rollback | Documentado, no automatizado | Ver procedimiento debajo; no hay proveedor/servicio autorizado para implementar un rollback automático. |
| Release atada a SHA | Cerrado para artifacts CI; pendiente de runtime cloud | Imágenes y manifest son SHA-only; staging/producción deben demostrar que el runtime desplegado es ese SHA. |
| No experimentos directos a usuarios reales | Bloqueado por configuración externa | `render.yaml` aún declara `autoDeploy: true`; una persona debe imponer aprobación/entorno protegido en el proveedor antes de certificar este punto. |

## Procedimiento de rollback / forward-fix

Este runbook no ejecuta comandos contra Render, Vercel, Supabase ni GitHub.
Una persona con autorización operativa debe:

1. Detener la promoción y registrar el SHA desplegado, el SHA objetivo, el
   ambiente, la hora UTC y el incidente. No usar `latest` ni una rama como
   identificador.
2. Seleccionar el último SHA conocido bueno y obtener su manifest de release.
   Validarlo localmente, sin secretos:

   ```bash
   .venv/bin/python scripts/agent_ops/verify_release_sha.py \
     /ruta/al/release-manifest.json \
     --expected-sha <SHA_CONOCIDO_BUENO> \
     --expected-repository <owner/repository> \
     --expected-environment staging
   ```

3. En el proveedor, fijar el servicio al artifact exacto de ese SHA. No
   cambiar la DB a mano ni borrar migraciones para hacer coincidir versiones.
4. Verificar health, logs sin secretos, smoke tests operativos y que la
   evidencia del proveedor muestre el mismo SHA. En producción se requiere la
   aprobación definida por el environment protegido.
5. Tratar el schema por separado: si el código anterior es compatible con el
   schema actual, hacer rollback de aplicación y preparar un forward-fix. Sólo
   hacer `alembic downgrade` después de backup/restore drill, revisión de
   compatibilidad y autorización humana explícita; nunca como paso automático.
6. Si el rollback de schema no es seguro, mantener la aplicación en el SHA
   compatible, preservar la base y corregir hacia adelante en una rama nueva.
   Registrar la revisión Alembic antes y después (`alembic current` y
   `alembic heads`) en el incidente.

## Acciones humanas necesarias para desbloquear el cierre

1. Crear y nombrar formalmente los environments GitHub `staging` y
   `production`, con reviewers requeridos para producción y sin permitir que
   un PR no confiable lea sus secrets.
2. Configurar branch protection de `main`: PR obligatorio, checks de
   `pr-validation`, `release-gate` y `trusted-release-gate`, y bloqueo de push
   directo. Esta configuración está fuera del repositorio y no se modifica en
   esta PR.
3. Crear o confirmar un backend, frontend y PostgreSQL/Supabase de staging
   independientes de producción. Confirmar por IDs/hosts que DB, Redis,
   JWT/keys, URLs, CORS y secrets no se comparten. Guardar sólo nombres,
   fingerprints no sensibles y referencias en la evidencia.
4. Definir el mecanismo autorizado de deploy a staging y producción para que
   consuma el artifact/manifest del SHA aprobado, no `latest` ni el estado
   mutable de una rama. Debe publicar la revisión observada para que
   `verify_release_sha.py` pueda validarla.
5. Desactivar o someter a aprobación humana el auto-deploy productivo del
   proveedor. El `autoDeploy: true` de `render.yaml` es una declaración
   versionada existente, no evidencia de que la cuenta real ya esté protegida.
6. Ejecutar un drill real y aislado de migración, rollback de aplicación y
   forward-fix en staging. Registrar resultado, SHA, revisión Alembic, health
   y evidencia manual. Repetir la verificación sobre producción sólo con
   autorización explícita y sin datos reales durante el ensayo.

## Validación local de esta PR

```bash
python -m pytest -q tests/test_release_sha_validator.py \
  tests/test_release_evidence_contract.py \
  tests/test_preview_manifest_contract.py
```

La sintaxis YAML se valida con `actionlint` si está disponible; de lo
contrario, usar un parser YAML básico y revisar los contratos Python. No se
ejecutó ningún deploy, migración cloud, cambio de secrets, billing o cutover.
