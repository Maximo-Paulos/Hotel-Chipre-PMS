# Dominio y datos

Estado: `confirmed` para inventario de archivos; `needs-verification` para auditoría completa de cada relación.

Hay 42 módulos de modelo en `app/models/`, que cubren hotel/configuración/membresías, usuario/permisos, huéspedes, reservas, habitaciones/bloques/tarifas, transacciones/pagos/reembolsos, caja, empresas/documentos, integraciones/OTAs, stock/lavandería, analítica/auditoría y suscripciones.

`hotel_id` es un límite de aislamiento frecuente; cualquier servicio/query nuevo debe tomar contexto autenticado y filtrar por hotel antes de leer o escribir. Ver [inventario de migración](../_generated/migration-head.md) para el head actual y no inferir esquema desde documentación histórica.
