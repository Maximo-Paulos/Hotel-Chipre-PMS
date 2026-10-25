# WhatsApp CRM W0/W1

La primera entrega de WhatsApp separa el CRM humano del bot público legado y de los dominios de pagos e IA.

## Alcance entregado

- `whatsapp_channels`, `whatsapp_contacts`, `whatsapp_conversations`, `whatsapp_messages`, notas y eventos son tenant-scoped; usan claves compuestas hotel+entidad y políticas RLS en PostgreSQL.
- `whatsapp_provider_routes` contiene únicamente IDs de Meta para resolver el hotel antes de establecer `app.hotel_id`; no contiene PII y no se fuerza RLS en esa tabla de routing.
- Pro y Ultra habilitan el feature `whatsapp.crm`; Starter recibe `403`.
- La bandeja autenticada permite listar conversaciones, enviar mensajes manuales en cola, asignar responsables, guardar notas y cambiar estado. Cada acción deja un evento auditable.
- Los mensajes entrantes son idempotentes por `provider_message_id`; las notificaciones solo transportan identificadores permitidos por la política de payload seguro.
- El webhook verifica token de suscripción y firma HMAC. El procesamiento queda deshabilitado salvo `INBOUND_PROVIDER_EVENTS_ENABLED=true` y secreto configurado.

## Configuración y límites

`META_WHATSAPP_APP_ID`, `META_WHATSAPP_APP_SECRET` y `META_WHATSAPP_VERIFY_TOKEN` son configuración de servidor. No se aceptan access tokens en el frontend ni en el endpoint de finalización; `POST /api/whatsapp/channel/complete` recibe solamente metadata devuelta por el adaptador server-side de Embedded Signup.

No se realizan llamadas a Meta, envíos reales, cobros ni cambios de cuentas en esta entrega. El worker de salida y la prueba controlada de mensaje quedan como siguiente integración, usando sandbox.

Rutas principales:

- `GET /api/whatsapp/channel`
- `POST /api/whatsapp/channel/complete`
- `GET /api/whatsapp/conversations`
- `GET /api/whatsapp/conversations/{id}/messages`
- `POST /api/whatsapp/conversations/{id}/messages`
- `POST /api/whatsapp/conversations/{id}/notes`
- `POST /api/whatsapp/conversations/{id}/assignment`
- `POST /api/whatsapp/conversations/{id}/status`
- `GET|POST /api/webhooks/meta/whatsapp`

## Historial y alcance de acceso

La lista de conversaciones devuelve datos resumidos y no incluye mensajes. El historial se consulta por páginas con `GET /api/whatsapp/conversations/{id}/messages`: la primera solicitud trae los 50 mensajes más recientes, en orden cronológico; las siguientes envían `before_message_id` con el cursor de la página anterior. El límite máximo es 100 mensajes por solicitud.

La bandeja requiere `whatsapp:inbox:view`. `whatsapp:inbox:all` permite ver todas las conversaciones del hotel; cada acción además exige su permiso específico. Sin ese permiso, el PMS fuerza el alcance a las conversaciones asignadas a la persona autenticada en la lista, el historial, el envío, las notas, la asignación y el cambio de estado. Las conversaciones fuera de ese alcance responden como no encontradas.

La migración agrega el índice `(hotel_id, conversation_id, id)` con creación concurrente en PostgreSQL para permitir escrituras mientras se construye.

El bot público `/api/public/whatsapp` permanece sin cambios.
