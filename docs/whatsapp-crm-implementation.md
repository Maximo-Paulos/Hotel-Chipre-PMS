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
- `POST /api/whatsapp/conversations/{id}/messages`
- `POST /api/whatsapp/conversations/{id}/notes`
- `POST /api/whatsapp/conversations/{id}/assignment`
- `POST /api/whatsapp/conversations/{id}/status`
- `GET|POST /api/webhooks/meta/whatsapp`

El bot público `/api/public/whatsapp` permanece sin cambios.
