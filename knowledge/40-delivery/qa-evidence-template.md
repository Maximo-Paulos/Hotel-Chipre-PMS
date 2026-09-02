# Plantilla histórica de evidencia QA

La campaña vigente ya no usa este paquete de evidencia de preview para bloquear
un merge. La QA funcional se registra en `qa/operational/runs/<run-id>/` sobre
Render producción; este documento se conserva para interpretar artefactos
históricos de preview.

Estado: `historical` por `scripts/agent_ops/check_qa_evidence.py`.

Cada ejecución vive en `qa/evidence/<task-id>/` y contiene exactamente tres archivos
versionados:

```text
qa/evidence/<task-id>/
  summary.json
  validated-preview-manifest.json
  attestation.json
```

`validated-preview-manifest.json` es el manifiesto no sensible publicado después de
la verificación de proveedores. `summary.json` lo vincula por SHA-256 y conserva los
identificadores de workflow y artefacto usados para obtenerlo.
`attestation.json` es una firma Ed25519 del operador QA sobre los bytes exactos de
ambos JSON, task/SHA/rama/repositorio, timestamp, fingerprint de clave y el inventario
exacto de hashes/paths/tamaños verificados bajo `artifacts/qa/<task-id>/`.

```json
{
  "task_id": "feature-123",
  "code_sha": "abcdef1234567890abcdef1234567890abcdef12",
  "provider_evidence": {
    "manifest_file": "validated-preview-manifest.json",
    "manifest_sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "workflow_run_id": 123456789,
    "artifact_id": 987654321,
    "task_id": "preview-abcdef123456",
    "repository": "Maximo-Paulos/Hotel-Chipre-PMS",
    "git_branch": "codex/feature-preview",
    "workflow_code_sha": "1111111111111111111111111111111111111111",
    "workflow_git_branch": "main"
  },
  "preview": {
    "app_url": "https://hotel-chipre-pms-git-feature.vercel.app",
    "api_origin": "https://hotel-chipre-pms-api-qa.onrender.com",
    "api_url": "https://hotel-chipre-pms-api-qa.onrender.com/api",
    "health_url": "https://hotel-chipre-pms-api-qa.onrender.com/health",
    "vercel_project_id": "prj_qa",
    "vercel_deployment_id": "dpl_qa",
    "render_service_id": "srv-qa",
    "render_deployment_id": "dep-qa",
    "render_environment_id": "env-qa",
    "supabase_project_ref": "qaqaqaqaqaqaqaqaqaqa",
    "supabase_branch_ref": "qaqaqaqaqaqaqaqaqaqa"
  },
  "executed_at": "2026-07-19T16:00:00Z",
  "results": [
    {
      "persona": "owner",
      "case_id": "dashboard-permissions",
      "status": "passed",
      "preview_url": "https://hotel-chipre-pms-git-feature.vercel.app/dashboard",
      "precondition": "owner QA activo",
      "human_action": "iniciar sesión y abrir dashboard",
      "expected": "Dashboard loads only data permitted to the persona.",
      "observed": "dashboard permitido y datos limitados al hotel QA",
      "evidence": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "code_sha": "abcdef1234567890abcdef1234567890abcdef12"
    }
  ],
  "external_exclusions": [
    "payment completion",
    "outgoing email",
    "webhook delivery",
    "OTA operation"
  ],
  "blocked": false
}
```

La matriz real debe incluir exactamente todas las filas de
`qa/regression-catalog.json`; el ejemplo anterior muestra sólo la forma de una fila.
El `code_sha` siempre es completo (40 o 64 caracteres), cada referencia de evidencia
usa `sha256:<64 hex>`, y `executed_at` se expresa en UTC. La regresión debe comenzar
después de `generated_at` del manifiesto y finalizar en un máximo de 24 horas.

Los binarios (captura, trace y video) viven en `artifacts/qa/` ignorado por Git. No
incluir URLs con credenciales, cookies, tokens, emails personales ni PII.

La clave pública estable vive en `qa/trust/qa-evidence-public-key.pem`. La clave
privada nunca se versiona: se carga por `QA_EVIDENCE_OPERATOR_PRIVATE_KEY` o desde
un archivo ignorado bajo `artifacts/qa/`. No se crea una clave real como parte del
código; el bootstrap operativo debe generarla fuera del repositorio y agregar sólo
la pública mediante una entrega separada.

La atestación debe firmarse después de `executed_at` y vence a las 24 horas. La
puerta confiable lee la pública exclusivamente del checkout del SHA base y rechaza
una PR que intente cambiar esa clave al mismo tiempo que presenta evidencia.
