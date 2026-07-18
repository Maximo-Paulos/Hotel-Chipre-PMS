---
name: qa-persona-bootstrap
description: Prepara las cinco identidades QA sintéticas una única vez.
---

# qa-persona-bootstrap

Sigue `knowledge/30-operations/qa-personas-and-bootstrap.md`.

Crea únicamente hotel y usuarios sintéticos aislados; la verificación de correo la hace una persona mediante buzón dedicado. Master-admin usa variables Render separadas `MASTER_ADMIN_EMAIL`, `MASTER_ADMIN_PASSWORD`, `MASTER_ADMIN_PIN`.

Guarda sólo metadatos no sensibles. Nunca escribas contraseñas, cookies, OTPs, tokens ni capturas en Git o vault.
