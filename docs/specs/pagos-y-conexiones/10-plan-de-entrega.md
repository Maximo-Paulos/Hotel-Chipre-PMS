# 10 · Plan de entrega

Cada fase se entrega en una o más PRs chicas, con tests, migraciones reversibles y la validación del repo (`validate-all`). Los cambios de comportamiento visible llevan evidencia de QA en preview (`cloud-user-qa`). Después de cambiar código, regenerar Graphify según `CLAUDE.md`.

## Fase 0 — Limpieza y base (≈ 3 días)

- F0.1 Quitar Stripe de la configuración de cobro del hotel (`onboarding_service.py`, schemas y frontend).
- F0.2 Eliminar código legacy de `/api/connections` (`app/api/connections.py`, `app/services/connection_service.py`, schema asociado) si nada lo importa.
- F0.3 Migrar precios por medio de `Float` a `Numeric(12,2)` en `daily_rates` y `price_periods`.
- F0.4 Agregar `fee_vat_amount` a `transactions`.

Aceptación: tests existentes en verde; migración sube y baja en SQLite y PostgreSQL.

## Fase 1 — Canales, tasas y precios (≈ 1,5 semanas)

- F1.1 Tablas `payment_channels` y `payment_channel_rates`; seed de canales básicos (efectivo, transferencia) por hotel.
- F1.2 `payment_pricing_service.py` con las fórmulas de `04` y sus casos de prueba; reemplazar `calculate_payment_surcharge`.
- F1.3 Configuración del hotel: modo de precio, redondeo, tipo de cotización.
- F1.4 `target_net_price` en tarifas y overrides por canal; pantalla de Tarifas con la tabla calculada.
- F1.5 Pantalla "Canales de cobro" con tasas sugeridas de `02` (con fecha) y edición con historial.
- F1.6 `reservations.target_net_total` y `net_covered` en pagos; `_sync_reservation_financial_status` basado en saldo neto.

Aceptación: criterios de `04`.

## Fase 2 — Asistente de cobro con efectivo, transferencia y link MP existente (≈ 2 semanas)

- F2.1 `payment_sessions` y `payment_session_parts`; servicio y API de `05`.
- F2.2 `PaymentWizard` en frontend (un medio y pago dividido).
- F2.3 Efectivo integrado con la caja; transferencia con comprobante (reutiliza `payment_proof_service`); link MP desde una parte.
- F2.4 Permisos `payment:collect`, `payment:custom_amount`, `payment:pricing_override`, `checkin:override_payment`.
- F2.5 Bloqueo de check-in según pago requerido.

Aceptación: criterios de `05` para estos medios.

## Fase 3 — Hub de conexiones y Mercado Pago OAuth (≈ 1,5 semanas)

Prerequisito: D3 (app de integrador de PMS Paulus en Mercado Pago).

- F3.1 Columnas nuevas de catálogo y conexiones; estados y health check; `POST /test`.
- F3.2 OAuth de MP con PKCE, refresh de token y job diario.
- F3.3 Rediseño de la pantalla Conexiones por categorías.
- F3.4 Permisos `integration:view` e `integration:manage`.

Aceptación: criterios de `03` para MP.

## Fase 4 — QR dinámico y Point (≈ 2,5 semanas)

- F4.1 Asistente de sucursal, caja y terminales (`payment_terminals`, `PATCH /terminals/v1/setup`).
- F4.2 Orden QR dinámica y dibujo del QR con monto.
- F4.3 Orden Point, cancelación y devolución.
- F4.4 Webhook de órdenes y job de respaldo.
- F4.5 Prueba real con una Point Smart en cuenta de prueba y otra con una tarjeta extranjera (resuelve `needs-verification` de `02`).

Aceptación: criterios de `05` y `06` para QR y Point.

## Fase 5 — PayPal EE. UU. y Payway (≈ 2 semanas)

- F5.1 Conexión PayPal por credenciales del dueño con registro de webhook; retirar `paypalrestsdk`.
- F5.2 Orders v2 (link y QR del link), captura, devolución, comisión real; precio en USD con cotización congelada.
- F5.3 Conexión Payway Venta Online y link en ARS.
- F5.4 Terminales asistidas (Payway, Getnet, Nave) en el asistente.

Aceptación: criterios de `06` para PayPal y Payway.

## Fase 6 — Conciliación (≈ 2 semanas)

- F6.1 `provider_settlement_lines` y bandeja de diferencias.
- F6.2 Mercado Pago por API; Payway/Getnet/Nave por archivo; PayPal por API si el permiso está disponible.
- F6.3 Reporte para el contador (CSV).

## Fase 7 — Garantías y seña web (≈ 2 semanas)

- F7.1 Garantía con MP (retención de hasta 5 días) y PayPal (autorización de 29 días).
- F7.2 Catálogo de cargos, captura y liberación automática.
- F7.3 Seña obligatoria configurable y vencimiento de reservas web sin seña.
- F7.4 Tarifas no reembolsables con prepago.

## Fase 8 — SMS (≈ 3 días) · Fase 9 — Suscripción SaaS (≈ 1,5 semanas, depende de D2) · Fase 10 — WhatsApp Embedded Signup (depende de D4)

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Tasas de proveedores cambian | Tasas en datos con historial, nunca en código; conciliación muestra la comisión real |
| Mercado Pago no acepta tarjetas extranjeras en Point o link | Prueba en F4.5; si falla, marcar `accepts_foreign_cards = false` y ofrecer Payway o PayPal |
| Plazo de captura de Payway desconocido | Consultar a Payway antes de F7; no ofrecer garantía por Payway hasta confirmarlo |
| Aprobaciones de terceros (MP integrador, Google, Meta, entidad para Stripe) | Iniciar trámites en paralelo a la Fase 1 |
| Validez legal de precios por medio de pago | D1; el modo `uniform_list` está disponible desde la Fase 1 |

## Cómo usar esta spec (para el agente de desarrollo)

1. Leer `README.md` y `01` antes de tocar código.
2. Implementar por fase, una PR por ticket o por grupo chico.
3. Todo `needs-verification` que afecte la fase en curso se resuelve primero (consulta al proveedor o prueba en sandbox) y se actualiza `02`.
4. No agregar tasas, credenciales ni URLs de producción en código.
5. Al cerrar cada fase, actualizar `01-estado-actual.md`.
