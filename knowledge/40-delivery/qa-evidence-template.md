# Plantilla de evidencia QA

Crear `qa/evidence/<task-id>/summary.json` con campos no sensibles:

```json
{
  "task_id": "feature-123",
  "code_sha": "abcdef1",
  "preview": {"app_url": "https://...", "api_url": "https://..."},
  "executed_at": "2026-07-18T00:00:00Z",
  "results": [{"persona": "owner", "case_id": "dashboard-permissions", "status": "passed", "preview_url": "https://...", "precondition": "owner QA activo", "human_action": "iniciar sesión y abrir dashboard", "expected": "dashboard permitido", "observed": "dashboard permitido", "evidence": "sha256:...", "code_sha": "abcdef1"}],
  "external_exclusions": ["payment completion", "emails", "webhooks", "OTA"],
  "blocked": false
}
```

Los binarios (captura, trace, video) viven en `artifacts/qa/` ignorado por Git y se referencian por hash. No incluir URLs con credenciales, cookies, tokens, emails personales o PII.
