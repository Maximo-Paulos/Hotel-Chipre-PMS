# Registro de decisiones

| Fecha | Decisión | Estado | Evidencia / motivo | Revisión |
| --- | --- | --- | --- | --- |
| 2026-07-18 | El vault operativo vive en `knowledge/` dentro del repositorio. | confirmed | Alcance aprobado; evita vault Windows divergente. | Cuando cambie la estrategia documental. |
| 2026-07-18 | Graphify queda separado del vault; sólo se enlazan resúmenes e inventarios. | confirmed | Grafo de miles de nodos no es memoria curada. | Tras cambios de Graphify. |
| 2026-07-18 | QA cloud exige preview aislado Vercel + Render + Supabase Branch. | confirmed | Evita datos y versiones compartidos. | Al aprovisionar proveedores. |
| 2026-07-18 | No hay pago, correo, webhook u OTA real durante regresión QA. | confirmed | Política externa de seguridad. | Si cambia autorización expresa. |
| 2026-07-18 | El dominio operativo canónico es `hotels-pms.com` y no el histórico `hoteles-pms.com`. | confirmed | Login y marketing canónicos respondieron HTTP 200; los hosts históricos no resolvieron. | Confirmar que las variables privadas de Render/Vercel coincidan. |
| 2026-07-19 | Mientras el plan gratuito no permita Supabase Branches persistentes, se usa un segundo proyecto QA sin datos productivos y un lease exclusivo serializado. | confirmed | La sesión Supabase mostró el upgrade requerido; compartir la base principal queda prohibido. | Migrar a branch-per-PR cuando el plan lo permita. |
| 2026-07-19 | Verificación, bootstrap, re-verificación y cleanup de QA ocurren en un único workflow confiable. | confirmed | Elimina artefactos bearer y la ventana TOCTOU entre workflows. | Revisar tras el primer run real. |
| 2026-07-19 | Preview QA inicia con integraciones externas fail-closed y sin workers/cron. | confirmed | Correo, pagos, OTA e IA podían usar configuración live fuera de producción. | Ampliar el guard si aparece un proveedor nuevo. |
| 2026-07-19 | Evidencia humana y bootstrap usan dos pares Ed25519 distintos. | confirmed | Separa la firma local de artefactos de la capacidad máquina de Render. | Rotar si se compromete una clave. |
