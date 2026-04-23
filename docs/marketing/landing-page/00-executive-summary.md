# Executive Summary

## Diagnostico resumido

Hotel Chipre PMS ya tiene suficiente evidencia de producto para venderse como un PMS hotelero SaaS real para hoteles pequenos y medianos, con foco inicial en Argentina y operacion en espanol. La evidencia en codigo y docs respalda reservas, habitaciones, huespedes, check-in/check-out, pagos, onboarding guiado, planes, trial, integraciones OTA seleccionadas, reportes y una capa de asistente AI con guardrails.

La evidencia NO alcanza todavia para vender:

- pricing definitivo publico
- checkout real de compra online
- testimonios, logos, volumen de clientes o metricas comerciales
- ventajas del tipo "el mejor", "lider", "#1", "sin errores", "soporte premium" o SLA publico
- motor de reservas publico como claim central
- channel manager completo como claim principal sin validacion adicional

## Que conviene vender hoy

Conviene vender una promesa simple y demostrable:

- un sistema de gestion hotelera / PMS para centralizar la operacion diaria
- hecho para hoteles independientes, boutique y pequenos/medianos dentro del rango definido por producto
- con onboarding claro
- con trial de 14 dias
- con acceso web
- con integraciones concretas ya visibles en producto
- con enfoque en control, orden operativo y menos trabajo manual

## Que no conviene decir todavia

- "Compra ahora" con checkout real
- "Tarifas definitivas" si hoy el pricing sigue con datos mock/demo
- "Motor de reservas incluido" como pilar de home sin validacion funcional y comercial
- "Despegar incluido" como parte del lanzamiento sin confirmacion de owner
- "Soporte prioritario", "SLA 99.5%" o claims equivalentes tomados de datos mock
- cualquier claim de adopcion, crecimiento, ahorro de tiempo o ROI no medido

## Mensaje principal recomendado

"Sistema de gestion hotelera para centralizar reservas, habitaciones, huespedes y cobros en un solo lugar."

Version mas comercial pero todavia defendible:

"Un PMS hotelero para dejar atras planillas y operar tu hotel desde un solo sistema."

La segunda version debe tratarse como posicionamiento recomendado, no como claim cuantificado.

## Estructura recomendada

1. Home indexable en `https://hoteles-pms.com/`
2. Navegacion corta hacia `Funciones`, `Precios`, `FAQ` e `Ingresar`
3. Hero con CTA dual: `Registrarte` y `Ingresar`
4. Bloque de dolor -> solucion
5. Bloque "todo en un solo lugar" con evidencia funcional
6. Capturas del producto reales
7. Integraciones verificadas
8. Pricing con Starter / Pro / Ultra y tratamiento "coming soon" para compra
9. FAQ orientado a intencion de busqueda
10. CTA final y footer tecnico/comercial

## Riesgos principales

- A fecha 2026-04-22, `hoteles-pms.com` y `app.hoteles-pms.com` no resolvian por DNS desde este entorno.
- La pagina actual `frontend/src/views/public/PricingPage.tsx` sigue en modo beta/demo y hoy no es apta como landing publica final.
- El repo no tiene baseline SEO serio: sin sitemap, robots, canonical, schema ni metadata completa.
- Hay configuraciones sensibles versionadas que requieren rotacion y saneamiento antes de una salida publica.
- Hay decisiones de negocio todavia abiertas en `docs/product-definition.md`: precios, trial exacto, downgrade/upgrade y alcances finales de planes.

## Proximos pasos

1. Definir el mensaje madre y el set minimo de claims aprobables.
2. Separar marketing site de app operativa por dominio/subdominio y reglas de indexacion.
3. Reemplazar pricing demo por pricing comercial real o por version "lista de espera / hablar con ventas".
4. Implementar landing root-domain con metadata, schema y medicion desde el dia 1.
5. Completar QA SEO, funcional y responsive antes de abrir indexacion.
