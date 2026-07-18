# Manifiesto de superficies cloud

Estado: `confirmed` para los tres dominios canónicos; `needs-verification` para URLs dinámicas de preview y variables privadas de proveedor.

| Tipo | URL / patrón | Acceso | Política QA |
| --- | --- | --- | --- |
| App | `https://app.hotels-pms.com` | protegido + master-admin | Login devolvió HTTP 200 el 2026-07-18; Vercel Production usa la API canónica. No usar producción compartida para regresión. |
| Marketing | `https://hotels-pms.com` | público | Devolvió HTTP 200 el 2026-07-18; verificar navegación/SEO básico. |
| API | `https://api.hotels-pms.com` | pública controlada/protegida | Un primer intento agotó 20 s; el reintento con 60 s devolvió HTTP 200 el 2026-07-18. Vigilar posible cold start; no reemplaza UI QA. |
| Vercel preview | URL por PR | público/protegido QA | Git puede crearla, pero queda no válida para QA hasta compilarla contra backend aislado exacto. |
| Render preview | URL por PR + `/health` | backend QA | PR Previews está `Off`; habilitar sólo Manual tras confirmar DB/secrets QA aislados. |
| Supabase Branch | conexión por PR | sólo backend preview | Sin datos reales, migrada y seed QA. |
| Callbacks | pagos/email/WhatsApp/OTA | externo | Excluidos de ejecución QA; validar contrato/adapters. |

Las URLs antiguas `hoteles-pms.com` y proveedores `*.onrender.com` citados por documentación quedan `historical` hasta confirmación. El JSON reproducible está en `../_generated/cloud-surfaces.json`.
