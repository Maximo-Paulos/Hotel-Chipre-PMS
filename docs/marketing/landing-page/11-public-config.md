# Configuración pública

Archivo de referencia para el comportamiento de URLs públicas, canonicalización e indexación.

## Variables esperadas

- `VITE_PUBLIC_SITE_URL`
- `VITE_PUBLIC_APP_URL`
- `VITE_PUBLIC_APP_HOSTNAME`
- `VITE_ALLOW_INDEXING`

## Valores recomendados

### Local

Usá este perfil cuando quieras desarrollar la app en local:

- `VITE_PUBLIC_SITE_URL=` vacío
- `VITE_PUBLIC_APP_URL=http://localhost:5173`
- `VITE_PUBLIC_APP_HOSTNAME=localhost`
- `VITE_ALLOW_INDEXING=false`

Notas:
- El sitio usa URLs relativas cuando `VITE_PUBLIC_SITE_URL` está vacío.
- `VITE_ALLOW_INDEXING=false` mantiene `noindex` en todas las páginas públicas.
- Si querés revisar la home marketing en un preview local, usá un build previo en un host que no coincida con `VITE_PUBLIC_APP_HOSTNAME`.

### Preview / staging

Usá la URL pública real del entorno de preview o staging:

- `VITE_PUBLIC_SITE_URL=https://<preview-site-url>`
- `VITE_PUBLIC_APP_URL=https://<preview-app-url>`
- `VITE_PUBLIC_APP_HOSTNAME=<preview-app-hostname>`
- `VITE_ALLOW_INDEXING=false`

Notas:
- Mantené `noindex` hasta producción.
- `VITE_PUBLIC_APP_HOSTNAME` debe coincidir con el host que sirve la app para que el router separe marketing y producto.

### Producción

Valores finales esperados:

- `VITE_PUBLIC_SITE_URL=https://hoteles-pms.com`
- `VITE_PUBLIC_APP_URL=https://app.hoteles-pms.com`
- `VITE_PUBLIC_APP_HOSTNAME=app.hoteles-pms.com`
- `VITE_ALLOW_INDEXING=true`

Notas:
- `VITE_ALLOW_INDEXING=true` habilita la indexación del root marketing.
- La app y las rutas de auth deben seguir en `noindex`.
