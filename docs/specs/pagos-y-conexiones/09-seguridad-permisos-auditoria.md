# 09 · Seguridad, permisos y auditoría

## Permisos nuevos

Formato existente `dominio:acción`. Agregar con el skill `new-permission` (catálogo, guardia backend, gate frontend, migración y verificación en navegador por rol).

| Código | Qué permite | Dueño / co-dueño | Recepcionista (default) | Confirmación reforzada |
|---|---|---|---|---|
| `integration:view` | Ver estado de conexiones | Sí | No | — |
| `integration:manage` | Conectar, probar, desconectar, editar terminales | Sí | No | Sí |
| `payment:channel_manage` | Crear canales y cargar tasas | Sí | No | — |
| `payment:collect` | Usar el asistente de cobro | Sí | Sí | — |
| `payment:custom_amount` | Cobrar un monto distinto del calculado | Sí | No | Sí |
| `payment:pricing_override` | Aplicar precio único en una sesión | Sí | No | — |
| `payment:refund` | Devolver pagos | Sí | No | Sí |
| `payment:guarantee_capture` | Cobrar un cargo sobre una garantía | Sí | Configurable | Sí |
| `payment:reconciliation_view` | Ver la bandeja de conciliación | Sí | No | — |
| `checkin:override_payment` | Hacer check-in sin el pago requerido | Sí | No | — |

La confirmación reforzada reutiliza el mecanismo de step-up existente (`app/services/action_step_up_service.py`, `_require_action_step_up` en `app/dependencies/auth.py`).

## Secretos

- Credenciales de proveedores solo en el payload cifrado de `integration_connections` (Fernet, `encrypt_payload`). Nunca en respuestas de API, logs, eventos de auditoría ni en el frontend.
- Claves privadas (Payway, PayPal secret, MP access token) solo en el backend. La clave pública de Payway puede ir al frontend si se usa tokenización propia; preferir formularios hospedados.
- Rotación: "Reconectar" reemplaza credenciales y registra el evento.
- `redact_integration_error` se aplica a todo error de proveedor antes de guardarlo.

## Datos de tarjeta (PCI)

- El PMS no recibe, procesa ni guarda número de tarjeta ni código de seguridad. Solo formularios hospedados del proveedor, terminales o tokens del proveedor.
- En cobro asistido solo se guardan últimos 4 dígitos, marca, autorización, lote y cupón.
- Test automático que falla si alguna columna o log contiene una secuencia de 13 a 19 dígitos que pase la validación de Luhn.

## Webhooks

- Validar firma en todos (MP `x-signature`, PayPal `verify-webhook-signature`, Stripe `Stripe-Signature`).
- Resolver el hotel por dato firmado (`external_reference` firmado o `external_account_id` de la conexión), nunca por un parámetro de la URL sin firmar.
- Cuerpo acotado (`read_bounded_body` existente) y respuesta rápida; procesamiento pesado en job.
- Idempotencia por id de evento del proveedor.

## Aislamiento por hotel

- Toda tabla nueva lleva `hotel_id` y claves foráneas compuestas `(hotel_id, id)` como las existentes en `payments`.
- Toda consulta filtra por el hotel del contexto de autenticación.
- Un terminal, canal o conexión de un hotel no puede usarse en una sesión de otro (test explícito).

## Auditoría

Registrar con `audit_log_service` (acción, usuario, hotel, antes/después, sin secretos):

- Conectar, reconectar y desconectar proveedores; cambios de terminales.
- Alta y cambio de tasas de canales.
- Creación, cambio de canal, cancelación y cierre de sesiones de cobro.
- Montos personalizados, overrides de precio, check-in sin pago.
- Devoluciones, capturas y liberaciones de garantía.
- Resultados de conciliación y resolución de diferencias.

Reporte para el contador: por período, cada cobro con reserva, huésped, canal, moneda, bruto, comisión, IVA de la comisión, neto, cotización y referencia del proveedor. Exportable a CSV.

## Prevención de fraude interno

- El recepcionista no ve credenciales ni puede generar cobros fuera de una reserva.
- Los links se generan solo desde el PMS; la conciliación marca cobros del proveedor que no salieron del PMS.
- Cambiar el canal de una parte ya enviada al proveedor exige cancelarla primero en el proveedor.
- Alerta al dueño ante: devoluciones, montos personalizados, check-in sin pago, diferencias de conciliación y cobros asistidos sin liquidación después de 3 días hábiles.
