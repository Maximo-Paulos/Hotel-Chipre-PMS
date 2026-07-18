# Manifiesto de superficies cloud

Estado: `confirmed` para dominios canónicos; `needs-verification` para URLs dinámicas de preview.

| Tipo | URL / patrón | Acceso | Política QA |
| --- | --- | --- | --- |
| App | `https://app.hotels-pms.com` | protegido + master-admin | Referencia actual; no usar para regresión de cambios. |
| Marketing | `https://hotels-pms.com` | público | Verificar navegación/SEO básico. |
| API | `https://api.hotels-pms.com` | pública controlada/protegida | Health y contratos; no reemplaza UI QA. |
| Vercel preview | URL por PR | público/protegido QA | Obligatoria para cada cambio funcional. |
| Render preview | URL por PR + `/health` | backend QA | Debe usar DB/secrets QA aislados. |
| Supabase Branch | conexión por PR | sólo backend preview | Sin datos reales, migrada y seed QA. |
| Callbacks | pagos/email/WhatsApp/OTA | externo | Excluidos de ejecución QA; validar contrato/adapters. |

Las URLs antiguas o proveedores `*.onrender.com` citados por documentación quedan `historical` hasta confirmación. El JSON reproducible está en `../_generated/cloud-surfaces.json`.
