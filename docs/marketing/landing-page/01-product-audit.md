# Product Audit

## Alcance de la auditoria

Se revisaron docs, backend, frontend, rutas publicas/protegidas, configuracion de despliegue, metadata actual y assets del repo. Tambien se uso `graphify-out/GRAPH_REPORT.md` como punto de entrada arquitectonico, segun `AGENTS.md`.

## Arquitectura general verificada

- Backend: FastAPI (`app/main.py`)
- Frontend: React 18 + TypeScript + Vite + React Router + TanStack Query (`frontend/package.json`)
- Base de despliegue actual:
  - Render para backend (`render.yaml`)
  - Vercel para frontend (`vercel.json`)
- Modo actual del frontend: SPA con rewrite global a `index.html`

## Evidencia de posicionamiento de producto

### Claim verificable: PMS hotelero SaaS multi-tenant

Evidencia:

- `docs/product-definition.md`: "multi-tenant SaaS Property Management System for hotels"
- `app/main.py`: titulo y descripcion del API
- `app/dependencies/auth.py`: aislamiento por `hotel_id`
- `tests/test_multi_hotel_api.py`
- `tests/test_multi_hotel_isolation_contracts.py`

Confianza: alta

### Claim verificable: cubre operacion hotelera base

Evidencia:

- Reservas: `app/api/reservations.py`, `frontend/src/views/protected/ReservationsPage.tsx`
- Huespedes: `app/api/guests.py`, `frontend/src/views/protected/GuestsPage.tsx`
- Habitaciones: `app/api/rooms.py`, `frontend/src/views/protected/RoomsPage.tsx`
- Check-in/check-out: `app/api/checkin.py`
- Pagos: `app/api/payments.py`, `app/services/payment_service.py`
- Reportes: `app/api/reports.py`

Confianza: alta

### Claim verificable: onboarding estructurado

Evidencia:

- `app/api/onboarding.py`
- `app/services/onboarding_service.py`
- `frontend/src/views/onboarding/OnboardingWizard.tsx`
- tests: `tests/test_onboarding_flow.py`, `tests/test_onboarding_gates.py`, `tests/test_onboarding_wizard.py`

Confianza: alta

### Claim verificable: planes Starter / Pro / Ultra

Evidencia:

- `docs/product-definition.md`
- `app/models/subscription_v2.py`
- `app/services/hotel_service.py`
- `app/api/subscription.py`
- `frontend/src/hooks/useSubscription.ts`
- `frontend/src/views/public/PricingPage.tsx`

Confianza: alta para existencia; baja/media para pricing publico final

### Claim verificable: trial de 14 dias

Evidencia:

- `docs/product-definition.md`
- `app/api/subscription.py`
- `app/schemas/onboarding.py`

Confianza: alta para existencia del trial; media para copy exacto del flujo comercial final

## ICP respaldado por producto

Segun `docs/product-definition.md`, el producto se orienta al lanzamiento a:

- Argentina primero
- espanol
- hoteles independientes
- boutique hotels
- apart-hotels
- hoteles pequenos y medianos
- rango admitido 1-80 habitaciones

Confianza: alta

## Flujos publicos existentes

- Login: `frontend/src/views/public/LoginPage.tsx`
- Registro owner: `frontend/src/views/public/RegisterOwnerPage.tsx`
- Recupero: `frontend/src/views/public/ForgotPasswordPage.tsx`
- Reset password: `frontend/src/views/public/ResetPasswordPage.tsx`
- Verificacion de email: `frontend/src/views/public/VerifyEmailPage.tsx`
- Pricing publico actual: `frontend/src/views/public/PricingPage.tsx`

Observacion clave:

- La ruta raiz `/` hoy redirige a `/dashboard` (`frontend/src/router.tsx`).
- Esto confirma que la app actual no esta pensada como marketing home.

## Flujos de onboarding y activacion

Pasos visibles y/o documentados:

- owner
- identity
- categories
- rooms
- policy
- payments
- ota
- subscription
- staff
- finish

Evidencia:

- `app/schemas/onboarding.py`
- `app/api/onboarding.py`
- `frontend/src/views/onboarding/OnboardingWizard.tsx`

Valor vendible hoy:

- "configuracion guiada"
- "puesta en marcha paso a paso"
- "alta del hotel desde un flujo ordenado"

No vender todavia:

- "implementacion en minutos" sin medicion
- "onboarding automatico" sin matiz

## Integraciones verificadas

Evidencia fuerte en backend/frontend/config:

- Booking
- Expedia
- Mercado Pago
- PayPal
- Gmail
- WhatsApp
- Stripe (solo en determinadas reglas de plan/onboarding)

Paths:

- `app/config.py`
- `app/api/integrations.py`
- `frontend/src/views/protected/SettingsConnectionsPage.tsx`
- `docs/product-definition.md`

Matices importantes:

- Despegar existe como adapter en codigo (`app/services/ota/adapters/despegar.py`) pero sigue con decision abierta de lanzamiento en docs.
- No usar Despegar como claim principal hoy.
- No vender "channel manager completo" como claim central sin auditar toda la cobertura funcional de distribucion outbound.

## AI / asistente

Evidencia:

- `app/api/gemma_chat.py`
- `frontend/src/views/protected/SettingsAssistantPage.tsx`
- `docs/product-definition.md`
- `tests/test_gemma_chat_api.py`

Lo demostrable:

- existe un asistente
- usa flujo draft/review/apply
- no opera de forma autonoma sobre datos criticos

Como comunicarlo sin exagerar:

- "asistente AI con control humano"
- "sugerencias revisables"
- "ayuda operativa y de configuracion"

No comunicar todavia:

- "optimiza tus ingresos"
- "aprende solo"
- "automatiza todo"

## Reportes y control operativo

Evidencia:

- `app/api/reports.py`
- dashboard en `frontend/src/views/protected/DashboardPage.tsx`

Lo vendible:

- reportes diarios
- ocupacion
- revenue
- visibilidad operativa

## Seguridad y confianza

Evidencia:

- `app/dependencies/auth.py`
- `app/config.py`
- `tests/test_auth_security.py`
- `tests/test_runtime_security.py`
- `tests/test_rate_limiting.py`

Mensajes posibles:

- "aislamiento por hotel"
- "sesion y permisos validados"
- "configuracion sensible por entorno"

No convertir esto en claims grandilocuentes del tipo "seguridad enterprise" sin auditoria externa.

## Pricing actual y limitaciones

La pagina de pricing actual sirve solo como base visual inicial, no como base comercial final.

Problemas detectados en `frontend/src/views/public/PricingPage.tsx` y `frontend/src/hooks/useSubscription.ts`:

- copy explicito de beta/demo
- checkout falso
- precios mock
- badge "Gratis" en Starter mock
- claim "SLA 99.5%" en fallback mock
- algunas descripciones no estan aprobadas por docs de producto

Conclusion:

- reutilizable como inspiracion visual y de layout
- NO reutilizable como copy/comercial final sin reescritura fuerte

## SEO y metadata actuales

`frontend/index.html` hoy tiene baseline muy debil:

- titulo generico
- sin meta description util
- sin canonical
- sin robots
- sin structured data
- OG/Twitter minimo
- `lang="en"` aunque el producto y mercado inicial son en espanol

Ademas:

- no se encontro `robots.txt`
- no se encontro `sitemap.xml`
- no se encontro schema JSON-LD

## Dominios y despliegue

Evidencia repo:

- frontend pensado hoy para Vercel
- backend para Render
- configuraciones apuntan a `hotel-chipre.vercel.app`

Hallazgo operativo:

- En verificacion hecha el 2026-04-22 desde este entorno, `https://hoteles-pms.com`, `https://app.hoteles-pms.com` y `https://app.hoteles-pms.com/login` no resolvian por DNS.

Esto es bloqueo real para lanzamiento.

## Assets disponibles

Utiles para landing:

- UI real del pricing actual
- UI real del dashboard
- UI real de reservas, habitaciones, conexiones, subscription y assistant
- logos/favicons existentes

Faltan todavia:

- casos de exito verificados
- logos de clientes con permiso
- screenshots marketing preparados
- comparativas comerciales aprobadas

## Fortalezas vendibles hoy

1. producto real, no simple mock de brochure
2. foco claro en operacion hotelera
3. onboarding definido
4. planes y trial ya modelados
5. integraciones verificadas
6. reportes operativos basicos presentes
7. modelo multi-tenant con aislamiento
8. asistente AI con guardrails en vez de automatizacion opaca
9. stack web moderno y deploy cloud
10. app ya navegable con flujos de auth y paneles

## Gaps importantes

1. pricing comercial final sin definir
2. checkout real no implementado para compra publica
3. metadata/SEO casi inexistente
4. home marketing inexistente en root
5. root de la SPA redirige al dashboard
6. falta separar bien lo indexable de lo no indexable
7. faltan pruebas sociales verificables
8. faltan decisiones cerradas sobre claims de planes
9. secretos/config sensible versionados
10. dominios publicos no resuelven hoy
