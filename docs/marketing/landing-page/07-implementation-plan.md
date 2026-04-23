# Implementation Plan

## Objetivo del plan

Dejar un blueprint ejecutable por Codex, sin reinterpretacion amplia, para construir la landing principal en `https://hoteles-pms.com`.

## Milestone 0 - Alineacion de negocio y claims

### Objetivo

Cerrar que se puede prometer publicamente.

### Tareas

1. aprobar mensaje principal
2. aprobar claims respaldados por evidencia
3. definir copy permitido para trial
4. definir tratamiento comercial de `Comprar`
5. cerrar si `/precios` tendra precios reales o modo waitlist/contacto

### Dependencias

- owner / producto
- `docs/product-definition.md`

### Riesgos

- seguir construyendo sobre pricing/demo mock

### Criterio de aceptacion

- lista cerrada de claims aprobados
- definicion de CTA comercial para planes pagos

## Milestone 1 - Preparacion de contenido y assets

### Objetivo

Reunir todo lo necesario antes de tocar codigo.

### Tareas

1. capturar screenshots reales del producto:
   - dashboard
   - reservas
   - habitaciones
   - onboarding
   - conexiones
2. definir logos y assets de marca validos
3. redactar copy final inicial de home, precios, funciones y FAQ
4. preparar matriz de metadata por pagina

### Archivos probables a tocar

- nuevos assets en `frontend/src/assets/` o carpeta marketing dedicada
- docs de copy internas

### Riesgos

- usar capturas desactualizadas o funcionalidad no estable

### Aceptacion

- screenshots aprobados
- copy base aprobado

## Milestone 2 - Definicion de rutas y arquitectura

### Objetivo

Separar correctamente marketing y app.

### Tareas

1. decidir si el marketing se monta:
   - dentro del mismo frontend con rutas publicas nuevas, o
   - como app separada
2. crear mapa final de rutas indexables
3. definir reglas de noindex para auth/app
4. definir canonical por dominio

### Recomendacion

Mantener una sola codebase frontend si acelera, pero con separacion fuerte entre:

- marketing routes en root domain
- app routes en subdominio

### Archivos probables a tocar

- `frontend/src/router.tsx`
- `vercel.json`
- config de dominio/deploy

### Riesgos

- colision de SPA routing con SEO
- duplicacion de contenido entre root y app

### Aceptacion

- documento tecnico de rutas aprobado

## Milestone 3 - Implementacion del landing root domain

### Objetivo

Construir `https://hoteles-pms.com/` como home indexable.

### Tareas

1. crear layout marketing
2. crear pagina home
3. implementar header, hero, secciones de valor, screenshots, integraciones, CTA final y footer
4. enlazar `Ingresar` a login actual de app
5. enlazar `Registrarte` a registro owner actual

### Archivos probables a tocar

- `frontend/src/...` nuevos componentes/pages de marketing
- `frontend/index.html`
- posibles hojas de estilo / assets

### Riesgos

- querer reutilizar demasiado codigo de app y arrastrar complejidad

### Validaciones

- render correcto desktop/mobile
- links correctos
- contenido visible sin dependencia innecesaria de datos runtime

### Aceptacion

- home navegable y alineada al wireframe

## Milestone 4 - Reutilizacion o reemplazo de pricing actual

### Objetivo

Quitar el pricing demo y dejar pricing comercial seguro.

### Tareas

1. auditar datos que hoy vienen de API vs mock
2. remover todo lenguaje beta/demo/fake checkout
3. crear pagina `precios` con Starter/Pro/Ultra
4. definir CTA por plan:
   - Starter -> trial / registro
   - Pro/Ultra -> waitlist / contacto / coming soon

### Archivos probables a tocar

- `frontend/src/views/public/PricingPage.tsx` o reemplazo
- `frontend/src/hooks/useSubscription.ts`
- componentes de pricing nuevos

### Riesgos

- exponer pricing invalido o claims mock

### Aceptacion

- ningun precio/claim mock en produccion

## Milestone 5 - Paginas satelite SEO

### Objetivo

Construir profundidad semantica minima.

### Tareas

1. crear `/funciones`
2. crear `/pms-hotelero`
3. crear `/software-para-hoteles`
4. crear `/faq`
5. conectar linking interno

### Riesgos

- thin content
- paginas duplicadas semanticas

### Aceptacion

- cada pagina con intencion clara, metadata unica y CTA definido

## Milestone 6 - Metadata y SEO tecnico

### Objetivo

Corregir baseline SEO.

### Tareas

1. actualizar `lang="es"`
2. definir title/meta por pagina
3. agregar canonical
4. agregar OG/Twitter cards
5. definir site name
6. preparar 404 y estados correctos donde aplique

### Archivos probables a tocar

- `frontend/index.html`
- componentes/head manager segun stack elegido

### Riesgos

- metadata generica por SPA

### Aceptacion

- metadata unica y consistente en todas las URLs indexables

## Milestone 7 - Structured data

### Objetivo

Agregar solo schema legitimo.

### Tareas

1. `WebSite` en home
2. `Organization` si datos empresariales reales estan listos
3. `BreadcrumbList` en paginas internas
4. `FAQPage` si el FAQ visible queda publicado

### Riesgos

- markup no representativo

### Aceptacion

- Rich Results Test sin errores importantes

## Milestone 8 - Performance / Core Web Vitals

### Objetivo

Lanzar con base tecnica sana.

### Tareas

1. optimizar hero media
2. minimizar JS innecesario en landing
3. lazy-load de assets no criticos
4. asegurar estabilidad visual
5. revisar Lighthouse y Web Vitals

### Riesgos

- landing pesada por screenshots
- CLS por imagenes sin dimensiones

### Aceptacion

- objetivo de LCP/INP/CLS razonable cumplido o con plan correctivo concreto

## Milestone 9 - Search Console / robots / sitemap / canonical

### Objetivo

Dejar la infraestructura de indexacion lista.

### Tareas

1. crear `robots.txt`
2. crear sitemap
3. declarar sitemap en robots
4. verificar dominio en Search Console
5. subir sitemap
6. revisar cobertura e inspeccion URL

### Riesgos

- indexar auth/app
- sitemap con URLs no canonicas

### Aceptacion

- sitemap accesible
- robots accesible
- Search Console verificado

## Milestone 10 - Analytics y medicion

### Objetivo

Poder medir impacto desde day 1.

### Tareas

1. instalar analytics si aun no existe para marketing
2. definir eventos de CTA
3. definir conversiones:
   - click registro
   - inicio registro
   - completion registro
   - click login
   - click waitlist/contact
4. documentar dashboard inicial

### Riesgos

- no poder saber si la landing funciona

### Aceptacion

- eventos validados en entorno productivo

## Milestone 11 - QA funcional + QA SEO + QA responsive

### Objetivo

No salir con errores obvios.

### Tareas

1. links y CTAs
2. mobile y desktop
3. metadata por pagina
4. schema
5. robots/sitemap/canonical
6. screenshots cargando bien
7. formularios y flows correctos
8. revisar noindex en auth/app

### Aceptacion

- checklist pre-launch completo

## Milestone 12 - Deploy y post-launch

### Objetivo

Publicar y medir.

### Tareas

1. configurar `hoteles-pms.com`
2. configurar `app.hoteles-pms.com`
3. validar DNS/SSL
4. desplegar
5. hacer smoke test
6. enviar sitemap
7. monitorear primeras 2-4 semanas

### Riesgos

- dominios hoy no resuelven
- canonical cruzadas incorrectas

### Aceptacion

- sitio accesible, indexable y medible

## Backlog priorizado por complejidad

### Alta prioridad / baja ambiguedad

1. separar marketing y app
2. corregir metadata base
3. crear home indexable
4. corregir pricing demo
5. robots/sitemap/canonical

### Alta prioridad / alta ambiguedad

1. pricing final
2. tratamiento de compra
3. alcance comercial del trial

### Prioridad media

1. paginas satelite
2. FAQ SEO
3. schema
4. analytics avanzado

## Checklist tecnico de aceptacion

- rutas de marketing funcionando
- CTA `Ingresar` y `Registrarte` correctos
- app/auth en noindex
- title/meta/canonical por pagina
- sitemap y robots publicados
- home no redirige al dashboard
- sin copy demo/mock
- sin secretos expuestos en frontend

## Estimacion relativa

- M0: M
- M1: M
- M2: M
- M3: L
- M4: M
- M5: M
- M6: M
- M7: S
- M8: M
- M9: S
- M10: S/M
- M11: M
- M12: M
