# Deuda técnica y riesgos

| Riesgo | Estado | Tratamiento |
| --- | --- | --- |
| Graphify sin descripciones/labels semánticos por política AST-only. | confirmed | La extracción AST y portable-check están actuales; usar código/Graphify mínimo hasta completar etiquetas de forma explícita. |
| Documentación puede citar hosts históricos. | confirmed | Usar manifiesto canónico y marcar historial, nunca configurar desde docs viejas. |
| `render.yaml` actual usa secretos `sync:false`; previews requieren valores aislados. | confirmed | Aprovisionamiento externo explícito, sin fallback compartido. |
| Registro owner depende de email manual. | confirmed | Bootstrap humano único con buzón dedicado; no automatizar acceso al correo. |
| QA cloud aún no tiene evidencia baseline en este commit. | needs-verification | Crear/validar cuentas y previews aislados antes de activar gate de merge. |
| Cobertura de permiso por las cinco personas requiere recorrido visible. | needs-verification | Ejecutar catálogo completo en cada tarea funcional. |

No se elimina una fila por conveniencia: cada riesgo se cierra con evidencia, decisión o aceptación explícita.
