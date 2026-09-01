# CI/CD y ambientes seguros

Estado de TECH-0112 al 2026-09-01: el código de CI y la QA funcional sobre
Render producción están definidos; las protecciones de rama y la configuración
de secrets del environment todavía requieren una acción humana autorizada.

## Pipeline vigente

```text
feature branch
  -> PR
  -> tests + lint/build + migraciones en DB descartable
  -> aprobación protegida
  -> main
  -> build de artefactos inmutables con tag SHA
  -> Render producción auto-deploy del mismo SHA
  -> QA funcional visible sobre el hotel de prueba
```

Las pruebas unitarias, migraciones descartables, lint y build siguen siendo
automáticas en CI. La prueba funcional cloud se ejecuta después del merge sobre
Render producción, con el hotel de prueba autorizado y sin efectos externos.
El workflow sólo lee la API de Render y espera el SHA publicado; no cambia
configuración ni despliega ramas sobre producción.

## Qué queda cerrado en esta PR

- `.github/workflows/pr-validation.yml` aplica `alembic upgrade head` sobre
  `sqlite:///./ci-migrations.db` descartable antes de ejecutar los tests. No
  toca ninguna base compartida.
- `.github/workflows/preview-qa.yml` sigue siendo un contrato no confiable: no
  tiene secrets, artifacts de proveedor ni permisos `actions: read`.
- `.github/workflows/verify-preview-providers.yml` es ahora el ciclo de QA de
  Render producción: se ejecuta en `push` a `main` o manualmente, espera el
  deploy exacto de `GITHUB_SHA`, valida el perfil sin efectos externos y publica
  sólo un manifiesto redactado.
- `.github/workflows/release-gate.yml` y
  `.github/workflows/trusted-release-gate.yml` ya no bloquean un PR por la
  inexistencia de un servicio QA separado. El cierre cloud ocurre después del
  merge mediante el ciclo de Render producción.
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
| QA funcional en Render producción | Workflow cerrado; matriz pendiente | El ciclo verifica el SHA live, el healthcheck, Redis y el perfil de prueba del servicio productivo; la matriz humana se registra en `qa/operational/`. |
| Staging formal | Fuera del flujo elegido | El producto usa Render producción como superficie funcional autorizada para este hotel de prueba. |
| DB separadas | No aplica al flujo productivo autorizado | La selección de hotel y los permisos siguen aislando los datos operativos; no se ejecutan seeds ni migraciones destructivas desde QA. |
| Secrets separados | Parcialmente cerrado | Los nombres/configuración son versionables y los valores quedan fuera de Git; falta configurar y auditar scopes por environment. |
| Migraciones controladas | Cerrado en código, operación pendiente | PR usa DB descartable y Render declara pre-deploy Alembic; falta ejecutar y registrar un drill real por ambiente. |
| Rollback | Documentado, no automatizado | Ver procedimiento debajo; no hay proveedor/servicio autorizado para implementar un rollback automático. |
| Release atada a SHA | Cerrado para artifacts CI; pendiente de runtime cloud | Imágenes y manifest son SHA-only; Render producción debe demostrar que el runtime desplegado es ese SHA. |
| No efectos externos durante QA | Cerrado en código/configuración | El verificador exige `EXTERNAL_EFFECTS_ENABLED=false`, inbound events desactivados, email nulo, PayPal sandbox y conexiones externas desactivadas. |

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
     --expected-environment production
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

## Acciones humanas necesarias para ejecutar QA en producción

1. Mantener configurados `RENDER_PRODUCTION_SERVICE_ID` y `RENDER_API_TOKEN`
   en el environment protegido usado por el workflow. No se necesita
   `RENDER_QA_SERVICE_ID` ni `SUPABASE_QA_PROJECT_REF`.
2. Configurar branch protection de `main`: PR obligatorio, checks de
   `pr-validation`, `release-gate` y `trusted-release-gate`, y bloqueo de push
   directo. Esta configuración está fuera del repositorio.
3. Ejecutar la matriz humana en Chrome sobre el hotel de prueba autorizado,
   registrar el SHA live y guardar observaciones redactadas en
   `qa/operational/runs/<run-id>/`.
4. No completar pagos reales, enviar emails, disparar webhooks/OTAs ni tocar
   datos de otros hoteles. Si el perfil seguro no coincide, el workflow debe
   fallar y la prueba queda bloqueada.

## Validación local de esta PR

```bash
python -m pytest -q tests/test_production_render_verifier.py \
  tests/test_release_sha_validator.py \
  tests/test_release_evidence_contract.py \
  tests/test_preview_manifest_contract.py \
  tests/test_compare_preview_manifests.py
```

La sintaxis YAML se valida con `actionlint` si está disponible; de lo
contrario, usar un parser YAML básico y revisar los contratos Python. No se
ejecutó ningún deploy, migración cloud, cambio de secrets, billing o cutover.
