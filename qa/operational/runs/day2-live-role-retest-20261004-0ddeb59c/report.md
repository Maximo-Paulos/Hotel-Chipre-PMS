# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Resumen ejecutivo

Registro parcial de navegación visible en el PMS compartido el 2026-10-04. Se usaron únicamente las sesiones ya abiertas de Dueño, Gerencia y Recepción, según el alcance confirmado por el usuario. La prueba fue de solo lectura.

La aplicación en vivo sigue en `0ddeb59c3e9252c7062856e0560ed56980da16ca`. El PR #115 sigue abierto, con head `a455f9b4d0ace800dcadf8610bd66033378905bf`; por eso este recorrido no comprueba los cambios del PR.

El hallazgo visible más claro fue Caja en la sesión de Dueño: los resúmenes y sesiones permanecieron cargando; la consola registró HTTP 422 en el resumen diario y HTTP 503 en tickets de colaboración. Reportes de Dueño cargó después de esperar y mostró el informe; se registra como PASS tras demora, con una primera espera prolongada. No se registraron cobros, gastos, reservas, mensajes ni cambios de permisos.

## Cobertura observada

| Rol | Área | Resultado visible | Estado |
|---|---|---|---|
| Dueño | Dashboard | Cargó la vista general, próximas reservas y bandeja operativa. | PASS |
| Dueño | Caja | Resumen diario, sesiones y gastos permanecieron en estado de carga; se observaron respuestas 422 y 503 descritas arriba. | FAIL |
| Dueño | Reportes | Tras la espera inicial, cargó el informe del período con sus indicadores. La primera carga demoró más que las páginas operativas. | PASS, con demora inicial |
| Gerencia | Reservas | La ruta abrió en la sesión autenticada. | PASS |
| Gerencia | Habitaciones | La ruta abrió y la pantalla mostró el listado de habitaciones. | PASS |
| Gerencia | Planilla | La ruta abrió y mostró el panel operativo del día. | PASS |
| Gerencia | Tareas | Se cargaron encabezados y tareas sintéticas visibles. | PASS |
| Gerencia | Reportes | Se cargaron secciones operativas (llegadas, no-shows, salidas, bloqueos y riesgos); no se observaron importes financieros. | PASS |
| Gerencia | Caja | La aplicación mostró acceso denegado. La expectativa de permiso para esta ruta debe cotejarse con la matriz de permisos aprobada antes de tratarlo como defecto. | NEEDS-VERIFICATION |
| Recepción | Reservas | La lista abrió. Se observaron acciones de saldo pendiente como texto; no se abrió un formulario de cobro ni se registró un pago. | PASS, lectura solamente |
| Recepción | Planilla | La pantalla operativa abrió. | PASS |
| Recepción | Caja | La aplicación mostró acceso denegado; queda pendiente cotejar la política de permisos aprobada. | NEEDS-VERIFICATION |
| Recepción | Lavandería / Analítica | Se observó acceso denegado en las rutas visitadas. La autorización esperada para estas rutas no se confirmó en esta corrida. | NEEDS-VERIFICATION |

Las solicitudes 403 observadas en Caja y otras consultas auxiliares se registran como señales técnicas; no se atribuye una causa sin correlacionarlas con la política de autorización y los logs del servidor.

## Validación local relacionada

En la validación local relacionada con el PR se ejecutaron:

- Suite completa Playwright: 193 aprobadas, 6 omitidas, 0 fallidas.
- Smoke responsive: 24 aprobadas en Chromium móvil y tres perfiles WebKit.
- Unit tests frontend: 88 aprobadas.
- TypeScript, ESLint y `git diff --check`: aprobados.
- Pruebas backend focalizadas de analítica, auditoría, caja, grupos, bloqueos y lavandería: 66 aprobadas y 2 omitidas porque PostgreSQL no está disponible en este entorno local.

La primera repetición completa había dejado un único timeout en el clic de “Hotel” en Chromium móvil. Se hizo explícito el scroll del panel y se verificó el punto de toque real antes de navegar; la repetición completa posterior terminó sin fallas. Estas validaciones usaron el worktree local basado en `a455f9b4d0ace800dcadf8610bd66033378905bf`; aún no están en `main` y no sustituyen la navegación sobre la aplicación publicada.

En GitHub, el PR #115 sigue abierto en `a455f9b4d0ace800dcadf8610bd66033378905bf`. Sus checks consultados muestran fallidos los dos jobs E2E de Chromium, `operating-system` y `trusted-base-evidence`; las validaciones de backend y frontend están aprobadas. La repetición local verde todavía no aparece en esos checks porque sus ajustes locales no están incorporados a un commit nuevo del PR.

## Límites y estado de evidencia

- Entorno: dominios compartidos con etiqueta de producción; no elegible para el gate de release.
- SHA probado en la nube: `0ddeb59c3e9252c7062856e0560ed56980da16ca`.
- Roles incluidos: Dueño, Gerencia y Recepción. Codueña, Limpieza y master-admin quedan fuera por decisión explícita del usuario.
- La sesión del navegador no permitió guardar capturas redactadas como artefactos locales. `observations.json` queda vacío; por ello esta bitácora no constituye evidencia binaria ni una corrida validada por caso.
- No se accedió a Gmail. No se activaron pagos, cobros, emails, webhooks, OTAs ni modificaciones de datos compartidos.

## Próximos pasos

1. Resolver los checks que mantienen abierto el PR #115; no afirmar que está mergeado hasta que GitHub muestre `MERGED`.
2. Después del despliegue, confirmar que `/build-meta.json` informa el SHA integrado y repetir estas rutas sobre esa versión.
3. Repetir Caja y Reportes de Dueño tras el despliegue, y cotejar los permisos de Caja, Lavandería y Analítica para Gerencia y Recepción con la matriz aprobada.
4. Para probar cobros, gastos, reservas y reconciliaciones de punta a punta, usar fixtures sintéticos en un entorno aislado; esta campaña compartida fue solo de lectura.
