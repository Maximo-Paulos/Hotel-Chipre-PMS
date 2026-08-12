---
name: cloud-user-qa
description: Prueba un preview cloud como una persona usuaria real.
---

# cloud-user-qa

Usa navegador visible y `.env.qa.local` ignorado; primero identifica si el destino
es un preview aislado o el sandbox compartido y lee su catálogo correspondiente.

En un preview aislado, recorre la matriz formal completa con owner, co-owner,
manager, recepción, housekeeping y master-admin usando selectores accesibles. Para
cada fila registra persona, dispositivo, URL preview, precondición, acción humana,
esperado, observado, evidencia y `code_sha` en `qa/evidence/<task-id>/`.

En el sandbox compartido, usa `qa/operational/shared-sandbox-catalog.json` y escribe
exclusivamente en `qa/operational/runs/<run-id>/` y
`artifacts/qa-operational/<run-id>/`. El reporte debe comenzar con
`QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE`; nunca lo
ofrezcas al release gate formal.

No accedas al correo, no pagues, no envíes emails, no dispares webhooks/OTAs y no toques datos de terceros. Un fallo, URL inaccesible o evidencia incompleta bloquea el cierre.
