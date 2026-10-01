---
name: cloud-user-qa
description: Prueba un preview cloud como una persona usuaria real.
---

# cloud-user-qa

Usa navegador visible y `.env.qa.local` ignorado; primero lee el catálogo y manifest de QA.

Recorre la matriz completa con owner, manager, recepción, housekeeping y master-admin usando selectores accesibles. Para cada fila registra URL de preview, precondición, acción humana, esperado, observado, evidencia y `code_sha` en `qa/evidence/<task-id>/`.

No accedas al correo, no pagues, no envíes emails, no dispares webhooks/OTAs y no toques datos de terceros. Un fallo, URL inaccesible o evidencia incompleta bloquea el cierre.
