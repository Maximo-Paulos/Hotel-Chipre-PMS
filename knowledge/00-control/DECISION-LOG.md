# Registro de decisiones

| Fecha | Decisión | Estado | Evidencia / motivo | Revisión |
| --- | --- | --- | --- | --- |
| 2026-09-01 | La QA funcional cloud se ejecuta sobre Render producción, en el hotel de prueba autorizado, después del deploy de `main`; no se exige un servicio Render QA separado. | confirmed | Decisión explícita del owner; el workflow verifica SHA live, health, Redis y perfil sin efectos externos antes de la matriz humana. | Si se habilita una campaña de carga, pagos reales o un nuevo hotel. |
| 2026-07-18 | El vault operativo vive en `knowledge/` dentro del repositorio. | confirmed | Alcance aprobado; evita vault Windows divergente. | Cuando cambie la estrategia documental. |
| 2026-07-18 | Graphify queda separado del vault; sólo se enlazan resúmenes e inventarios. | confirmed | Grafo de miles de nodos no es memoria curada. | Tras cambios de Graphify. |
| 2026-07-18 | QA cloud exige preview aislado Vercel + Render + Supabase Branch. | historical | Política anterior; fue reemplazada el 2026-09-01 por la QA funcional en Render producción sobre el hotel de prueba autorizado. | Si el owner vuelve a solicitar una campaña aislada. |
| 2026-07-18 | No hay pago, correo, webhook u OTA real durante regresión QA. | confirmed | Política externa de seguridad. | Si cambia autorización expresa. |
| 2026-07-18 | El dominio operativo canónico es `hotels-pms.com` y no el histórico `hoteles-pms.com`. | confirmed | Login y marketing canónicos respondieron HTTP 200; los hosts históricos no resolvieron. | Confirmar que las variables privadas de Render/Vercel coincidan. |
| 2026-07-19 | Mientras el plan gratuito no permita Supabase Branches persistentes, se usa un segundo proyecto QA sin datos productivos y un lease exclusivo serializado. | historical | Política anterior de preview; la campaña vigente usa el hotel de prueba de Render producción. | Si el owner vuelve a solicitar una campaña aislada. |
| 2026-07-19 | Verificación, bootstrap, re-verificación y cleanup de QA ocurren en un único workflow confiable. | historical | Flujo anterior de preview; el workflow vigente sólo verifica Render producción de forma read-only. | Si cambia la superficie cloud. |
| 2026-07-19 | QA cloud inicia con integraciones externas fail-closed y sin workers/cron. | confirmed | Correo, pagos, OTA e IA no deben producir efectos durante la campaña productiva de prueba. | Ampliar el guard si aparece un proveedor nuevo. |
| 2026-07-19 | Evidencia humana y bootstrap usan dos pares Ed25519 distintos. | historical | Contrato anterior de bootstrap/preview; la campaña vigente publica evidencia operativa redactada. | Si se reactiva un bootstrap firmado. |
| 2026-07-23 | La memoria persistente de agentes vive en `/Users/maximopaulos/AI-Workspace/memory`, con Git local sin remoto, y `knowledge/` conserva memoria específica del proyecto. | confirmed | Plan aprobado y contrato Markdown implementado localmente. | Revisar al registrar otro proyecto o agente. |
