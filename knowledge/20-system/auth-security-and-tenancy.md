# Auth, seguridad y tenancy

Estado: `confirmed` para configuración y rutas revisadas; `needs-verification` para cobertura de autorización exhaustiva.

El login de hotel usa contraseña hasheada y JWT; registro, verificación de email y reset son rutas públicas controladas. Master-admin usa credenciales separadas (`MASTER_ADMIN_EMAIL`, `MASTER_ADMIN_PASSWORD`, `MASTER_ADMIN_PIN`), sesión/cookie, límite de intentos y lockout. `validate_runtime_security()` rechaza secretos JWT débiles y PIN de producción inválido.

Se exige autorización explícita y alcance de hotel en toda operación sensible. Nunca se loguean secretos, tokens, datos de tarjeta o PII innecesaria. En Render producción, CORS debe contener exactamente los hosts canónicos de marketing y aplicación, sin comodines.
