# 03 · Hub de conexiones self-service

## Objetivo

El dueño (o co-dueño) conecta, prueba, reconecta y desconecta cada proveedor desde **Configuración → Conexiones**, sin soporte y sin tocar código, con la misma experiencia que "Conectar con Google". El recepcionista nunca ve credenciales.

Se construye sobre lo que existe: `integration_catalog`, `integration_connections`, cifrado Fernet y `SettingsConnectionsPage.tsx`. No crear un sistema paralelo.

## Modelo de datos

Reutilizar `IntegrationCatalog` e `IntegrationConnection` (`app/models/integration.py`). Agregar (migración con el skill `new-migration`):

**`integration_catalog`** (nuevas columnas)

| Columna | Tipo | Uso |
|---|---|---|
| `category` | `String(30)` | `payments`, `messaging`, `email`, `ota`, `platform` |
| `connect_modes` | `JSON` | Lista ordenada de modos soportados: `oauth`, `manual_credentials`, `embedded_signup`, `assisted` |
| `capabilities` | `JSON` | Lo que habilita, por ejemplo `["payment_link","qr","point","refund","reserve_capture"]` |
| `setup_guide_slug` | `String(80)` | Guía paso a paso que muestra la UI (`docs/conexiones/<proveedor>/README.md`) |

**`integration_connections`** (nuevas columnas)

| Columna | Tipo | Uso |
|---|---|---|
| `connect_mode` | `String(30)` | Modo usado en esta conexión |
| `account_label` | `String(200)` | Ya se calcula con `connection_account_label`; persistirlo |
| `external_account_id` | `String(120)` | `user_id` de MP, `merchant_id` de PayPal, `site_id` de Payway, `waba_id` |
| `scopes_granted` | `JSON` | Scopes efectivos devueltos por el proveedor |
| `token_expires_at` | `DateTime` | Para refresh proactivo |
| `refresh_expires_at` | `DateTime` | MP: refresh token de 6 meses |
| `last_health_check_at`, `last_health_status`, `last_error_code` | — | Estado visible en la tarjeta |
| `webhook_status` | `String(20)` | `not_required`, `pending`, `active`, `failing` |

Restricción: una conexión activa por `(hotel_id, provider)`. Las credenciales siguen en el payload cifrado; nunca en columnas planas ni en logs (`redact_integration_error` ya existe).

**`payment_terminals`** (nueva; ver `06`) y **`payment_channels`** (nueva; ver `04`) cuelgan de la conexión del proveedor.

## Estados de una conexión

`not_connected → authorizing → connected → (degraded | expired | revoked | error) → connected`

- `degraded`: funciona pero falla algo accesorio (por ejemplo, webhook sin eventos en 48 h o terminal desconectada).
- `expired`: token vencido sin refresh posible; la UI pide "Reconectar".
- Toda transición se registra con `record_event` (ya existe).

## API (sobre `/api/integrations`, existente)

| Método y ruta | Estado | Cambio |
|---|---|---|
| `GET /api/integrations` | Existe | Devolver `category`, `connect_modes`, `capabilities`, estado de salud y `webhook_status` |
| `POST /api/integrations/{id}/connect` | Existe | Aceptar `mode` explícito. `oauth` devuelve `redirect_url`; `manual_credentials` valida contra el proveedor antes de guardar |
| `GET /api/integrations/oauth/{provider}/callback` | Existe | Agregar PKCE para MP y persistir `token_expires_at`/`refresh_expires_at` |
| `POST /api/integrations/{id}/refresh` | Existe (solo Gmail) | Agregar Mercado Pago (`grant_type=refresh_token`) |
| `POST /api/integrations/{id}/test` | Nuevo | Prueba de salud sin efectos: MP `GET /users/me`; PayPal token client credentials; Payway consulta de historial de links; Gmail perfil |
| `POST /api/integrations/{id}/revoke` | Existe | Además desactivar canales y terminales dependientes |
| `GET /api/integrations/{id}/resources` | Nuevo | Recursos del proveedor para configurar: sucursales, cajas y terminales de MP; números de WhatsApp |

Todos requieren el permiso nuevo `integration:manage` (solo dueño y co-dueño) salvo `GET`, que requiere `integration:view`. Los códigos siguen el formato existente `dominio:acción` (ver `payment:proof:review`, `cash:operate`) y se agregan con el skill `new-permission`. Un job diario (`app/adapters/job_dispatcher.py`) refresca tokens que vencen en menos de 7 días y corre `test` en todas las conexiones activas.

## Por proveedor

### Mercado Pago — modo `oauth` (principal) y `manual_credentials` (respaldo)

Prerequisito de plataforma (D3): crear una aplicación de integrador de PMS Paulus en Mercado Pago, configurar `MERCADOPAGO_CLIENT_ID`, `MERCADOPAGO_CLIENT_SECRET`, `MERCADOPAGO_REDIRECT_URI` y la URL de notificaciones de la app.

Flujo del dueño:
1. Toca "Conectar con Mercado Pago" y autoriza en `auth.mercadopago.com` (ya implementado en `build_redirect_url`; agregar `code_challenge` PKCE).
2. El callback canjea el código (válido 10 minutos, un solo uso) y guarda `access_token`, `refresh_token`, `user_id`, `expires_in`.
3. El PMS llama a `GET /users/me` y muestra el nombre de la cuenta.
4. **Asistente Point y QR:** el PMS lista sucursales y cajas de la cuenta; si no hay, ofrece crearlas ("Hotel Chipre – Recepción"). Lista terminales, el dueño elige cuáles usar y las nombra; el PMS las pasa a modo `PDV` con `PATCH /terminals/v1/setup`, respetando una terminal PDV por caja.
5. El dueño elige los plazos de acreditación que tiene configurados en su cuenta y el PMS precarga las tasas sugeridas de `02` para crear sus canales (`04`).

Webhooks: con OAuth, las notificaciones se configuran en la app de la plataforma y llegan con el `user_id` del vendedor. Rutear por `user_id` → `external_account_id` → `hotel_id`. Mantener la validación de firma existente.

El modo manual actual (el dueño crea su propia app y pega el token) queda como respaldo.

### Payway Venta Online — modo `manual_credentials` + `assisted`

1. La tarjeta muestra la guía: pedir a `soporte@payway.com.ar` las claves de Venta Online.
2. El dueño pega `site_id`, clave pública y clave privada. El PMS valida con una consulta de solo lectura (historial de links).
3. Para terminales Payway, Getnet o Nave: el dueño da de alta cada terminal como **no integrada** (nombre, proveedor, número de comercio y de terminal). Esto habilita el "cobro asistido" (`06`).

### PayPal (cuenta EE. UU. del dueño) — modo `manual_credentials`

1. Guía: crear en developer.paypal.com una app REST "Live" en la cuenta del dueño, con los permisos de aceptar pagos y facturación, sin pagos salientes (Payouts).
2. El dueño pega Client ID y Secret. El PMS obtiene un token con client credentials para validar y guarda el `merchant_id`.
3. El PMS registra por API su webhook en esa app (`PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `INVOICING.INVOICE.PAID`, `CHECKOUT.ORDER.APPROVED`) y guarda el `webhook_id` para verificar firmas.
4. Reemplazar el OAuth actual de "Log in with PayPal" (solo identidad). Evaluar a futuro el programa de partners de PayPal para un botón "Conectar con PayPal" (`needs-verification`).

### Gmail — modo `oauth` (existente)

Funciona. Pendiente: verificación de la app de Google (scope `gmail.send` sensible, D5) y mostrar el estado de salud.

### WhatsApp — modo `embedded_signup` (fase posterior)

Prerequisito (D4): la plataforma debe ser Tech Provider de Meta, con verificación de negocio, App Review de `whatsapp_business_management` y `whatsapp_business_messaging`. Sin verificación, el alta queda limitada a 10 clientes cada 7 días (200 con verificación).

Flujo: el front abre Embedded Signup con el SDK de Meta; recibe `waba_id`, `phone_number_id` y un código; el backend canjea el código por un token del negocio del cliente (server-to-server), registra el número en Cloud API y suscribe webhooks del WABA. Luego llama al existente `complete_embedded_signup`. El cliente paga sus mensajes a Meta con su propio medio de pago (modelo Tech Provider).

### SMS — conexión de plataforma

El proveedor de SMS (D6) es de la plataforma, no del hotel. Credenciales en configuración de entorno o en master admin. Se muestra al hotel solo como "SMS disponible" y el consumo por hotel.

### Stripe — conexión de plataforma

Solo en master admin (ver `08`). Quitar Stripe de la configuración de medios de pago del hotel.

## Pantalla "Conexiones"

- Tarjetas agrupadas por categoría: Cobros, Mensajería, Correo, Canales de venta.
- Cada tarjeta muestra: estado con color y texto, cuenta conectada, qué habilita, último chequeo, botones "Conectar", "Probar", "Reconectar" y "Desconectar", y la guía paso a paso en línea.
- Mensajes de error accionables ("El token venció. Tocá Reconectar.") en lugar de códigos del proveedor.

## Criterios de aceptación

1. Un dueño sin ayuda conecta Mercado Pago por OAuth, ve el nombre de su cuenta y ve sus terminales Point listadas en menos de 3 minutos.
2. Un recepcionista no puede ver ni llamar a ningún endpoint de conexiones (403).
3. Un token de MP con vencimiento en 3 días se refresca solo en el job diario; si el refresh falla, la conexión pasa a `expired` y la tarjeta pide "Reconectar".
4. Desconectar Mercado Pago desactiva sus canales y terminales; el asistente de cobro deja de ofrecerlos.
5. Ningún secreto aparece en respuestas de API, logs ni eventos de auditoría (test que busca patrones de token en logs capturados).
