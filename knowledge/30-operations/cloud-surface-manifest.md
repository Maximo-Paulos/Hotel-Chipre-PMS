# Manifiesto de superficies cloud

Estado: `confirmed` para los tres dominios canónicos; `needs-verification` para variables privadas y el SHA live de cada deploy.

| Tipo | URL / patrón | Acceso | Política QA |
| --- | --- | --- | --- |
| App | `https://app.hotels-pms.com` | protegido + master-admin | Superficie autorizada para la QA funcional del hotel de prueba después de verificar el SHA live de Render. |
| Marketing | `https://hotels-pms.com` | público | Devolvió HTTP 200 el 2026-07-18; verificar navegación/SEO básico. |
| API | `https://api.hotels-pms.com` | pública controlada/protegida | Un primer intento agotó 20 s; el reintento con 60 s devolvió HTTP 200 el 2026-07-18. Vigilar posible cold start; no reemplaza UI QA. |
| Render producción | servicio `main` + `/health` | backend productivo autorizado | `Production Render QA cycle` verifica el deploy live, el perfil sin efectos externos y Redis; no se despliegan ramas desde QA. |
| Hotel de prueba | hotel autorizado en producción | usuarios QA autorizados | Datos sintéticos/reversibles; registrar la matriz en `qa/operational/runs/`; no usar otros hoteles. |
| Callbacks | pagos/email/WhatsApp/OTA | externo | Excluidos de ejecución QA; validar contrato/adapters. |

Las URLs antiguas `hoteles-pms.com` y proveedores `*.onrender.com` citados por documentación quedan `historical` salvo la URL de servicio observada por el verificador. El JSON reproducible está en `../_generated/cloud-surfaces.json`.
