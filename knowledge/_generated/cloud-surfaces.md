# Superficies cloud

Generado: 2026-09-01T12:12:23.860163+00:00
Commit: `9aee997`

## canonical

- https://app.hotels-pms.com
- https://hotels-pms.com
- https://api.hotels-pms.com

## production_render_qa

- Render producción en el deploy normal de main, verificado por SHA y /health
- Frontend canónico https://app.hotels-pms.com contra la API canónica
- Hotel de prueba autorizado con datos sintéticos/reversibles y efectos externos deshabilitados

## historical_or_needs_verification

- Cualquier host hoteles-pms.com o onrender.com citado por documentación histórica
- Callbacks de pagos, email, WhatsApp y OTAs: validar por contrato, no ejecutar en QA cloud

Datos estructurados: [cloud-surfaces.json](cloud-surfaces.json).
