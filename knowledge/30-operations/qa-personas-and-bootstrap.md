# Personas QA y bootstrap

Variables permitidas únicamente en `.env.qa.local` (ignorado): URLs preview y email/contraseña de `owner`, `manager`, `reception`, `housekeeping`, `master-admin`; no cookies, tokens, OTPs, capturas ni secretos de terceros. Usar `.env.qa.example` como nombres de variables.

`DATABASE_URL`, claves Ed25519, secretos runtime, variables de lease y la capacidad
efímera de bootstrap no pertenecen a `.env.qa.local`: viven sólo en GitHub
Environment/Render o en `artifacts/qa/keys/` ignorado. El fingerprint combinado
liga las cinco identidades y `QA_RUN_ID` al manifiesto provider-verificado sin
versionar sus valores.

Bootstrap único y manual:

1. Crear owner y hotel sintético identificado por `QA_RUN_ID`.
2. Una persona verifica el email usando un buzón QA dedicado; el agente no accede al correo.
3. Owner invita/crea manager, recepción y housekeeping y la persona verifica lo requerido.
4. Configurar una identidad master-admin distinta en Render mediante `MASTER_ADMIN_EMAIL`, `MASTER_ADMIN_PASSWORD`, `MASTER_ADMIN_PIN`.
5. Anotar sólo fecha, entorno, roles disponibles y run id en la evidencia/vault.

No tocar hoteles ni usuarios de terceros. Limpiar por UI sólo datos reversibles; conservar registros auditables irreversibles y etiquetarlos como sintéticos.
