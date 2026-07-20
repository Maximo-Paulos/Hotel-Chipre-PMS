# Evidencia QA versionable

Crear un directorio por tarea con `summary.json`, su hermano
`validated-preview-manifest.json` y `attestation.json`, siguiendo
`knowledge/40-delivery/qa-evidence-template.md`. Sólo se versionan resultados
redactados, el manifiesto proveedor no sensible y hashes de artefactos. Screenshots,
trazas, videos, perfiles y sesiones van a `artifacts/qa/` (ignorado).
Como la atestación versiona los paths relativos, los nombres de archivo también
deben ser identificadores no sensibles, sin emails, nombres de huéspedes ni PII.

Después de completar la matriz, el operador firma localmente. El comando comprueba
que cada hash `evidence` corresponde a exactamente un archivo real bajo el root
indicado y rechaza symlinks. La clave privada se carga desde
`QA_EVIDENCE_OPERATOR_PRIVATE_KEY` o desde un archivo bajo `artifacts/qa/`; nunca se
versiona ni se pasa como argumento. Si se usa un archivo, debe tener permisos
exclusivos del propietario (`chmod 600`):

```bash
.venv/bin/python scripts/agent_ops/qa_evidence_attestation.py \
  qa/evidence/<task-id>/summary.json \
  --artifact-root artifacts/qa/<task-id> \
  --private-key-file artifacts/qa/keys/qa-evidence-private-key.pem
```

Validar la firma y el bundle con:

```bash
.venv/bin/python scripts/agent_ops/check_qa_evidence.py qa/evidence/<task-id>/summary.json
```

La CLI siempre exige `qa/trust/qa-evidence-public-key.pem` y una atestación Ed25519
de menos de 24 horas. El modo `attestation_mode="structural"` existe únicamente en
la API Python para tests aislados y para la validación previa del emisor.

La puerta de release selecciona exactamente un `summary.json` modificado por la PR.
Si se ejecuta manualmente con varios candidatos, la selección debe ser explícita:

```bash
.venv/bin/python scripts/agent_ops/check_release_evidence.py \
  qa/evidence/<task-id>/summary.json --head HEAD
```
