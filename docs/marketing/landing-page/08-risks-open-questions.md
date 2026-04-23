# Risks and Open Questions

## Riesgos criticos

### 1. Dominios no resolviendo

Hallazgo:

- El 2026-04-22, `hoteles-pms.com`, `app.hoteles-pms.com` y `app.hoteles-pms.com/login` no resolvian por DNS desde este entorno.

Impacto:

- bloqueo de salida publica
- bloqueo de Search Console
- bloqueo de validacion final

## 2. Pricing publico actual no confiable

Hallazgo:

- la pagina actual de pricing y los fallbacks contienen demo/mock/fake checkout

Impacto:

- riesgo comercial
- riesgo reputacional
- riesgo SEO si se indexa contenido equivocado

## 3. Secrets/config sensibles versionados

Hallazgo:

- hay archivos de entorno con valores sensibles presentes en el repo de trabajo

Impacto:

- riesgo severo de seguridad
- obliga a rotacion antes de lanzamiento

Nota:

- no se listan valores ni secretos en esta documentacion

## 4. Falta de baseline SEO

Hallazgo:

- sin sitemap, robots, canonical ni schema serios

Impacto:

- indexacion debil
- CTR bajo
- duplicacion potencial

## 5. Ambiguedades comerciales abiertas

Segun `docs/product-definition.md`, siguen abiertos:

- precios definitivos por plan
- trial exacto por tier
- post-trial behavior
- inclusion de Despegar
- reglas de upgrade/downgrade
- definicion final de algunas capacidades avanzadas

Impacto:

- imposibilidad de cerrar pricing/copy sin decision de negocio

## Claims no verificables hoy

Tratar explicitamente como NO aptos para home final:

- "lider"
- "#1"
- "mejor PMS"
- "mas ventas"
- "mas ingresos"
- "menos errores"
- "soporte prioritario" como promesa publica cerrada
- "SLA 99.5%"
- "motor de reservas" como capability central ya cerrada
- "channel manager completo"
- "checkout online ya disponible"
- testimonios o logos de clientes

## Hipotesis de posicionamiento validas pero no demostrables como dato

1. alternativa a Excel / planillas / gestion manual
2. menos friccion operativa
3. mas claridad para el hotel
4. sistema mas simple que trabajar con herramientas desconectadas

Estas ideas sirven como marco de mensaje, no como metricas ni garantias.

## Decisiones pendientes

1. El trial se asigna efectivamente a Starter, Pro o a un estado especial?
2. Se mostraran precios reales o se lanzara con waitlist/contacto?
3. La pagina de `Comprar` llevara a contacto, modal, waitlist o formulario?
4. Se publicara `Funciones` y `FAQ` en la primera salida o solo Home + Precios?
5. Se usara una sola app frontend o una capa marketing separada?
6. Se quiere indexar alguna pagina del subdominio app, o todo el valor SEO se concentrara en el dominio raiz?

## Tradeoffs

### Opcion A - salir rapido con Home + Precios + FAQ

Pros:

- mas velocidad
- menos costo

Contras:

- menor profundidad semantica

### Opcion B - salir con Home + money pages + metadata completa

Pros:

- mejor base SEO
- mejor estructura interna

Contras:

- mas trabajo inicial

Recomendacion:

- Opcion B, pero con scope controlado y sin blog en la primera tanda.

## Supuestos usados en este research

1. El producto se vende en espanol y Argentina first, por docs.
2. La futura home debe vivir en root domain, no en la app.
3. El CTA `Registrarte` puede usar el owner signup actual mientras no exista flujo mejor.
4. `Comprar` no debe prometer checkout real hasta que el flujo exista.
5. La landing debe vender categoria y claridad, no autoridad social inventada.
