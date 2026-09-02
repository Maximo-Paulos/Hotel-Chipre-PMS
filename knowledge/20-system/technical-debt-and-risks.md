# Deuda técnica y riesgos

| Riesgo | Estado | Tratamiento |
| --- | --- | --- |
| Graphify sin descripciones/labels semánticos por política AST-only. | confirmed | La extracción AST y portable-check están actuales; usar código/Graphify mínimo hasta completar etiquetas de forma explícita. |
| Documentación puede citar hosts históricos. | confirmed | Usar manifiesto canónico y marcar historial, nunca configurar desde docs viejas. |
| `api.hotels-pms.com/health` agotó un primer intento de 20 s, aunque un reintento de 60 s devolvió HTTP 200. | needs-verification | Medir/mitigar posible cold start Render y exigir health estable en cada deploy antes de QA. |
| Render/Vercel pueden conservar variables privadas con el host histórico. | needs-verification | Comparar `FRONTEND_URL`, CORS y `VITE_PUBLIC_*` contra `hotels-pms.com` en los dashboards sin exponer secretos. |
| `render.yaml` actual usa secretos `sync:false`; la QA funcional usa el hotel de prueba autorizado en Render producción. | confirmed | El workflow verifica hosts canónicos y el perfil seguro sin exigir un entorno QA separado. |
| Registro owner depende de email manual. | confirmed | Bootstrap humano único con buzón dedicado; no automatizar acceso al correo. |
| QA cloud aún no tiene matriz humana para el SHA vigente. | needs-verification | Ejecutar/registrar el catálogo funcional sobre el hotel de prueba de Render producción después del deploy. |
| Cobertura de permiso por las cinco personas requiere recorrido visible. | needs-verification | Ejecutar catálogo completo en cada tarea funcional. |

No se elimina una fila por conveniencia: cada riesgo se cierra con evidencia, decisión o aceptación explícita.
