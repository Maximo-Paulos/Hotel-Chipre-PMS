# Site Architecture and Wireframe

## Arbol recomendado

- `/`
- `/funciones`
- `/precios`
- `/pms-hotelero`
- `/software-para-hoteles`
- `/faq`

## Objetivo de la landing

1. explicar rapido que es
2. mostrar que resuelve
3. demostrar que el producto existe
4. reducir friccion con trial y acceso
5. llevar al usuario a:
   - `Ingresar`
   - `Registrarte`
   - `Comprar` -> coming soon / lista de espera / hablar con ventas

## Orden recomendado de secciones

1. Header / nav
2. Hero
3. Problema actual del hotel
4. Solucion: todo en un solo sistema
5. Capturas / producto real
6. Integraciones verificadas
7. Como funciona / onboarding
8. Beneficios por tipo de tarea
9. Pricing
10. Comparativa de planes
11. FAQ
12. CTA final
13. Footer

## Wireframe textual de alta fidelidad

### 1. Header / nav

Elementos:

- logo / wordmark
- links: Funciones, Precios, FAQ
- CTA texto: `Ingresar`
- CTA primario: `Registrarte`

Comportamiento:

- `Ingresar` -> `https://app.hoteles-pms.com/login`
- `Registrarte` -> `https://app.hoteles-pms.com/register-owner`
- sticky header en desktop
- nav simplificada en mobile

### 2. Hero

Objetivo:

- dejar clarisimo producto + audiencia + CTA

Layout:

- izquierda: H1 + subtitulo + CTA dual + microcopy
- derecha: screenshot real o mockup compuesto del producto

Contenido recomendado:

- H1 centrado en "sistema de gestion hotelera"
- subtitulo explicando reservas, habitaciones, huespedes y cobros
- CTA primario: `Registrarte`
- CTA secundario: `Ingresar`
- microcopy bajo CTA:
  - `Prueba 14 dias con Starter`
  - si la implementacion real da trial desde otra logica, ajustar el copy al comportamiento real

### 3. Problema actual

Objetivo:

- conectar con buyer que hoy trabaja disperso

Mensaje:

- reservas en varios lados
- control manual
- informacion fragmentada

Nota:

- comunicar como pain hypothesis basada en intencion de busqueda, no como estudio propio

### 4. Solucion: todo en un solo sistema

Objetivo:

- condensar el valor principal

Bloques:

- Reservas
- Habitaciones
- Huespedes
- Cobros
- Reportes

Cada bloque debe usar una frase respaldada por UI/codigo.

### 5. Producto real / screenshots

Objetivo:

- probar que existe software real

Que mostrar:

- dashboard
- reservas
- habitaciones
- conexiones/integraciones
- onboarding

No usar renders conceptuales si ya hay UI real.

### 6. Integraciones verificadas

Objetivo:

- aumentar confianza

Mostrar solo las verificadas:

- Booking
- Expedia
- Mercado Pago
- PayPal
- Gmail
- WhatsApp

Microcopy:

- "Integraciones visibles hoy en configuracion del producto"

### 7. Como funciona

Objetivo:

- bajar friccion de implementacion

Pasos:

1. Crea tu cuenta
2. Configura tu hotel con onboarding guiado
3. Empieza a operar desde una sola plataforma

Si se quiere incluir AI:

- usarlo como apoyo de setup/operacion, no como claim central

### 8. Beneficios por tarea

Objetivo:

- hablar en lenguaje de jobs

Tarjetas sugeridas:

- para recepcion
- para operacion diaria
- para control del hotel

Evitar frases vagas tipo "transforma tu negocio".

### 9. Pricing

Objetivo:

- capturar demanda transaccional

Orden:

- Starter
- Pro
- Ultra

Reglas:

- mostrar 14 dias trial en Starter si ese es el flujo real validado
- si precios definitivos no estan cerrados, usar:
  - "precio en definicion"
  - "coming soon"
  - "lista de espera"
  - "hablar con ventas"

No usar precios mock.

### 10. Comparativa de planes

Objetivo:

- resolver objeciones y facilitar decision

Columnas:

- Starter
- Pro
- Ultra

Filas solo con dimensiones respaldadas:

- alcance general
- room_limit
- staff_limit si se define
- trial
- Stripe si corresponde
- profundidad de reportes/AI si esta aprobada en docs de producto

Marcar lo abierto como decision pendiente, no como hecho.

### 11. FAQ

Objetivo:

- capturar long-tail y bajar objeciones

Preguntas:

- Que es Hotel Chipre PMS?
- Para que tipo de hoteles sirve?
- Que incluye la prueba?
- Como ingreso si ya tengo cuenta?
- Como compro si el checkout aun no esta habilitado?
- Que integraciones estan disponibles?
- Necesito instalar algo?

### 12. CTA final

Objetivo:

- cerrar con una accion

CTA principal:

- `Registrarte`

CTA secundaria:

- `Ingresar`

CTA terciaria opcional:

- `Quiero enterarme cuando se habilite la compra`

### 13. Footer

Contenido:

- logo
- links principales
- acceso a app/login
- legal/politicas cuando existan
- contacto comercial si aplica

## Ubicacion recomendada del pricing

- primera mencion breve en hero/microcopy
- seccion completa en la segunda mitad de la pagina
- repetir CTA a `Precios` desde header y mid-page

## Como manejar los CTAs

### Ingresar

- siempre visible
- header + hero + footer
- apuntar al login actual de la app

### Registrarte

- CTA primario de toda la pagina
- apuntar al flujo actual de owner signup
- reforzar el trial de 14 dias solo si el flujo lo confirma

### Comprar

Mientras no exista compra real:

- usar como CTA secundario de plan
- direccionarlo a:
  - lista de espera
  - contacto comercial
  - aviso de coming soon

Recomendacion:

- "Hablar con ventas" o "Quiero que me avisen"
- mejor que "Comprar" si aun no hay checkout real

## Sustituto de social proof si no hay logos/clientes

Como hoy no hay autoridad social verificable, usar:

- screenshots reales
- seccion "Que puedes hacer hoy con el sistema"
- integraciones visibles
- claridad tecnica
- trial

No inventar logos, clientes ni contadores.

## Como reducir rebote

1. H1 directo y categorico.
2. Screenshot visible arriba del fold.
3. CTA dual claro.
4. Evitar parrafos largos en hero.
5. Secciones cortas con progresion logica.
6. FAQ y pricing accesibles sin friccion.

## Como aumentar conversion

1. Trial visible.
2. Registro simple.
3. Pricing honesto.
4. Producto real visible.
5. Menos claims, mas demostracion.
