# 04 · Canales de cobro, tarifas y precios

## Conceptos

- **Canal de cobro:** una forma concreta de cobrar en un hotel, con su proveedor, medio, plazo y tasa. Ejemplos: "Efectivo", "Transferencia al alias", "QR Mercado Pago", "Point · Crédito 10 días", "Payway terminal · Crédito", "Link Mercado Pago 35 días", "PayPal EE. UU. · Factura".
- **Neto objetivo:** lo que el hotel quiere recibir por la estadía (o por noche en la tarifa). Es la base de todos los precios.
- **Precio del canal:** lo que hay que cobrar en ese canal para que quede el neto objetivo.
- **Precio de lista:** el precio más alto entre los canales habilitados.
- **Bonificación:** precio de lista − precio del canal.

## Modelo de datos

### `payment_channels` (nueva)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | — |
| `hotel_id` | FK `hotel_configuration.id` | Índice; toda consulta filtra por hotel |
| `integration_connection_id` | FK nullable | Nulo para efectivo y cobro asistido sin conexión |
| `code` | `String(60)` | Único por hotel, por ejemplo `mp_point_credit_10d` |
| `display_name` | `String(120)` | Lo que ve el recepcionista |
| `method` | `String(30)` | `cash`, `bank_transfer`, `mp_transfer`, `qr`, `payment_link`, `card_terminal`, `paypal` |
| `card_kind` | `String(10)` nullable | `debit`, `credit`, `prepaid`, `any` |
| `provider` | `String(30)` | `none`, `mercado_pago`, `payway`, `getnet`, `nave`, `paypal` |
| `integration_mode` | `String(20)` | `integrated` (el sistema manda el monto y recibe el resultado), `assisted` (el empleado tipea en el posnet y carga el cupón), `manual` (efectivo, transferencia con comprobante) |
| `currency` | `String(3)` | `ARS` o `USD` |
| `ledger_payment_method` | `String(30)` | Valor de `PaymentMethodEnum` con el que se escribe la `Transaction` |
| `accepts_foreign_cards` | Boolean nullable | Informativo; `null` = sin confirmar |
| `is_enabled` | Boolean | — |
| `sort_order` | Integer | Orden en el asistente; poner primero los más baratos |
| `created_at`, `updated_at` | DateTime | — |

`PaymentMethodEnum` es un enum de base de datos: si hace falta un valor nuevo (`qr`, `paypal_usd`), agregarlo con migración. Mantener compatibilidad con reportes que agrupan por `payment_method`.

### `payment_channel_rates` (nueva, historial)

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | — |
| `hotel_id`, `channel_id` | FK | — |
| `percent_rate` | `Numeric(7,4)` | Porcentaje, por ejemplo `4.1900` |
| `fixed_fee` | `Numeric(12,2)` | Fijo por cobro (PayPal: `0.49`) |
| `fixed_fee_currency` | `String(3)` | — |
| `vat_on_fee` | Boolean | `true` para proveedores argentinos; `false` para PayPal hasta confirmar |
| `vat_rate` | `Numeric(5,2)` | Default `21.00` |
| `settlement_label` | `String(60)` | Texto: "10 días", "1 día hábil" |
| `effective_from` | DateTime | — |
| `effective_to` | DateTime nullable | Nulo = vigente |
| `source` | `String(40)` | `suggested:2026-09-27` o `owner` |
| `created_by_user_id` | FK | — |

Nunca se edita una fila vigente: se cierra (`effective_to`) y se inserta otra. Cada cobro guarda el `rate_id` aplicado.

### Configuración del hotel (nuevas columnas en `hotel_configuration`)

| Columna | Tipo | Default |
|---|---|---|
| `payment_pricing_mode` | `String(20)` | `by_method` (`by_method` o `uniform_list`) |
| `price_rounding_step` | `Numeric(12,2)` | `100.00` |
| `usd_pricing_rate_type` | `String(20)` | `oficial` (tipos de `fx_service.RATE_TYPES`) |
| `usd_quote_validity_minutes` | Integer | `1440` |

### Tarifas

- Agregar `target_net_price Numeric(12,2)` a `daily_rates` y `price_periods`: el neto que el dueño quiere recibir por noche.
- Los precios por canal se **calculan al cotizar**, no se guardan por noche.
- Los overrides manuales van a `rate_channel_price_overrides` (`hotel_id`, `daily_rate_id` o `price_period_id`, `channel_id`, `amount Numeric(12,2)`, `created_by_user_id`, `reason`).
- Migrar las columnas actuales `price_cash`, `price_transfer`, `price_mercadopago`, `price_paypal`, `price_credit_card`, `price_debit_card` de `Float` a `Numeric(12,2)` y convertir los valores cargados en overrides del canal equivalente. Mantener las columnas en lectura durante una versión y luego retirarlas.

## Fórmulas

Sea, para un canal `c`: `r` = `percent_rate/100`, `k` = `1 + vat_rate/100` si `vat_on_fee` y `1` si no, `F` = fijo convertido a la moneda del canal, `S` = paso de redondeo.

```
precio_c(neto)  = redondear_arriba( (neto + F) / (1 − r × k), S )
neto_de(monto)  = monto × (1 − r × k) − F
lista(neto)     = max( precio_c(neto) convertido a ARS, para c habilitado )
bonificación_c  = lista − precio_c
```

- Moneda USD: `neto_usd = neto_ars / cotización` (tipo `usd_pricing_rate_type`, venta, snapshot guardado) y el redondeo es al centavo.
- Calcular sobre el **total de la estadía**, no noche por noche, para no acumular redondeos.
- Toda la aritmética con `Decimal`, nunca `float`.
- Reemplazar `calculate_payment_surcharge` y `calculate_base_amount_before_surcharge` (`app/services/payment_service.py:144-213`) por estas funciones en un módulo nuevo `app/services/payment_pricing_service.py`. Los recargos existentes en `payment_surcharges` se migran como override de tasa del canal equivalente.

### Casos de prueba obligatorios (neto $100.000, IVA 21 %, redondeo $1)

| Canal | Tasa | Precio esperado | Neto resultante |
|---|---|---|---|
| Efectivo | 0 | 100.000 | 100.000 |
| QR MP dinero en cuenta | 0,80 % | 100.978 | ≥ 100.000 |
| Payway débito Visa | 1,20 % | 101.474 | ≥ 100.000 |
| Payway crédito | 2,00 % | 102.481 | ≥ 100.000 |
| Payway link crédito | 3,00 % | 103.767 | ≥ 100.000 |
| Point débito 2 días | 2,75 % | 103.443 | ≥ 100.000 |
| Point crédito 10 días | 4,19 % | 105.341 | ≥ 100.000 |
| Link MP al instante | 6,29 % | 108.238 | ≥ 100.000 |
| PayPal EE. UU., extranjero, dólar 1.500, sin IVA | 4,99 % + USD 0,49 | USD 70,69 | ≥ USD 66,67 |

Con redondeo $100: lista con esos canales habilitados (sin PayPal) = $108.300 (link MP al instante).

## Modos de precio

| Modo | Qué cobra cada canal | Qué ve el huésped |
|---|---|---|
| `by_method` | `precio_c` | Precio de lista y "Bonificación por pago con X: −$Y" |
| `uniform_list` | `lista` | Un solo precio |

- Un empleado con el permiso `payment:pricing_override` puede aplicar `uniform_list` a una sesión de cobro puntual con motivo obligatorio (queda en auditoría).
- D1: la validez legal de `by_method` la define el dueño con su contador y abogado. El sistema no decide.

## Obligación de la reserva expresada en neto

Para soportar seña + saldo con canales distintos, la reserva guarda su deuda en **neto objetivo**:

- `reservations.target_net_total Numeric(12,2)`: neto de la estadía, congelado al confirmar la reserva (con snapshot de tarifa).
- Cada pago guarda `net_covered` (el neto que cubre ese cobro según la fórmula `neto_de`).
- `saldo_neto = target_net_total − Σ net_covered`.
- Una sesión de cobro elige cuánto neto cubrir (todo el saldo o una seña de `deposit_percentage`) y calcula su total con los canales elegidos (ver `05`).
- El saldo visible para el recepcionista se muestra por canal: "Saldo: $X en efectivo · $Y en QR · $Z con crédito".

Esto convive con `deposit_amount` y los estados `deposit_paid`/`fully_paid` existentes: `_sync_reservation_financial_status` pasa a usar `saldo_neto`.

## Dólares

- Precio en USD se calcula al crear la sesión de cobro o el link, con la cotización del momento. Guardar `fx_rate_snapshot` (valor, tipo, fuente, hora) en la sesión, el `Payment` y la `Transaction`.
- El monto en USD queda congelado hasta que vence la sesión (`usd_quote_validity_minutes`).
- Fuente: `fx_service` (dolarapi.com). Agregar la API del BCRA como segunda fuente para auditoría. Si ambas fallan, no se ofrece el canal en USD (no se inventa una cotización).
- Contabilidad: la `Transaction` en USD guarda `currency = USD`, `amount` en USD y `fx_rate_snapshot`; el `net_covered` se guarda en ARS para la cuenta del saldo.

## Pantalla de Tarifas (dueño)

1. Selector de modo de precio y paso de redondeo.
2. Carga del **neto objetivo** por noche, por categoría, período o día.
3. Tabla calculada en vivo: canal, tasa vigente, precio, bonificación y neto resultante, marcando qué canal define la lista.
4. Override manual por canal con aviso si deja menos que el neto objetivo.
5. Link a "Canales de cobro" para editar tasas, con los valores sugeridos de `02` y su fecha.

## Criterios de aceptación

1. Los casos de prueba de la tabla anterior pasan con `Decimal`.
2. Cambiar la tasa de un canal no altera cobros ya registrados (cada cobro conserva su `rate_id`).
3. En `uniform_list` todos los canales muestran el mismo total.
4. Una reserva con seña cobrada por QR y saldo cobrado con crédito deja un neto total igual al `target_net_total` (±1 paso de redondeo).
5. Sin cotización disponible, el canal USD no aparece y se muestra el motivo.
