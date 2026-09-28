# 07 · Garantías, señas y no-show

## Lo que se quiere

1. **Depósito de garantía en el hotel:** al hacer check-in se retiene un monto en la tarjeta del huésped (aunque pague la estadía en efectivo). Si no pasa nada, se libera. Si hay un daño o faltante (llave, toalla), se cobra lo que corresponde.
2. **Seña en reservas:** toda reserva exige seña, salvo que el dueño lo desactive.
3. **Tarjeta en garantía por no-show** en reservas sin cancelación gratuita hechas por la web del hotel.

## Qué permite cada proveedor (documentación oficial)

| Necesidad | Mercado Pago | Payway Venta Online | PayPal EE. UU. | Terminales |
|---|---|---|---|---|
| Retener y capturar después | Sí, online: `capture_mode: "manual"`. **Máximo 5 días**, solo crédito, **solo captura total** | Sí: transacción en dos pasos y `CapturePayment` con monto. Plazo máximo `needs-verification` | Sí: `intent=AUTHORIZE`; retención 29 días, 3 días de "honor period", reautorizable | Preautorización en Point: no documentada. Payway, Getnet y Nave: según terminal, `needs-verification` |
| Cobrar después una tarjeta guardada sin el huésped | **No**: la tarjeta guardada pide de nuevo el código de seguridad | **No** en modo estándar: el pago tokenizado pide código de seguridad. Solo comercios con certificación PCI | `needs-verification` (vault) | No aplica |
| Cobro recurrente sin el huésped | Solo con Suscripciones (no aplica a hoteles) | — | — | — |

Conclusiones:
- En Argentina, **no se puede guardar una tarjeta y cobrar un no-show semanas después sin el huésped** con estos proveedores en modo estándar. Guardar números de tarjeta en el PMS está prohibido (PCI).
- La garantía de no-show se resuelve con **seña o prepago** según la política de cancelación, no con tarjeta guardada.
- El depósito de garantía en el hotel se resuelve con **retención y captura**, con los límites de cada proveedor.

## Diseño: depósito de garantía

Configuración por hotel: `guarantee_enabled`, `guarantee_amount` (monto fijo ARS o USD), `guarantee_channel_id`, `guarantee_release_hours_after_checkout` (default 24).

Flujo:
1. En el check-in, el asistente (`05`) ofrece "Garantía" con propósito `guarantee` por el monto configurado.
2. **Mercado Pago (estadías de hasta 4 noches):** el huésped carga la tarjeta en un formulario hospedado de MP (Checkout API / Brick) desde el celular por QR o en la tablet de recepción. Se crea la orden con `capture_mode: "manual"`. El PMS nunca ve la tarjeta.
3. **PayPal (extranjeros, hasta 29 días):** orden con `intent: "AUTHORIZE"`. Reautorizar automáticamente al vencer el honor period de 3 días si la estadía continúa.
4. **Payway (estadías largas):** transacción en dos pasos, si el plazo de captura lo permite (`needs-verification`).
5. Durante la estadía, la garantía aparece en la reserva con monto, vencimiento de la retención y botón "Cobrar cargo".
6. **Cobrar un cargo:** el empleado con permiso `payment:guarantee_capture` elige ítems de un catálogo configurable (Llave $X, Toalla $Y, Daños con monto y foto obligatoria) y confirma con reautenticación. Con Mercado Pago **solo se puede capturar el total**: si el cargo es menor, capturar el total y devolver la diferencia en el acto, o cancelar la retención y crear un cobro nuevo por el cargo con la tarjeta del huésped presente. Con PayPal y Payway se captura el monto del cargo.
7. **Liberar:** al check-out sin cargos, o automáticamente pasadas `guarantee_release_hours_after_checkout` horas, se cancela la retención (`POST /v1/orders/{id}/cancel` en MP, void en PayPal).
8. Alerta cuando una retención está por vencer y el huésped sigue alojado (MP a los 4 días).

Datos: la garantía es una `payment_session` con `purpose = guarantee` y una parte con estado adicional `authorized`. Solo al capturar se crea `Transaction`.

Límite a comunicar: con Mercado Pago, la retención no sirve para estadías de más de 5 días. Para esas, usar PayPal (extranjeros), Payway si confirma plazo, o un depósito cobrado y devuelto al salir.

## Diseño: seña

Ya existen `deposit_percentage`, `enable_deposit_payment`, `enable_full_payment` y el estado `deposit_paid`.

- Agregar `deposit_required` (Boolean, default `true`) y `deposit_due_hours` (plazo para pagar la seña antes de liberar la reserva, default 24).
- La seña se expresa en neto (`deposit_percentage × target_net_total`) y se cobra con una sesión `purpose = deposit` (`04`, `05`).
- Reservas por la web (futuro sitio del hotel, `public_booking`): al reservar, el huésped elige el medio de la seña entre los canales habilitados para web (link de MP, link de Payway, PayPal). La reserva queda `pending` hasta el pago; vence si no se paga en `deposit_due_hours`.
- Reservas manuales: el recepcionista envía el link de seña desde la reserva.

## Diseño: no-show en reservas sin cancelación gratuita

- Tarifas marcadas como `non_refundable` (nuevo flag en tarifas o plan de tarifa) exigen **prepago total** o seña igual al monto de la penalidad de no-show.
- `no_show_policy_applied` (existente) registra qué se retuvo. El dinero ya cobrado se imputa a la penalidad; no se intenta cobrar una tarjeta después.
- Si en el futuro un proveedor ofrece cobro sin el titular (por ejemplo, Stripe con una entidad fuera de Argentina, o PayPal vault), se agrega como canal nuevo sin cambiar el modelo.

## Criterios de aceptación

1. Una garantía de MP no liberada al día 4 genera alerta; al día 5 el sistema la muestra como vencida.
2. Capturar un cargo menor que la garantía de MP devuelve la diferencia en el mismo acto y deja dos movimientos trazables.
3. Liberar una garantía no crea `Transaction`.
4. Una reserva web sin seña pagada a las `deposit_due_hours` pasa a vencida y libera el cupo.
5. El PMS no persiste números de tarjeta ni códigos de seguridad en ninguna tabla ni log.
