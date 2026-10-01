# 01 · Estado actual (commit `4a4c34e`)

Todo lo de este archivo es `confirmed` por lectura de código, salvo donde se indica.

> Este relevamiento describe el código observado en `4a4c34e`; no es una garantía del estado del `main` actual. La rama avanzó después de ese corte. Revalidar cada afirmación en el código desplegado antes de implementar o tomar una decisión operativa.

## Cobros

| Pieza | Estado | Evidencia | Notas |
|---|---|---|---|
| Ledger financiero | Funciona | `app/models/transaction.py` | `transactions` es la fuente de verdad. Ya tiene `gross_amount`, `tax_amount`, `fee_amount`, `net_amount`, `fx_rate_snapshot`, `provider_code`, `idempotency_key`, `created_by_user_id`. |
| Estado de pasarela | Funciona | `app/models/payment.py` | `payments`, `payment_links`, `payment_webhook_events`. Regla: `PaymentLink → webhook → Payment(completed) → Transaction`. |
| Efectivo y caja | Funciona | `app/models/cash_register.py`, `app/api/cash_register.py` | Sesiones, movimientos, cierre con diferencia aprobada y traspaso de custodia. |
| Link de Mercado Pago | Funciona de punta a punta | `app/services/payment_link_service.py`, `app/services/payment_webhook_service.py`, `app/api/payment_links.py` | Checkout Pro (`/checkout/preferences`), `external_reference` firmado, webhook con validación de `x-signature`, verificación contra la API de MP, idempotencia. Solo `provider="mercado_pago"` (`payment_link_service.py:295`). |
| Link desde la reserva web | Existe | `app/api/public_booking.py` (`POST /api/public/booking/payment-link(s)`) | Reutiliza el servicio de links. |
| Comprobante de transferencia | Funciona | `app/services/payment_proof_service.py`, `app/api/payment_proofs.py` | Subida de imagen, aprobación o rechazo con auditoría y creación de `Transaction` al aprobar. |
| Tarjeta crédito/débito | Manual | `PaymentMethodEnum.CREDIT_CARD/DEBIT_CARD` en `transaction.py` | Se registra a mano vía `POST /api/payments`. Sin vínculo con terminal. |
| QR de Mercado Pago | No existe | — | El hotel usa un QR estático impreso; no hay QR con monto ni aviso. |
| Posnet integrado | No existe | — | — |
| PayPal | No conectado | `app/adapters/paypal_adapter.py` | Usa `paypalrestsdk==1.13.3` (SDK v1 discontinuado). Ninguna ruta lo usa. |
| Recargo por medio de pago | Existe, con error de cálculo | `app/services/payment_service.py:144` (`calculate_payment_surcharge`), `app/models/payment_surcharge.py` | Calcula `base × %`, que cobra de menos. Ver fórmula correcta en `04`. |
| Precios por medio en tarifas | Existe, carga manual | `app/models/daily_rate.py` (`price_cash`, `price_transfer`, `price_mercadopago`, `price_paypal`, `price_credit_card`; `price_periods` además `price_debit_card`, `price_booking`, `price_expedia`) | Tipo `Float` (dinero en punto flotante). No hay cálculo automático. |
| Cotizaciones y conversión FX | Existe | `app/services/fx_service.py`, `app/models/fx_rate_snapshot.py` | DolarAPI: USD oficial/blue y cotizaciones oficiales directas de EUR, BRL, CLP y UYU; blue no USD se deriva y se identifica como estimado. El código de conversión excluye tarjeta, MEP, CCL, cripto y otros mercados. Caché y snapshots. |
| Cierre diario por medio | Existe | `app/services/cash_daily_summary_service.py:457` (`by_payment_method`) | — |
| Seña y no-show | Parcial | `hotel_configuration.deposit_percentage`, `enable_deposit_payment`, `free_cancellation_hours`, `cancellation_penalty_percentage`, `no_show_cutoff_hours`; `reservations.deposit_amount`, `no_show_policy_applied` | Hay política; no hay tarjeta en garantía ni cobro automático de no-show. |

## Conexiones

Catálogo sembrado en `app/services/integration_service.py:97` (`seed_catalog`). Pantalla: `frontend/src/views/protected/SettingsConnectionsPage.tsx`. Credenciales cifradas con Fernet (`encrypt_payload`/`decrypt_payload`).

| Proveedor | Tipo en catálogo | Cómo conecta hoy | Refresh de token | Uso real | Estado |
|---|---|---|---|---|---|
| Mercado Pago | `oauth_code` | Manual: el dueño crea su propia app en MP y pega `access_token` (guía en `docs/conexiones/mercadopago/README.md`). El OAuth existe en código (`build_redirect_url`, `exchange_token`) pero depende de `MERCADOPAGO_CLIENT_ID/SECRET` de una app de la plataforma. | No implementado para MP | Links de pago y webhooks | Funciona en modo manual. OAuth sin terminar. |
| PayPal | `oauth_code` | OAuth con `PAYPAL_CLIENT_ID` de la plataforma y "Log in with PayPal" (scopes de identidad). | No | Ninguno | No sirve para cobrar: el login de identidad no otorga permisos de cobro sobre la cuenta del dueño. |
| Gmail | `oauth_code` | OAuth de Google con `gmail.send`, `access_type=offline`. | Sí (`refresh_gmail_access_token`) | Envío de mails del hotel | Funciona. Requiere verificación de la app de Google para producción abierta (`needs-verification` del estado actual de la verificación). |
| WhatsApp | `bearer_token` | `POST /api/whatsapp/channel/complete` guarda `waba_id` y `phone_number_id`. No hay flujo de Embedded Signup ni llamadas a Graph API. Webhook de entrada en `app/api/whatsapp_meta_webhook.py`. | — | Bandeja interna del CRM | Parcial: sin alta self-service ni envío real por Cloud API. |
| Booking / Expedia | `bearer_token` / `signature` | Credenciales manuales | — | OTAs | Fuera de alcance de esta spec. |
| Stripe (plataforma) | — (master admin) | `app/master_admin/stripe.py`: guarda secret key y webhook secret, valida contra `/v1/account`. `POST /api/master-admin/stripe/webhook` verifica firma y guarda el evento. | — | Ninguno | Parcial: no crea clientes, suscripciones ni actualiza el estado de suscripción del hotel. |
| Stripe (hotel) | — | `onboarding_service.py:403,436` usa "stripe" como proveedor de tarjeta del hotel para planes pro/ultra | — | — | **Contradice la decisión del producto**: Stripe no es medio de cobro de hoteles. Hay que retirarlo del onboarding del hotel. |
| Legacy `/api/connections` | — | `app/main.py:447` devuelve error "retirada"; `app/api/connections.py` y `app/services/connection_service.py` quedaron sin uso | — | — | Código muerto a eliminar. |

## Hallazgos a corregir como parte del trabajo

1. `calculate_payment_surcharge` recarga con `base × %`. Reemplazar por la fórmula de `04`.
2. Precios por medio en `Float`. Migrar a `Numeric(12,2)`.
3. Stripe aparece como medio de cobro del hotel en onboarding. Quitarlo.
4. El OAuth de PayPal pide scopes de identidad; no sirve para cobrar. Reemplazar según `03`.
5. `paypalrestsdk` discontinuado. Reemplazar por llamadas REST a Orders v2 / Invoicing v2.
6. Mercado Pago no tiene refresh de token OAuth (el refresh token dura 6 meses según la documentación oficial).
7. Código legacy de `/api/connections` sin uso.
