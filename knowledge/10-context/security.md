---
scope: auth, roles, tenancy, secretos, pagos, webhooks y PII
owner: security-auditor
last_verified_commit: 1b6ca045
working_tree_review: local RBAC diff, not deployed
canonical_sources: [app/config.py, app/api/auth.py, app/dependencies/auth.py, app/services/permission_service.py, app/master_admin/, app/services/security.py]
graphify_minimum: graphify affected-flows --files app/api/auth.py
required_validation: security suite + independent authorization review + authenticated allow/deny before release
---
# Context pack — Seguridad

Autenticación de usuario usa JWT y hashes de contraseña; master-admin es un límite distinto con email, password, PIN, sesión y lockout. Producción rechaza secretos débiles mediante validación runtime, pero toda modificación debe verificar tanto configuración como tests.

Nunca incluir secretos/sesiones/PII en notas o evidencia. Webhooks deben verificarse; pagos, correos y OTAs no se ejecutan en QA cloud sin autorización explícita.
