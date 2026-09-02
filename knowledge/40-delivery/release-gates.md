# Puertas de entrega

Una tarea funcional no está terminada hasta que se cumpla todo:

1. Tests locales relevantes, lint/typecheck/build, migración limpia y Playwright focal.
2. `render_agents.py --check`, sincronía de skills, enlaces vault e inventarios válidos.
3. Actualización AST, `graphify flows build`, normalización portable, `graphify portable-check` y `graphify check-update` fresco cuando hubo código.
4. Revisión de auth/tenancy/integraciones proporcional al cambio.
5. Ciclo `Production Render QA cycle` exitoso después del merge: SHA live, health, CORS, Redis y perfil sin efectos externos.
6. Matriz funcional visible sobre el hotel de prueba autorizado, con datos sintéticos/reversibles y evidencia operativa posterior al último `code_sha`.

La QA funcional cloud ya no depende de un preview Vercel, un servicio Render QA,
una base Supabase separada ni un artefacto de evidencia previo al merge. El
workflow `.github/workflows/verify-preview-providers.yml` conserva su nombre por
compatibilidad histórica, pero ahora se ejecuta en `push` a `main` o manualmente,
lee únicamente la API de Render, espera el deploy normal y publica un manifiesto
redactado de `provider-verified-production-render`.

`release-gate.yml` y `trusted-release-gate.yml` mantienen las comprobaciones
estáticas y de seguridad del PR, pero no bloquean por falta de un servicio QA o
de una evidencia cloud previa. El resultado funcional queda pendiente hasta que
Render complete el deploy y la matriz humana se registre en
`qa/operational/runs/<run-id>/`.

El verificador falla cerrado si el servicio no es el backend de `main`, el SHA
live no coincide, falta Redis, CORS no es canónico o el perfil seguro no está
activo. No serializa URLs de base de datos, contraseñas, tokens, comprobantes ni
PII. La configuración productiva debe conservar `EXTERNAL_EFFECTS_ENABLED=false`,
`INBOUND_PROVIDER_EVENTS_ENABLED=false`, email nulo, PayPal sandbox e IA/Gemma
deshabilitadas para esta campaña.

La matriz cloud no ejecuta pagos reales, reembolsos reales, emails, webhooks,
OTAs, pruebas de carga destructivas ni pruebas contra hoteles ajenos. Esas
integraciones se validan por contrato, adapters, tests locales o una campaña
operativa expresamente autorizada y separada.

El workflow no despliega, muta secretos, ejecuta migraciones manuales ni cambia
la configuración de Render. Las migraciones del deploy siguen declaradas en
`render.yaml` y cualquier rollback requiere backup, compatibilidad comprobada y
autorización operativa.
