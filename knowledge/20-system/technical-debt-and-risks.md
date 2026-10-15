# Deuda técnica y riesgos

| Riesgo | Estado | Tratamiento |
| --- | --- | --- |
| Graphify sin descripciones/labels semánticos por política AST-only. | confirmed | La extracción AST y portable-check están actuales; usar código/Graphify mínimo hasta completar etiquetas de forma explícita. |
| Documentación puede citar hosts históricos. | confirmed | Usar manifiesto canónico y marcar historial, nunca configurar desde docs viejas. |
| `api.hotels-pms.com/health` agotó un primer intento de 20 s, aunque un reintento de 60 s devolvió HTTP 200. | needs-verification | Medir/mitigar posible cold start Render y exigir health estable en cada preview antes de QA. |
| Render/Vercel pueden conservar variables privadas con el host histórico. | needs-verification | Comparar `FRONTEND_URL`, CORS y `VITE_PUBLIC_*` contra `hotels-pms.com` en los dashboards sin exponer secretos. |
| `render.yaml` actual usa secretos `sync:false`; previews requieren valores aislados. | confirmed | Aprovisionamiento externo explícito, sin fallback compartido. |
| Registro owner depende de email manual. | confirmed | Bootstrap humano único con buzón dedicado; no automatizar acceso al correo. |
| QA cloud aún no tiene evidencia baseline en este commit. | needs-verification | Crear/validar cuentas y previews aislados antes de activar gate de merge. |
| Cobertura de permiso por las cinco personas requiere recorrido visible. | needs-verification | Ejecutar catálogo completo en cada tarea funcional. |
| La recuperación XLSX cubre una instancia local; no permite escalar entre procesos/hosts. | confirmed | El worker secuencial recupera `PENDING`/`RUNNING` no vencidos al iniciar si la base y `OBJECT_STORAGE_LOCAL_DIR` persisten. Antes de usar varias instancias, agregar almacenamiento compartido y coordinación sólo con evidencia de carga; no sumar Redis/worker/DB blobs por intuición. |

No se elimina una fila por conveniencia: cada riesgo se cierra con evidencia, decisión o aceptación explícita.
