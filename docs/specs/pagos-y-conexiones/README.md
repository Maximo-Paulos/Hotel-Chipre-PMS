# Especificación: cobros, conexiones y garantías

Documentación para que un agente de desarrollo implemente el módulo de cobros y el hub de conexiones del PMS. Está escrita para ejecutarse en fases, con criterios de aceptación verificables. No contiene código de implementación.

- **Relevado:** 27–28/09/2026 sobre el commit `4a4c34e` de `main`.
- **Presentación para el dueño:** https://claude.ai/artifact/NktokpoAkqW1eZv5aL4LWv (privada; compartir desde su menú).
- **Estados de certeza** (según `knowledge/00-control/SOURCE-OF-TRUTH.md`): `confirmed` = leído en código o en documentación oficial del proveedor; `inferred` = deducido, sin fuente directa; `needs-verification` = hay que confirmarlo con el proveedor o con una prueba real antes de implementar.

## Objetivo del producto

1. El recepcionista cobra cualquier medio siguiendo un asistente en pantalla, sin tipear montos (salvo el efectivo recibido y el reparto de un pago dividido) y sin acceso a las cuentas del dueño.
2. Todo cobro queda registrado con bruto, comisión, IVA de la comisión, neto, canal y tasa aplicada, y se concilia contra el proveedor.
3. El dueño del hotel conecta él mismo sus proveedores (Mercado Pago, Payway, PayPal, Gmail, WhatsApp) desde "Conexiones", igual que se conecta una cuenta de Google.
4. El dueño define en Tarifas si cobra distinto por medio de pago (precio de lista + bonificaciones) o el mismo precio para todos.
5. Huéspedes extranjeros pueden pagar con tarjeta extranjera, y se puede tomar una tarjeta en garantía o una seña.
6. Stripe se usa solo para que la plataforma (PMS Paulus) cobre la suscripción mensual a los hoteles. No es un medio de cobro de los hoteles.

## Índice

| Archivo | Contenido |
|---|---|
| [01-estado-actual.md](01-estado-actual.md) | Qué existe hoy en código, qué funciona de punta a punta y qué no |
| [02-proveedores-de-cobro.md](02-proveedores-de-cobro.md) | Cada proveedor: tarjetas extranjeras, costos, acreditación, API, garantía, fuentes |
| [03-hub-de-conexiones.md](03-hub-de-conexiones.md) | Arquitectura de conexiones self-service por proveedor |
| [04-canales-tarifas-y-precios.md](04-canales-tarifas-y-precios.md) | Canales de cobro, tasas con vigencia, fórmula de precio, modos de precio, dólares |
| [05-asistente-de-cobro.md](05-asistente-de-cobro.md) | El paso a paso del recepcionista, pago dividido, estados y API |
| [06-integraciones-de-cobro.md](06-integraciones-de-cobro.md) | Detalle técnico por medio: QR, Point, links, PayPal, Payway, transferencias, conciliación |
| [07-garantias-senas-y-no-show.md](07-garantias-senas-y-no-show.md) | Depósito de garantía, seña en reservas web, no-show |
| [08-stripe-suscripcion-saas.md](08-stripe-suscripcion-saas.md) | Cobro de la suscripción de la plataforma |
| [09-seguridad-permisos-auditoria.md](09-seguridad-permisos-auditoria.md) | Permisos, secretos, auditoría, PCI |
| [10-plan-de-entrega.md](10-plan-de-entrega.md) | Fases, tickets, criterios de aceptación y pruebas |

## Decisiones abiertas (las toma el dueño del producto)

| # | Decisión | Recomendación | Bloquea |
|---|---|---|---|
| D1 | Validación legal de precios distintos por medio de pago (Ley 25.065 art. 37 inc. c; Res. 51-E/2017) | Consultar contador y abogado. El sistema soporta ambos modos | Nada técnico; afecta el modo por defecto |
| D2 | Stripe para la suscripción: Argentina no es país soportado por Stripe | Usar Stripe solo si existe o se crea una entidad en EE. UU. (Stripe Atlas). Alternativa local: Mercado Pago Suscripciones | Fase de suscripción SaaS |
| D3 | Registrar la plataforma como integrador de Mercado Pago (app propia con OAuth) | Sí: habilita "Conectar con Mercado Pago" en un clic | Conexión self-service de MP y Point |
| D4 | Registrar la plataforma como Tech Provider de Meta | Sí, cuando se priorice WhatsApp | Alta self-service de WhatsApp |
| D5 | Verificación de la app de Google (scope `gmail.send` es sensible) | Iniciar verificación de marca y de scope | Gmail para más de los usuarios de prueba |
| D6 | Proveedor de SMS | Plivo o Twilio. Costo ≈ USD 0,05–0,09 por SMS a Argentina | Envío de links por SMS |
| D7 | Tipo de cotización para precios en USD | Oficial (venta), configurable por hotel | Precios en USD |
| D8 | Regla de pago dividido | La del dueño: total = precio del medio más caro entre los elegidos | Ya decidida |
