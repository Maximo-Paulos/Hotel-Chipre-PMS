# Dominio y datos

Estado: `confirmed` para inventario de archivos; `needs-verification` para auditoría completa de cada relación.

Hay 42 módulos de modelo en `app/models/`, que cubren hotel/configuración/membresías, usuario/permisos, huéspedes, reservas, habitaciones/bloques/tarifas, transacciones/pagos/reembolsos, caja, empresas/documentos, integraciones/OTAs, stock/lavandería, analítica/auditoría y suscripciones.

`hotel_id` es un límite de aislamiento frecuente; cualquier servicio/query nuevo debe tomar contexto autenticado y filtrar por hotel antes de leer o escribir. Ver [inventario de migración](../_generated/migration-head.md) para el head actual y no inferir esquema desde documentación histórica.

## Efectivo entregado, vuelto y propina

Estado: `confirmed` para la decisión del dueño; `validated-local` para la implementación en el working tree, sin QA cloud.

La decisión del 2026-10-23 es registrar por separado efectivo recibido, vuelto y propina voluntaria. La diferencia se devuelve por defecto; si el huésped decide dejarla, se ingresa explícitamente como propina. El importe de la reserva y sus asignaciones conservan el monto bruto aplicado; la propina se muestra separada y no incrementa el ingreso de alojamiento. La caja conserva el efectivo neto físicamente retenido, incluido el importe de propina.

La migración `20261023_cash_tender_change` añade esos campos y restricciones para cobros individuales y grupales. Código principal: [payment_service.py](../../app/services/payment_service.py), [reservation_group_payment_service.py](../../app/services/reservation_group_payment_service.py), [cash_daily_summary_service.py](../../app/services/cash_daily_summary_service.py) y [migración](../../alembic/versions/20261023_cash_tender_change.py). Evidencia local del 2026-10-23: 107 pruebas backend focales y 3 E2E Chromium con una base PostgreSQL limpia hasta `20261023_housekeeping_checklists`; ver [auditoría de escenarios y validación](../../docs/audits/auditoria-thermos-antislop-escenarios-pms-2026-10-22.md). No hubo cobros reales ni QA cloud. El trabajo sigue sin commit en la rama `refactor/app-quality-audit`, basada en HEAD `563ddc01d4b71ee63fce3a7115e02e83600d2ec3`.
