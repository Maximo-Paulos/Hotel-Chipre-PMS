# 08 · Suscripción de la plataforma (Stripe)

## Decisión de producto

Stripe se usa **solo** para que PMS Paulus cobre la suscripción mensual a los hoteles. No es un medio de cobro de los hoteles a sus huéspedes. Retirar "stripe" de `app/services/onboarding_service.py` (líneas 290, 403, 436-438) y de cualquier pantalla de medios de pago del hotel.

## Restricción que hay que resolver primero (D2)

Stripe no admite cuentas de empresas radicadas en Argentina (en Latinoamérica solo Brasil y México). Para usarlo, la plataforma necesita una entidad soportada, por ejemplo una empresa en EE. UU. creada con Stripe Atlas, con cuenta bancaria en EE. UU. y facturación en USD. `confirmed`

Alternativas si no se crea la entidad:
- **Mercado Pago Suscripciones** (`/preapproval_plan`, `/preapproval`) con la cuenta de la plataforma: cobra en ARS con tarjeta guardada sin intervención del hotel, reintentos automáticos, webhooks `subscription_preapproval` y `subscription_authorized_payment`. Disponible en Argentina. `confirmed`
- Cobro manual por transferencia con factura (situación actual).

Recomendación: diseñar una interfaz `BillingProvider` con dos implementaciones (Stripe y Mercado Pago Suscripciones) y activar la que corresponda según D2.

## Estado actual

- `app/master_admin/stripe.py`: guarda secret key y webhook secret, valida con `GET /v1/account`.
- `POST /api/master-admin/stripe/webhook`: verifica firma y guarda el evento en `MasterStripeWebhookEvent` (idempotente). **No procesa** el evento.
- `app/models/subscription_v2.py` y `app/services/subscription_entitlements.py`: planes y habilitaciones internas.

## Diseño

- Productos y precios en Stripe por plan (`starter`, `pro`, `ultra`, según `PLAN_CATALOG` en `app/services/subscription_service.py`), mensuales. Guardar `stripe_price_id` en el plan.
- Alta: el dueño elige plan en `/api/subscription/plan` → el backend crea un Customer y una Checkout Session en modo `subscription` y devuelve la URL. Al volver, el webhook confirma.
- Gestión: Customer Portal de Stripe para cambiar tarjeta, plan o cancelar.
- Webhooks a procesar: `checkout.session.completed`, `customer.subscription.created|updated|deleted`, `invoice.paid`, `invoice.payment_failed`. Actualizar `Subscription` (estado, período actual, plan) y las habilitaciones.
- Falta de pago: período de gracia configurable; luego restringir el acceso según la política de facturación existente (`app/master_admin/billing_policy.py`, que ya decide acceso por estado de suscripción: `allow_active`, `allow_trialing`, exenciones). Qué ve un hotel en mora (solo lectura o bloqueo) es decisión de producto.
- Facturación fiscal argentina de la plataforma: fuera de alcance técnico; definir con el contador.

## Criterios de aceptación

1. Un hotel se suscribe con tarjeta de prueba en modo test de Stripe y su plan queda activo solo después del webhook.
2. `invoice.payment_failed` marca la suscripción en mora y notifica al dueño.
3. Un evento repetido no cambia dos veces el estado.
4. Ninguna pantalla del hotel ofrece Stripe para cobrar a huéspedes.
