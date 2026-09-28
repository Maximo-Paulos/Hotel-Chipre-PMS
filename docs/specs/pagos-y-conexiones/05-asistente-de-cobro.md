# 05 · Asistente de cobro (recepción)

## Principios

1. El recepcionista **no tipea montos**, salvo: el efectivo que le entregan (para el vuelto) y el reparto de un pago dividido.
2. Cada paso tiene una sola acción principal. No se avanza con un paso incompleto.
3. El resultado de un cobro integrado lo decide el proveedor, no el empleado.
4. Todo queda en una **sesión de cobro** auditable.

## Modelo de datos

### `payment_sessions` (nueva)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | — |
| `hotel_id`, `reservation_id` | FK compuesta a `reservations` | Igual que `payments` |
| `purpose` | `String(20)` | `deposit`, `balance`, `full`, `guarantee`, `extra_charge` |
| `net_to_cover` | `Numeric(12,2)` | Neto que cubre esta sesión (ver `04`) |
| `pricing_mode` | `String(20)` | Copia de `payment_pricing_mode` o `uniform_list` si hubo override |
| `pricing_override_reason` | `String(300)` nullable | — |
| `total_amount`, `currency` | `Numeric(12,2)`, `String(3)` | Total a cobrar = precio del canal más caro de los elegidos |
| `fx_rate_snapshot` | JSON nullable | Si algún canal es USD |
| `status` | `String(20)` | `draft`, `in_progress`, `completed`, `cancelled`, `expired` |
| `created_by_user_id`, `completed_at`, `cancelled_at`, `cancel_reason` | — | — |
| `idempotency_key` | `String(100)` | Único por hotel |

### `payment_session_parts` (nueva)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | — |
| `session_id` | FK | — |
| `position` | Integer | Orden de cobro |
| `channel_id`, `rate_id` | FK | Tasa congelada |
| `amount`, `currency` | Numeric, String | — |
| `status` | `String(20)` | `pending`, `awaiting_customer`, `awaiting_provider`, `paid`, `failed`, `cancelled`, `pending_verification` |
| `payment_id` | FK nullable a `payments` | Cobros integrados y links |
| `transaction_id` | FK nullable a `transactions` | Se completa al confirmarse |
| `cash_received`, `change_given` | Numeric nullable | Efectivo |
| `terminal_id` | FK nullable a `payment_terminals` | Point o terminal asistida |
| `assisted_evidence` | JSON nullable | Lote, cupón, autorización, últimos 4, marca |
| `recipient_email`, `recipient_phone` | String nullable | Links |
| `fee_estimated`, `fee_vat_estimated`, `net_estimated` | Numeric | Calculados con la tasa congelada |
| `net_covered` | Numeric | — |

## Flujo

Se abre desde la reserva ("Registrar pago"), desde el check-in y desde el check-out.

### Paso 1 — Qué se cobra

- Muestra huésped, reserva, saldo neto y el total por canal habilitado ("Efectivo $100.000 · QR $101.000 · Crédito $105.400 · PayPal USD 70,69").
- Botones de propósito: "Saldo total", "Seña (X %)" si corresponde, "Garantía" (ver `07`).
- No hay campo de monto libre. Un monto distinto requiere el permiso `payment:custom_amount` y motivo.

### Paso 2 — Medio o pago dividido

- **Un medio:** elige un canal. Total = precio de ese canal.
- **Dividir pago:** elige dos o más canales. Total = **precio del canal más caro entre los elegidos** (regla del dueño, D8). Carga el monto de todas las partes menos la última; el sistema completa la última con el resto. Validaciones: cada parte > 0; suma = total exacto; no más de 4 partes.
- Si después se cambia una parte a un canal más caro que los elegidos, el total se recalcula y se muestra la diferencia antes de seguir. Las partes ya cobradas no cambian.

### Paso 3 — Cobrar cada parte (en orden)

| Canal | Pantalla | Confirmación | Timeout |
|---|---|---|---|
| Efectivo | Monto de la parte. Campo "Recibí". Vuelto calculado. Botón "Confirmar efectivo" | Inmediata. Crea `Transaction` y `CashMovement` en la sesión de caja abierta; sin caja abierta, bloquea y pide abrirla | — |
| Transferencia al alias | Alias/CVU del hotel y monto grande con botón copiar. Adjuntar comprobante | Parte en `pending_verification`. Se confirma por conciliación automática (`06`) o aprobación del dueño (flujo de `payment_proof_service` existente) | La sesión puede cerrarse con la parte pendiente, marcada |
| QR MP | QR dinámico grande y debajo el monto en grande. Estado en vivo | Webhook `order.processed` o consulta periódica. La pantalla pasa sola a "Pagado" | Vence a los 10 minutos; ofrece regenerar |
| Point MP | Elegir terminal (recuerda la última por usuario). "Enviado a Recepción 1". Botón cancelar mientras está `created` | Webhook o consulta. "Aprobado" o "Rechazado" | 5 minutos |
| Terminal asistida (Payway, Getnet, Nave) | "Tipeá en el posnet: $X". Luego campos: últimos 4, código de autorización, lote, cupón | El sistema rechaza si el monto no coincide. Queda `paid` con marca `assisted` y se verifica en la conciliación | — |
| Link (MP, PayPal, Payway) | Email obligatorio (teléfono opcional para SMS). "Enviar" | Webhook o consulta. El recepcionista puede cerrar la pantalla: la parte queda `awaiting_customer` y avisa cuando se paga | Vencimiento del link configurable (default 48 h) |

Actualización en vivo: la pantalla consulta `GET /api/payment-sessions/{id}` cada 2 segundos mientras hay partes en `awaiting_provider`; si el proyecto ya usa canal de tiempo real (`realtime-collaboration.md`), usarlo en lugar de consulta periódica.

### Paso 4 — Resumen

- Todas las partes `paid` → sesión `completed`, pantalla "Pago registrado" con detalle y botón "Continuar con el check-in" o "Imprimir comprobante".
- Partes `awaiting_customer` o `pending_verification` → sesión `in_progress`; la reserva muestra "Pago en curso".
- El check-in exige el propósito configurado (por ejemplo, saldo completo) salvo el permiso `checkin:override_payment` con motivo.

### Cancelación

- Una parte integrada en `awaiting_provider` se cancela en el proveedor (`POST /v1/orders/{id}/cancel`) antes de marcarse `cancelled`. Si el proveedor ya la aprobó, no se puede cancelar: hay que devolver.
- Cancelar una sesión con partes `paid` exige devolverlas (permiso `payment:refund`).

## API

| Método y ruta | Permiso | Descripción |
|---|---|---|
| `GET /api/reservations/{id}/payment-options?purpose=` | `payment:collect` | Canales habilitados con total por canal, lista y bonificaciones |
| `POST /api/payment-sessions` | `payment:collect` | Crea la sesión (`reservation_id`, `purpose`, `channel_ids`, `parts` con montos; header `Idempotency-Key`) |
| `GET /api/payment-sessions/{id}` | `payment:collect` | Estado de sesión y partes |
| `POST /api/payment-sessions/{id}/parts/{part_id}/start` | `payment:collect` | Ejecuta la parte: crea orden QR/Point, envía link o valida efectivo |
| `POST /api/payment-sessions/{id}/parts/{part_id}/cash` | `payment:collect` + `cash:operate` | `cash_received` |
| `POST /api/payment-sessions/{id}/parts/{part_id}/assisted` | `payment:collect` | Evidencia de terminal asistida |
| `POST /api/payment-sessions/{id}/parts/{part_id}/cancel` | `payment:collect` | Cancela en el proveedor si corresponde |
| `PATCH /api/payment-sessions/{id}/parts/{part_id}` | `payment:collect` | Cambia canal de una parte no iniciada; recalcula total |
| `POST /api/payment-sessions/{id}/cancel` | `payment:collect` | — |
| `POST /api/payments/{payment_id}/refund` | `payment:refund` + confirmación reforzada | Total o parcial |

Los servicios viven en `app/services/payment_session_service.py`. Los routers solo validan y delegan (regla del context pack de backend).

## Frontend

- Componente `PaymentWizard` en un modal de pantalla completa en mobile. Estado del servidor con TanStack Query; la fuente de verdad es la sesión del backend (si se recarga la página, se retoma).
- Números en fuente tabular; el monto a pagar siempre es el elemento más grande de la pantalla.
- Estados visibles con color y texto: esperando, pagado, rechazado, vencido.
- Accesible por teclado; confirmaciones dentro del modal (no `confirm()`).

## Criterios de aceptación

1. En un pago en efectivo, el único dato que tipea el empleado es lo recibido.
2. En un pago dividido QR + efectivo, el total es el precio de QR y la suma de partes siempre coincide; no se puede confirmar si no coincide.
3. Un QR pagado pasa a "Pagado" sin intervención en menos de 5 segundos desde el webhook (o 10 segundos por consulta si el webhook no llega).
4. Recargar el navegador en medio de un cobro retoma la misma sesión y no crea una segunda orden en el proveedor (idempotencia).
5. Un recepcionista sin `payment:custom_amount` no puede cambiar montos por API (403).
6. Cada parte pagada genera exactamente una `Transaction` con `gross_amount`, `fee_amount`, `fee_vat_amount` (columna nueva; no reutilizar `tax_amount`, que es impuesto de la venta), `net_amount`, `provider_code` y referencia a la parte.
