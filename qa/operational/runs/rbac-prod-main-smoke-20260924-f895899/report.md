# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

Run `rbac-prod-main-smoke-20260924-f895899` — 2026-09-24. Entorno productivo compartido, no certificante. SHA observado en Vercel Production y Render live: `f89589973c3c795d449220ab5ea26511f0629e85`.

## Resultado

- **PASS, alcance limitado:** `/health` respondió 200; el SHA del cuerpo coincide con producción. Sin credenciales, `GET /api/auth/me` y `GET /api/reservations/` respondieron 401; los cuerpos se descartaron.
- **PASS, alcance limitado:** la página pública de registro de dueño cargó; el formulario no se envió. A 390x844, 768x1024 y 1440x900 no hubo overflow horizontal.
- **BLOCKED:** no se recorrió el login ni la matriz RBAC autenticada. No existe `.env.qa.local` ni se detectaron identidades QA dedicadas en Render. No se usó la identidad personal de Google del navegador.

## Límites y estado observado

- La configuración de producción tiene `APP_ENV=production`, `EMAIL_PROVIDER=resend` y `CONNECTIONS_ENABLED=true`; el formulario no se envió para evitar crear cuentas o disparar correo.
- La metadata de Supabase mostró registros preexistentes en tablas operativas; no se leyeron filas de usuarios/reservas ni se escribió o borró ningún dato. No se asumió que esos registros fueran sintéticos.
- La cabeza Alembic leída en Supabase fue `20260918_member_alias_auth`; la cabeza local es `20260924_action_stepup_single_use`. El SHA local con RBAC nuevo no está desplegado.
- El servicio Render no tiene pre-deploy configurado y su start command no ejecuta `alembic upgrade head`. No se intentó migrar la base.

**Veredicto: BLOCKED / PARTIAL.** Esto no prueba el RBAC nuevo, no satisface la matriz formal de personas y no es evidencia de release. No se enviaron emails, pagos, webhooks, sincronizaciones OTA ni se hicieron cambios de datos.
