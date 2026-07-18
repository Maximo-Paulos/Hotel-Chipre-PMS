---
scope: auth, roles, tenancy, secretos, pagos, webhooks y PII
owner: security-auditor
last_verified_commit: bc938cf
canonical_sources: [app/config.py, app/api/auth.py, app/master_admin/, app/services/security.py]
graphify_minimum: graphify affected-flows --files app/api/auth.py
required_validation: security tests + review de autorización + logs redactados
---
# Context pack — Seguridad

Autenticación de usuario usa JWT y hashes de contraseña; master-admin es un límite distinto con email, password, PIN, sesión y lockout. Producción rechaza secretos débiles mediante validación runtime, pero toda modificación debe verificar tanto configuración como tests.

Nunca incluir secretos/sesiones/PII en notas o evidencia. Webhooks deben verificarse; pagos, correos y OTAs no se ejecutan en QA cloud sin autorización explícita.
