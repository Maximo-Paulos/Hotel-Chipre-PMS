# 02 · Proveedores de cobro

Relevamiento sobre documentación oficial al 27–28/09/2026. Las tasas cambian: el sistema **no** debe tener tasas fijas en código. Estos valores sirven como **valores sugeridos** que el dueño puede aceptar o editar al configurar un canal (ver `04`). Guardar la fecha de relevamiento junto a cada valor sugerido.

Todas las tasas son **sin IVA** salvo que se indique. El IVA (21 %) se aplica sobre la comisión.

## Resumen: tarjeta extranjera

| Proveedor / canal | Acepta tarjeta emitida en el exterior | Moneda que recibe el hotel | Recargo por extranjera | Certeza |
|---|---|---|---|---|
| Payway terminal | Sí (Visa, Mastercard, Cabal, Discover, Diners, UnionPay, Amex) | ARS; al huésped se le aplica "dólar turista" | No; misma tasa "Nacional e Internacional". Crédito extranjero se acredita a 18 días hábiles | confirmed |
| Payway Venta Online / link | Sí | ARS (la API también admite `currency` USD en links) | No; misma tasa | confirmed (moneda USD en link: needs-verification para tarjetas extranjeras) |
| Payway terminal Classic, conversión dinámica | Solo Visa extranjera | ARS; el comercio cobra una comisión por la conversión | — | confirmed |
| Payway bimonetarismo (USD) | **No**: solo débito argentino en USD | USD | — | confirmed |
| Getnet terminal | Sí (Visa y Mastercard internacionales) | ARS | **+0,7 %** | confirmed |
| Mercado Pago Point | No documentado | ARS | — | needs-verification (prueba real con tarjeta extranjera) |
| Mercado Pago link (Checkout Pro) | No documentado en la documentación oficial | ARS | — | needs-verification |
| Mercado Pago QR | En la práctica no: requiere app de billetera o banco argentino | ARS | — | inferred |
| Nave | No documentado | ARS | — | needs-verification |
| Fiserv Clover | Probable | ARS | Negociado | needs-verification |
| PayPal (cuenta EE. UU. del dueño) | Sí, tarjeta o saldo PayPal | USD | +1,50 % internacional | confirmed |
| Stripe | Sí | USD | +1,5 % | confirmed; **no disponible para empresas argentinas** |

Conclusión técnica: ningún adquirente argentino acredita USD por tarjetas extranjeras. Para recibir USD, la única opción viable hoy para el hotel es PayPal EE. UU. del dueño.

## Mercado Pago

**Conexión:** OAuth de integradores (authorization code de un solo uso, válido 10 minutos; refresh token válido 6 meses; soporta PKCE). Con el token del vendedor se operan links, QR, Point, pagos y suscripciones de su cuenta. `confirmed`.

### Point Smart (posnet integrado)

| Medio | Al instante | Plazo alternativo |
|---|---|---|
| Débito | 2,99 % | 2,75 % (2 días) |
| Crédito | 5,99 % | 5,19 % (5 días) · 4,19 % (10 días) |
| Prepaga | 3,75 % | 3,50 % (3 días) |

- Equipo: $44.999 (precio de lista con descuento, 27/09/2026), sin abono. `confirmed`
- IVA sobre la comisión: `inferred` (la página de Point dice que los costos varían por impuestos provinciales; las páginas de QR y link dicen explícitamente "+IVA").
- API: Orders API `POST /v1/orders` con `type: "point"`, `config.point.terminal_id`, `transactions.payments[0].amount` como string con 2 decimales, `external_reference` (máx. 64, alfanumérico, `-` y `_`), header `X-Idempotency-Key`. `expiration_time` entre `PT30S` y `PT3H` (15 minutos por defecto). `config.payment_method.default_type`, `default_installments`, `installments_cost` (`seller`/`buyer`), `config.point.print_on_terminal`. `confirmed`
- Cancelar: `POST /v1/orders/{id}/cancel` solo en estado `created`; si está `at_terminal`, se cancela en la terminal. Devolver: `POST /v1/orders/{id}/refund` (total sin body, parcial con transacción y monto) hasta 90 días. Consultar: `GET /v1/orders/{id}` (órdenes de hasta 3 meses). `confirmed`
- Terminales: modo `PDV` obligatorio para integrar. `PATCH /terminals/v1/setup` con `{"terminals":[{"id","operating_mode":"PDV"}]}`. Requiere sucursal (store) y caja (POS) asociadas; **una sola terminal en PDV por caja**. Modelos soportados según referencia: NEWLAND_N950, INGENICO_MOVE2500, PAX_A910 (Point Smart 1 y 2). Listado de terminales: ver referencia "Obtener lista de terminales" (ruta exacta `needs-verification`). `confirmed`
- Webhook: tópico `order`, acciones `order.processed`, `order.canceled`, `order.refunded`, `order.action_required`, `order.failed`, `order.expired`. Firma `x-signature` (HMAC con la clave secreta de la app). Responder 200/201 en menos de 22 segundos; reintentos cada 15 minutos. `confirmed`
- Preautorización (garantía) en Point: no documentada. `needs-verification`

### QR con monto (QR dinámico)

| Medio | Al instante | Plazo alternativo |
|---|---|---|
| Dinero en cuenta (cualquier billetera o banco) | 0,80 % + IVA | — |
| Débito | 1,35 % + IVA | 0,85 % + IVA (2 días) |
| Crédito | 5,99 % + IVA | 4,19 % + IVA (10 días) |
| Cuotas sin tarjeta (Mercado Crédito) | 1,35 % + IVA | — |

- API: Orders API unificada; requiere sucursal y caja creadas. Modelos estático, dinámico e híbrido. Usar **dinámico** (un QR por cobro). `confirmed` (tipo exacto de orden para QR: `needs-verification` en la referencia).
- Mismo webhook de órdenes.

### Link de pago (Checkout Pro, ya integrado)

| Acreditación | Tasa |
|---|---|
| Al instante | 6,29 % |
| 10 días | 4,39 % |
| 18 días | 3,39 % |
| 35 días | 1,49 % |

Cuotas (costo si las absorbe el hotel): 2x 7,79 % · 3x 10,49 % · 6x 18,69 % · 9x 26,49 % · 12x 32,29 % · 18x 41,59 %. `confirmed` (IVA: `inferred`).

### Transferencia a alias / CVU

- Sin comisión al recibir. `inferred` (práctica habitual; confirmar en la cuenta del hotel).
- No genera un aviso por cobro como el QR. La confirmación automática requiere leer movimientos de la cuenta por API o reportes. `needs-verification` (qué endpoint de movimientos está disponible con el token OAuth del vendedor).

### Reserva de fondos (Checkout API online)

- `POST /v1/orders` con `capture_mode: "manual"`. Captura hasta **5 días** desde la creación; si no, se cancela. **Solo captura total**. Solo tarjeta de crédito. Cancelar: `POST /v1/orders/{id}/cancel`. `confirmed`

### Tarjetas guardadas

- Se puede guardar la tarjeta del cliente (`/v1/customers/{id}/cards`), pero **para cobrarla hay que volver a pedir el código de seguridad**. No sirve para cobrar un no-show sin el huésped. `confirmed`

### Suscripciones

- `/preapproval` y `/preapproval_plan`; cobra la tarjeta guardada sin intervención del comprador; frecuencias semanal, mensual y anual; reintentos automáticos; webhooks `subscription_preapproval` y `subscription_authorized_payment`. `confirmed`. Relevante para `08`.

## Payway (Prisma)

**Conexión:** no hay OAuth. El comercio pide a `soporte@payway.com.ar` las API keys pública y privada de Venta Online y el `site_id`. `confirmed`

### Aranceles máximos publicados

| Medio | Marca | Terminal / QR / débito automático / venta telefónica | E-commerce / link |
|---|---|---|---|
| Débito | Visa / Cabal / Discover | 1,2 % | 2,0 % |
| Débito | Mastercard | 1,4 % | 2,0 % |
| Crédito o prepaga | Visa / Mastercard / Cabal / Diners / Discover / UnionPay | 2,0 % | 3,0 % |
| Crédito | American Express | 2,8 % | 2,8 % |
| Transferencia por QR (PCT) | — | 0,8 % | — |

Todos "Nacional e Internacional". Monotributistas: débito 0 %. `confirmed`

### Plazos de acreditación

| Medio | Origen | Plazo |
|---|---|---|
| Débito | Nacional e internacional | 1 día hábil |
| Crédito 1 pago | Nacional | 5, 8, 10 o 18 días hábiles según categoría BCRA: 8 para comercios pequeños y micro registrados como PyME; 10 para medianos y grandes de turismo y alojamiento |
| Crédito 1 pago | Internacional | 18 días hábiles |
| American Express | Nacional e internacional | 9 días hábiles |
| Prepaga | Nacional / internacional | 2 / 18 días hábiles |
| Diners, Discover | Internacional | 2 días hábiles |
| Transferencia (PCT) | Nacional | Inmediato |

"Cobro Anticipado" permite cobrar en 24 horas hábiles con costo. `confirmed`

### API Venta Online (ex Decidir)

Fuente: SDKs oficiales `github.com/payway-ar/sdk-*-ventaonline`. Sandbox `https://developers.decidir.com/api/v2/`. `confirmed` salvo donde se indica.

- Pago: el front genera un token con la **clave pública** (PAN, vencimiento, CVV, titular, documento) y el back ejecuta el pago con la **clave privada**, `site_transaction_id`, monto (entero en centavos), moneda y cuotas. El PMS no toca datos de tarjeta si usa el formulario hospedado.
- Transacción en dos pasos: autorizar y luego **capturar** (`CapturePayment` con `amount`). Plazo máximo de captura: `needs-verification` con Payway.
- Link de pago: crea un formulario hospedado; URL `https://live.decidir.com/web/checkout/{payment_id}` (sandbox `developers.decidir.com/web/checkout/{payment_id}`). Historial de links con filtros por estado, fecha, monto y moneda (`ARS`/`USD`).
- Devoluciones: total, parcial y anulación de devolución.
- Tokenización: guarda la tarjeta después de un primer pago (`user_id`), pero el pago tokenizado vuelve a pedir el **código de seguridad**. "Pago PCI tokenizado" existe para comercios con certificación PCI (no es nuestro caso).
- 3DS disponible (`cardholder_auth_required`).
- Aviso de pago por webhook: no figura en el README del SDK. `needs-verification`. Mientras tanto, confirmar por consulta de estado del pago o del historial de links.

### Terminal

- Sin API pública para mandar el monto a la terminal; solo integraciones de partners homologados. `confirmed`
- Ofrecer "cobro asistido" (ver `06`).

## Getnet (Santander)

| Medio | Tasa | Acreditación |
|---|---|---|
| QR dinero en cuenta | 0,80 % | Inmediata |
| Débito | hasta 1,53 % / hasta 1 % | Inmediata / 1 día hábil |
| Crédito 1 pago | hasta 7,28 % / hasta 6,75 % / hasta 2 % | Inmediata / anticipada / 8 días hábiles |
| Crédito en cuotas | hasta 3,06 % / hasta 2,53 % / hasta 2 % | Inmediata / anticipada / 2 días hábiles |
| Adicional tarjeta internacional Visa y Mastercard | +0,7 % | — |

Todas + IVA. Terminal sin API pública documentada; ofrecer cobro asistido. `confirmed`

## Nave (Galicia)

- Tasas: débito 1,89 %, crédito 3,29 %, acreditación 24–48 h. Fuente: comparador de terceros (marzo 2026). `needs-verification`
- Tarjeta extranjera: no documentado. `needs-verification`
- API: solo cobro online (intención de pago y webhook). Credenciales en `integraciones@navenegocios.com`. Terminal sin integración pública. `confirmed`

## Fiserv / Clover

- Semi-integración documentada para Argentina (Cloud Pay Display y REST Pay Display), con cuotas, número de factura y promociones. Requiere alta como proveedor de software (ISV) con Fiserv. Tasas negociadas. `confirmed`
- Fuera del alcance inicial. Evaluar si el hotel ya opera con Posnet/Fiserv.

## PayPal (cuenta de EE. UU. del dueño)

Tarifario de PayPal EE. UU. vigente desde el 01/09/2026. `confirmed`

| Forma de cobro | Doméstico (pagador en EE. UU.) | Pagador de otro país |
|---|---|---|
| PayPal Checkout | 3,49 % + USD 0,49 | 4,99 % + USD 0,49 |
| Invoicing (factura) | 3,49 % + USD 0,49 | 4,99 % + USD 0,49 |
| Tarjeta sin cuenta PayPal | 2,99 % + USD 0,49 | 4,49 % + USD 0,49 |
| QR presencial de PayPal | 2,29 % + USD 0,09 | 3,79 % + USD 0,09 |
| Enviar/solicitar dinero por bienes y servicios (app) | 2,99 % | 4,49 % |

- Conversión de moneda: 4,00 % (3,00 % en algunos casos) si hay conversión.
- El QR presencial de PayPal es estático: el huésped escribe el monto. No sirve para el objetivo de "cero tipeo". Un QR del link del sistema cobra la tasa de Checkout.
- Autorizar y capturar: `intent=AUTHORIZE`; retención válida 29 días; "honor period" de 3 días; reautorización posible dentro de los 29 días. `confirmed`
- Guardar tarjeta para cobro posterior sin el cliente (vault): `needs-verification` para cuentas de EE. UU. con cliente extranjero.
- Conexión self-service de la cuenta del dueño: la vía oficial para plataformas (Partner Referrals / "Connect with PayPal" para cobrar por el vendedor) requiere que la plataforma sea partner aprobado de PayPal. `needs-verification`. Alternativa que funciona sin aprobación: el dueño crea una app REST en su cuenta y pega Client ID y Secret en el PMS.

## Stripe

- Argentina **no** es país soportado; en Latinoamérica solo Brasil y México. Stripe Atlas permite crear una empresa en EE. UU. con cuenta bancaria. `confirmed`
- Uso previsto: solo suscripción SaaS de la plataforma (ver `08`).

## SMS (para envío de links)

- Twilio Argentina: USD 0,0935 por SMS (marzo 2026). Plivo: USD 0,05249. Cobro por segmento de 160 caracteres. `confirmed` (fuentes: tarifario de Twilio y comparador).

## Fuentes

- Mercado Pago: [Point overview](https://www.mercadopago.com.ar/developers/es/docs/mp-point/overview), [procesamiento de pagos Point](https://www.mercadopago.com.ar/developers/es/docs/mp-point/payment-processing), [notificaciones Point](https://www.mercadopago.com.ar/developers/es/docs/mp-point/notifications), [modo de operación de terminales](https://www.mercadopago.com.ar/developers/es/reference/in-person-payments/point/terminals/update-operation-mode/patch), [QR](https://www.mercadopago.com.ar/developers/es/docs/qr-code/overview), [reservar y capturar](https://www.mercadopago.com.ar/developers/es/docs/checkout-api-v2/payment-management/reserve-capture-cancel), [tarjetas guardadas](https://www.mercadopago.com.ar/developers/es/docs/checkout-api/cards-and-customers-management/receive-payments-with-saved-cards), [OAuth](https://www.mercadopago.com.ar/developers/es/docs/security/oauth/introduction), [suscripciones](https://www.mercadopago.com.ar/developers/es/docs/subscriptions/overview), tasas de [Point Smart](https://www.mercadopago.com.ar/herramientas-para-vender/lectores-point/point-smart), [QR](https://www.mercadopago.com.ar/herramientas-para-vender/cobrar-con-qr) y [link](https://www.mercadopago.com.ar/herramientas-para-vender/link-de-pago).
- Payway: [aranceles y plazos](https://ayuda.payway.com.ar/cobros/plazos-acreditacion-y-comisiones), [dólar turista](https://ayuda.payway.com.ar/dolarturista-cotizacion), [cobro en moneda extranjera](https://ayuda.payway.com.ar/terminales/servicios-integrados/cobro-moneda-extranjera), [bimonetarismo](https://ayuda.payway.com.ar/como/cobrar-dolares), [SDK PHP Venta Online](https://github.com/payway-ar/sdk-php-ventaonline), [SDK JavaScript](https://github.com/payway-ar/sdk-javascript-ventaonline).
- Getnet: [aranceles](https://www.getnet.net/ar/aranceles). Nave: [plugin WooCommerce](https://wordpress.org/plugins/nave-for-woocommerce/), [comparador](https://www.comparapasarelas.com/nave-comisiones). Clover: [guía LATAM](https://docs.clover.com/dev/docs/quick-reference-guides-latam-developers).
- PayPal: [tarifas EE. UU.](https://www.paypal.com/us/business/paypal-business-fees), [autorizar y capturar](https://developer.paypal.com/docs/checkout/standard/customize/authorization/).
- Stripe: [países soportados](https://stripe.com/global). SMS: [Twilio Argentina](https://www.twilio.com/en-us/sms/pricing/ar), [comparador](https://www.sent.dm/en/resources/sms-pricing/argentina-sms-pricing).
