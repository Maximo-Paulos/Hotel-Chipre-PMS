# 06 · Integraciones de cobro: detalle técnico

Patrón común (ya usado por el link de Mercado Pago, mantenerlo):

1. Crear el objeto en el proveedor con `external_reference` firmado (`sign_external_reference` en `payment_link_service.py`) y clave de idempotencia derivada de la parte de la sesión.
2. Guardar `Payment` (`pending`) con `external_payment_id`, `provider`, `payment_link_id` si aplica y referencia a la parte.
3. Recibir webhook → validar firma → registrar `PaymentWebhookEvent` (idempotente por `(hotel_id, provider, webhook_id)`) → **consultar al proveedor** el estado real → transición de estado permitida → `Transaction` idempotente.
4. Respaldo: job que consulta cada minuto los `Payment` en `pending`/`processing` con más de 2 minutos (QR y Point) o cada 15 minutos (links).
5. Nunca confiar en el cuerpo del webhook para montos o estados.

Todos los llamados externos pasan por `require_external_connections(...)` (`app/services/external_effects_policy.py`) para que QA y previews no generen efectos reales.

## Mercado Pago · QR dinámico

- Requiere sucursal y caja en la cuenta del hotel (se crean en el asistente de conexión, `03`).
- Crear orden en Orders API con el monto de la parte, `external_reference` firmado y vencimiento de 10 minutos. Tipo de orden para QR: confirmar en la referencia de Orders API (`needs-verification`).
- La respuesta trae el contenido del QR; el frontend lo dibuja (librería de QR del lado del cliente, sin servicios externos).
- Webhook tópico `order`. Mapeo: `order.processed` → `paid`; `order.expired` → `failed` (motivo vencido); `order.canceled` → `cancelled`; `order.failed` → `failed`; `order.refunded` → refund.
- Canal `ledger_payment_method`: `mercado_pago` (dinero en cuenta) o según la tarjeta usada si la orden lo informa.
- Endpoint nuevo: `POST /api/payment-webhooks/mercadopago/orders` (separado del webhook de links existente, misma validación de firma).

## Mercado Pago · Point (posnet integrado)

- `payment_terminals` (nueva): `hotel_id`, `integration_connection_id`, `provider`, `external_terminal_id`, `name`, `location`, `mode` (`integrated`/`assisted`), `operating_mode` (`PDV`/`STANDALONE`), `store_id`, `pos_id`, `is_active`, `last_seen_at`. Para Payway, Getnet y Nave se usan las mismas filas en modo `assisted` (sin `external_terminal_id` de API; guardar número de comercio y terminal).
- Iniciar parte: `POST /v1/orders` con `type: "point"`, `config.point.terminal_id`, monto con 2 decimales como string, `expiration_time: "PT5M"`, `config.payment_method.default_type` según el canal (`debit_card` o `credit_card`), `default_installments: 1` salvo cuotas, `installments_cost` según configuración, `config.point.print_on_terminal` configurable. Header `X-Idempotency-Key` = hash de `(session_id, part_id, intento)`.
- Cancelar: `POST /v1/orders/{id}/cancel` solo en `created`; si está `at_terminal`, la UI indica "Cancelalo en la terminal".
- Devolver: `POST /v1/orders/{id}/refund` hasta 90 días.
- Al confirmar, leer de la orden: tipo de tarjeta, marca, últimos 4, cuotas, comisión y neto si vienen informados; si no, usar la tasa congelada y completar en la conciliación.
- Si el huésped paga con crédito en un canal de débito (o al revés), registrar la `Transaction` con el medio real y marcar la diferencia de comisión en la conciliación.

## Mercado Pago · Link (existente)

- Mantener `payment_link_service.create_link`. Cambios: crear el link desde una parte de sesión, admitir envío por SMS, y tomar la tasa del canal según el plazo configurado.
- Tarjeta extranjera: probar antes de ofrecer el canal a extranjeros (`needs-verification`).

## Mercado Pago · Transferencia al alias

- Canal `manual` con comprobante (flujo existente `payment_proof_service`).
- Conciliación automática (fase posterior): leer movimientos o el reporte de la cuenta con el token OAuth y confirmar por monto exacto + ventana de tiempo + nombre del ordenante. Endpoint exacto `needs-verification`. Si hay más de una coincidencia, no confirmar automáticamente.

## PayPal (cuenta EE. UU. del dueño)

Reemplazar `app/adapters/paypal_adapter.py` y quitar `paypalrestsdk` de `requirements.txt`. Cliente REST propio (`requests` o `httpx`, como el resto del proyecto).

- Autenticación: `POST /v1/oauth2/token` con client credentials de la app del dueño (`03`). Cachear el token hasta su vencimiento.
- **Opción A, recomendada para links: Orders v2.** `POST /v2/checkout/orders` con `intent: "CAPTURE"`, `purchase_units[0].amount` en USD, `custom_id` = referencia firmada, `invoice_id` = id de la parte (evita duplicados en PayPal). El link a enviar es el `approve` de la respuesta. Al aprobar: captura por webhook `CHECKOUT.ORDER.APPROVED` → `POST /v2/checkout/orders/{id}/capture`; confirmación final con `PAYMENT.CAPTURE.COMPLETED`.
- **Opción B: Invoicing v2** si el dueño prefiere la factura de PayPal por mail (misma tasa). Webhook `INVOICING.INVOICE.PAID`.
- Verificación de webhooks: `POST /v1/notifications/verify-webhook-signature` con el `webhook_id` guardado en la conexión.
- Comisión real: leer `seller_receivable_breakdown` de la captura (`paypal_fee`, `net_amount`) y guardarla.
- Devoluciones: `POST /v2/payments/captures/{id}/refund` con permiso `payment:refund`.
- QR presencial: el frontend puede mostrar como QR el link `approve` de la orden (cobra tasa de Checkout). No usar el QR estático de PayPal.

## Payway · Venta Online (link)

- Credenciales de `03`. Cliente REST con clave privada solo en el backend.
- Crear link de pago (formulario hospedado) con monto en centavos, moneda, `site_transaction_id` = id de la parte y vencimiento. URL `https://live.decidir.com/web/checkout/{payment_id}`.
- Confirmación: webhook si Payway lo ofrece para el comercio (`needs-verification`); si no, consulta periódica del historial de links y del pago.
- Devoluciones total y parcial por API.

## Terminales no integradas (Payway, Getnet, Nave): cobro asistido

- La parte muestra "Tipeá en el posnet: $X" y pide últimos 4, código de autorización, lote y cupón.
- Validaciones: campos con formato; el recepcionista confirma que el monto del ticket coincide (checkbox obligatorio "El ticket dice $X").
- Queda `paid` con `integration_mode = assisted` y `verification_status = pending` hasta la conciliación.

## Conciliación

Tabla `provider_settlement_lines` (nueva): `hotel_id`, `provider`, `external_id`, `operation_date`, `settlement_date`, `gross`, `fee`, `fee_vat`, `taxes_withheld`, `net`, `card_last4`, `authorization_code`, `batch`, `coupon`, `raw` JSON, `matched_payment_id`, `match_status` (`matched`, `unmatched_provider`, `amount_mismatch`).

- Mercado Pago: reporte de liberaciones o de movimientos por API con el token del hotel (endpoint `needs-verification`).
- Payway / Getnet / Nave: importación de archivo de liquidación descargado del portal (CSV o Excel). Un parser por proveedor.
- PayPal: API de búsqueda de transacciones (Transaction Search), requiere que la app del dueño tenga habilitado ese permiso (`needs-verification`).
- Resultado: actualizar `fee_amount`, `fee_vat_amount`, `net_amount` reales en la `Transaction`, marcar asistidos como verificados y abrir una **bandeja de diferencias**: cobros del proveedor sin reserva, montos distintos, asistidos sin liquidación después de N días.
- Job diario; el dueño ve la bandeja en Reportes → Conciliación.

## Envío de links por SMS

- Proveedor de plataforma (D6). Servicio `sms_service.send(hotel_id, phone, text)` con registro de envío y costo.
- Texto corto (menos de 160 caracteres): "Hotel Chipre: pagá tu reserva 1482 ($101.000) acá: <link>". Link acortado propio del PMS para no exceder un segmento.
- Validar formato de teléfono E.164; límite de envíos por reserva para evitar abuso.

## Criterios de aceptación

1. Un webhook duplicado no crea una segunda `Transaction`.
2. Un webhook con firma inválida responde 401 y no cambia estados.
3. Si el webhook no llega, el job de respaldo confirma el pago en menos de 2 minutos (QR y Point).
4. PayPal: una orden aprobada y capturada crea una `Transaction` en USD con comisión y neto leídos de PayPal.
5. Conciliación: un cobro asistido cuyo monto no coincide con la liquidación aparece en la bandeja de diferencias.
6. Con `EXTERNAL_EFFECTS_ENABLED` apagado, ningún camino llama a un proveedor externo (tests existentes de `external_effects_policy` extendidos a los clientes nuevos).
