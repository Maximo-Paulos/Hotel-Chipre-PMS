---
name: cloud-user-qa
description: Prueba Render producción como una persona usuaria real sobre el hotel de prueba autorizado.
---

# cloud-user-qa

Usa navegador visible; primero confirma que `Production Render QA cycle` verificó el SHA live y lee el catálogo operativo.

Recorre la matriz funcional con las personas autorizadas usando selectores accesibles. Para cada fila registra la URL canónica, precondición, acción humana, esperado, observado, evidencia y `code_sha` en `qa/operational/runs/<run-id>/`.

No accedas al correo, no pagues, no envíes emails, no dispares webhooks/OTAs y no toques datos de terceros. Un fallo, URL inaccesible o evidencia incompleta bloquea el cierre.
