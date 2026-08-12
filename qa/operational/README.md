# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

Este árbol contiene campañas funcionales sobre el sandbox compartido que conserva
`APP_ENV=production`. No certifica un preview aislado y ningún archivo bajo
`qa/operational/` es elegible para el release gate formal.

La fuente normativa de esta campaña es `shared-sandbox-catalog.json`. Cada ejecución
versiona metadatos y observaciones redactadas bajo `runs/<run-id>/`; screenshots,
trazas, videos y DOM quedan fuera de Git bajo
`artifacts/qa-operational/<run-id>/` y se referencian únicamente por ID y SHA-256.

Inicializar y validar una campaña:

```bash
.venv312/bin/python scripts/agent_ops/operational_qa.py init \
  --run-id <run-id> \
  --code-sha <sha-de-40-caracteres>

.venv312/bin/python scripts/agent_ops/operational_qa.py validate \
  qa/operational/runs/<run-id> \
  --require-complete
```

Cada observación debe registrar el caso operativo, persona, dispositivo, URL,
precondiciones, acciones humanas, resultado esperado y observado, estado, severidad,
artefactos, SHA, referencias sintéticas creadas y estado de limpieza. Los secretos,
cookies, tokens, emails completos y PII no forman parte de la evidencia.
