# SEO Strategy

## Principios de base

La estrategia se apoya en documentacion oficial de Google Search Central:

- Search Essentials
- SEO Starter Guide
- Creating helpful, reliable, people-first content
- JavaScript SEO basics
- canonical, sitemap, robots, snippets, site name, Search Console y structured data guidelines

La meta no es "salir #1", sino maximizar:

- relevancia semantica
- rastreabilidad e indexabilidad
- claridad de intencion
- CTR organico
- experiencia de pagina
- conversion post-click

## Decision principal de arquitectura SEO

### Recomendacion

`https://hoteles-pms.com/` debe ser la landing principal indexable.

### Justificacion

1. El dominio raiz es el activo de marca y SEO.
2. La app vive en un subdominio y contiene areas que no conviene indexar masivamente.
3. Separar marketing y aplicacion reduce conflictos entre rutas privadas, metadata y objetivos.
4. La home actual de la app redirige al dashboard; no sirve como home comercial indexable.

## Arquitectura recomendada de URLs

### Fase inicial minima

- `/` -> home principal
- `/precios`
- `/funciones`
- `/pms-hotelero`
- `/software-para-hoteles`
- `/faq`

### Fase 2 recomendada

- `/gestion-hotelera`
- `/hotel-boutique`
- `/hotel-pequeno`
- blog / recursos

### NO recomendar todavia como pagina transaccional primaria

- `/motor-de-reservas`
- `/channel-manager-hotel`

Solo crear estas URLs cuando haya contenido visible y posicionamiento sustentable. Si se crean antes, deben tratarse como:

- hipotesis de posicionamiento
- contenido educativo, no promesa de feature central

## Keyword map

### Keywords primarias

- pms hotelero
- software para hoteles
- sistema de gestion hotelera
- software hotelero

### Keywords secundarias

- administrar hotel
- programa para hotel
- gestion hotelera
- software para hotel pequeno
- software para hotel boutique
- pms para hoteles independientes

### Keywords de apoyo / contenido futuro

- reservas hoteleras
- check in hotel
- software de recepcion hotelera
- como administrar un hotel
- alternativa a Excel para hotel
- integracion booking hotel
- integracion expedia hotel

## Keyword-to-page map

| URL | Keyword principal | Keywords secundarias | Objetivo |
|---|---|---|---|
| `/` | software para hoteles | sistema de gestion hotelera, software hotelero | categoria + conversion |
| `/pms-hotelero` | pms hotelero | pms para hoteles independientes | capturar buyer tecnico/comercial |
| `/software-para-hoteles` | software para hoteles | programa para hotel, administrar hotel | capturar demanda amplia |
| `/funciones` | funciones software hotelero | reservas, habitaciones, pagos, reportes | profundidad producto |
| `/precios` | precios software hotelero | planes pms hotelero, trial 14 dias | conversion |
| `/faq` | faq software hotelero | dudas de trial, implementacion, login | objeciones y snippets |

## Keyword-to-section map para home

| Seccion | Intencion / keyword |
|---|---|
| Hero | software para hoteles / sistema de gestion hotelera |
| Problema | administrar hotel / gestion manual |
| Todo en uno | pms hotelero |
| Funciones principales | reservas hoteleras / habitaciones / cobros |
| Integraciones | booking / expedia / pagos |
| Pricing | precios software hotelero / trial |
| FAQ | dudas de compra y uso |

## Metadata recomendada

### Home

Title ideal:

`Software para hoteles | PMS hotelero para centralizar tu operacion`

Meta description ideal:

`Sistema de gestion hotelera para centralizar reservas, habitaciones, huespedes y cobros en un solo lugar. Prueba 14 dias con el plan Starter.`

H1 ideal:

`Sistema de gestion hotelera para operar tu hotel desde un solo lugar`

### `/precios`

Title:

`Precios de Hotel Chipre PMS | Planes Starter, Pro y Ultra`

Meta description:

`Conoce los planes Starter, Pro y Ultra de Hotel Chipre PMS. Prueba 14 dias y elige la opcion que mejor encaje con tu hotel.`

### `/funciones`

Title:

`Funciones de Hotel Chipre PMS | Reservas, habitaciones, pagos y reportes`

Meta description:

`Explora las funciones principales del PMS: reservas, habitaciones, huespedes, cobros, onboarding e integraciones disponibles.`

## Estructura recomendada de headings para home

- H1: Sistema de gestion hotelera para operar tu hotel desde un solo lugar
- H2: Que puedes centralizar con el sistema
- H2: Como funciona en la operacion diaria
- H2: Integraciones disponibles hoy
- H2: Planes para distintas etapas del hotel
- H2: Preguntas frecuentes
- H2: Empieza con tu prueba

## Internal linking strategy

1. Desde home enlazar a `Funciones`, `Precios` y `FAQ` en header, hero y footer.
2. Desde `Funciones` enlazar a `Precios` y `Registrarte`.
3. Desde `Precios` enlazar a `Funciones`, `FAQ` y `Registrarte`.
4. Desde `FAQ` enlazar a `Precios`, `Funciones`, `Ingresar` y `Registrarte`.
5. Si se crea blog, cada articulo debe enlazar a una pagina money y a la home.

## Root domain vs app subdomain

### Recomendacion

- `hoteles-pms.com`: marketing, indexable
- `app.hoteles-pms.com`: producto, login, onboarding, settings, dashboard

### Politica recomendada

- Marketing pages: indexables
- Auth/app routes: noindex
- Login y registro pueden ser accesibles, pero no deben competir organicamente como landings SEO

## Canonical strategy

1. Cada URL indexable del root domain debe apuntar canonical a si misma.
2. Evitar duplicados entre root y subdominio app.
3. Si `/pricing` sigue existiendo temporalmente en app, decidir una de dos:
   - canonical a `https://hoteles-pms.com/precios` y noindex en app
   - o retirar el valor SEO de la app page por completo

Recomendacion: mover el valor SEO/comercial a root y dejar la app sin aspiracion organica.

## Indexation strategy

### Indexar

- `/`
- `/precios`
- `/funciones`
- `/pms-hotelero`
- `/software-para-hoteles`
- `/faq`
- recursos/blog futuros de valor real

### No indexar

- `/login`
- `/register-owner`
- `/forgot-password`
- `/reset-password`
- `/verify-email`
- `/dashboard`
- `/settings/*`
- `/onboarding/*`
- rutas privadas y paneles

## Robots strategy

Root domain:

- permitir crawling de marketing pages
- declarar sitemap

App subdomain:

- permitir crawling tecnico si hace falta
- aplicar `noindex` a auth y app pages a nivel meta/headers
- no bloquear por robots recursos necesarios para render

## Sitemap strategy

1. sitemap en root con todas las URLs indexables.
2. si luego hay blog, usar sitemap index.
3. incluir solo canonicals indexables.
4. enviar sitemap en Search Console.

## Structured data recomendada

### Recomendado

- `WebSite` en home para site name
- `Organization` si se completan datos reales de la empresa
- `BreadcrumbList` en paginas internas
- `FAQPage` solo si el FAQ es visible en la pagina

### No recomendado por ahora

- `Review`, `AggregateRating`, estrellas o ratings
- `Product` con precios falsos o incompletos
- markup que no represente exactamente el contenido visible

## FAQs recomendadas por intencion SEO

1. Que es un PMS hotelero?
2. Para que tipo de hoteles sirve Hotel Chipre PMS?
3. Que incluye la prueba de 14 dias?
4. Necesito instalar algo?
5. Puedo ingresar con mi cuenta actual?
6. Como funcionan los planes Starter, Pro y Ultra?
7. Que pasa si todavia no quiero comprar?
8. Que integraciones estan disponibles hoy?

## JS SEO y performance

Como el frontend es Vite SPA, hay riesgo de depender demasiado de JS para contenido critico. Segun Google, JS puede indexarse, pero conviene no dejar metadata y contenido clave dependientes exclusivamente del cliente.

Recomendacion fuerte:

- marketing landing con HTML/meta predecible
- metadata por ruta
- contenido principal visible en el DOM sin esperas innecesarias
- status codes correctos
- no soft-404

## Core Web Vitals

Objetivos:

- LCP <= 2.5s
- INP <= 200ms
- CLS <= 0.1

Riesgos actuales probables:

- SPA con hero pesado si se abusa de imagenes
- metadata y route handling poco especializados
- potencial overfetch si se reutiliza demasiado codigo de app

## Search Console y analytics

### Search Console

Crear propiedades para:

- `https://hoteles-pms.com/`
- opcional: `https://app.hoteles-pms.com/`

Monitorear:

- impresiones
- clicks
- CTR
- queries no brand
- pages indexadas
- Core Web Vitals
- coverage

### Analytics

Eventos minimos:

- click_ingresar
- click_registrarte
- click_comprar
- click_lista_espera
- click_contacto_comercial
- scroll_50
- scroll_90
- view_pricing
- select_plan_starter
- select_plan_pro
- select_plan_ultra

## Blog futuro

Conviene, pero no antes de cerrar la home y las money pages.

Clusters recomendados:

1. PMS hotelero
2. gestion hotelera
3. operacion hotelera
4. reservas y check-in
5. alternativas a planillas
6. integraciones OTA/pagos (solo si el producto lo soporta bien)
