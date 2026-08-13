# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

Este reporte documenta una campaña de QA **operativa, no certificante** ejecutada sobre los dominios
compartidos con etiqueta de producción (`app.hotels-pms.com`, `api.hotels-pms.com`, `hotels-pms.com`,
Supabase `ezkljznogqpmrjxyvklr`), usando identidades sintéticas creadas específicamente para esta
campaña. **No reemplaza el gate de release formal** (`qa/regression-catalog.json` + entorno de preview
aislado), que sigue pendiente de bootstrap ("needs-verification", ver `knowledge/40-delivery/release-gates.md`).

- Run ID: `shared-sandbox-campaign-20260812`
- Code SHA verificado: `8d88259d549ccfb17a961147fe658ab2ea841612` (main, post-merge del hardening RBAC/external-effects)
- Hoteles QA: `16` (Hotel QA Compartido) y `17` (Hotel QA Aislamiento)
- Personas ejecutadas: owner, co_owner, manager, reception, housekeeping (hotel 16), owner cross-tenant (hotel 17), anonymous
- Personas no ejecutadas: `isolation_owner` (identidad separada, no se obtuvo token propio — el owner de hotel 16 ya es miembro legítimo de hotel 17 y se usó para el chequeo de aislamiento), `master-admin` (autenticación por cookie, requiere PIN, fuera del patrón Bearer-token del resto de la campaña — no ejecutado en esta sesión)

## Resumen ejecutivo

De 52 observaciones registradas, **50 pasaron y 2 fallaron**, ambas atribuibles al mismo rol (`manager`)
y al mismo patrón de causa raíz: dos endpoints de reservas usan una lista de roles hardcodeada que
nunca incluyó `manager`. El resto de la superficie verificada — RBAC de los 5 roles de hotel,
aislamiento multi-tenant a nivel API, redaction financiera en reportes, fail-closed del runtime de IA
local, y las páginas públicas de marketing/login — se comportó exactamente como lo especifica la matriz
de roles del proyecto.

## Hallazgo prioritario (P1)

**Manager no puede listar reservas.** `GET /api/reservations/` devuelve `403 Forbidden` para el rol
`manager` porque [`app/api/reservations.py:264`](app/api/reservations.py#L264) usa
`require_roles("owner", "co_owner", "receptionist")`, sin incluir `manager`. Según la matriz de roles
del proyecto, manager tiene alcance operativo completo excluyendo solo cash/financiero/config —
consultar reservas es una función operativa central, no financiera. El frontend no expone el error:
como el hotel QA no tiene reservas cargadas, la UI muestra "0" en todos los contadores, un estado
indistinguible de "sin reservas" — un manager real no se enteraría de que está bloqueado.

**Bug relacionado (P2):** el mismo patrón bloquea `GET /api/reservations/actions/pending` (línea 288)
para manager. El widget "Bandeja operativa" del dashboard queda colgado indefinidamente en
"Cargando acciones pendientes..." sin mensaje de error, a diferencia de `subscription/status` que sí
tiene un fallback gracioso a un valor mock.

**Recomendación:** agregar `"manager"` a `require_roles(...)` en ambos endpoints (líneas 264 y 288 de
`app/api/reservations.py`). Es un fix de una línea por endpoint. No se aplicó en esta sesión por tratarse
de una campaña de QA, no de una sesión de desarrollo — queda a criterio del usuario decidir si se
corrige ahora o se registra como ticket separado.

## Verificaciones de seguridad confirmadas

- **RBAC por rol (5 personas × páginas core + Configuración):** matriz de permisos visible en
  `/settings/permissions` coincide exactamente con lo implementado — checkboxes de "Configurar hotel"
  y "Administrar permisos" solo marcados para owner/co-owner; housekeeping sin acceso a huéspedes.
- **Guardas de ruta en frontend:** manager/reception/housekeeping son redirigidos automáticamente a su
  landing correspondiente al intentar acceder a `/settings/users`, `/settings/permissions` o `/caja`
  fuera de su alcance — sin fuga de UI prohibida.
- **Redaction financiera en reportes:** `/reportes` no muestra montos a manager/reception/housekeeping;
  el banner de la propia UI lo declara explícitamente.
- **Aislamiento multi-tenant a nivel API (verificado con fetch directo, no solo UI):** un token de
  manager con `hotel_ids=[16]` que fuerza `X-Hotel-Id: 17` recibe `403 "No tenes acceso al hotel
  solicitado"`. Un owner que sí es miembro de ambos hoteles recibe `200` con datos vacíos y
  correctamente aislados de hotel 16.
- **Fail-closed del runtime de IA local:** `/settings/assistant` muestra "Runtime: Deshabilitado" en este
  entorno, consistente con la política de efectos externos.
- **Invitaciones:** las 4 identidades no-owner (co_owner, manager, reception, housekeeping) fueron
  creadas via el flujo real de invitación (`POST /api/users/invite` + `POST /api/invitations/{token}/accept`)
  y verificadas en `/settings/users` con el rol correcto.

## Cobertura ejecutada

| Área | Owner | Co-owner | Manager | Reception | Housekeeping |
|---|---|---|---|---|---|
| Dashboard, Reservas, Huéspedes, Habitaciones, Caja, Reportes | ✓ | parcial | ✓ | parcial | parcial |
| Waitlist, Lavandería, Stock, Tarifas, Planilla, Analytics | ✓ | — | — | — | Lavandería ✓ |
| Settings/* (permissions, api-keys, connections, security, hotel, subscription, whatsapp, assistant, tests, companies, users) | ✓ (11/11) | 2/11 | 2/11 (bloqueo) | 1/11 (bloqueo) | 1/11 (bloqueo) |
| Aislamiento multi-tenant (API directa) | ✓ | — | ✓ | — | — |
| Páginas públicas (marketing, login) | — | — | — | — | — (anonymous: 4 páginas) |

## Limitaciones de esta campaña (declaradas explícitamente, no ocultas)

1. **No hay evidencia binaria por caso.** El pipeline de `operational_qa.py validate` exige archivos de
   captura con sha256 registrados en `artifact-index.json`. Las capturas de esta sesión se tomaron y
   revisaron en vivo vía la extensión de navegador, pero no se localizó una ruta de archivo accesible
   por filesystem para persistirlas como artefactos verificables (`save_to_disk` no expuso una ruta
   resoluble). Por lo tanto `observations.json` de este run **no pasa** `operational_qa.py validate`
   estrictamente (falla por "requires operational evidence" en cada observación) — queda como bitácora
   de comportamiento, no como evidencia binaria certificable.
2. **No se cubrió la matriz completa de 346 combinaciones (45 casos × personas × 2 device profiles).**
   Se priorizó profundidad en el riesgo real (RBAC, aislamiento de tenant, redaction financiera) sobre
   cobertura mecánica exhaustiva de cada subruta para cada rol.
3. **Viewport móvil no verificado.** El tab de Chrome usado es el navegador real del usuario
   (`claude-in-chrome`), no un panel aislado — redimensionar la ventana a 390×844 afecta su ventana real
   de escritorio, no un viewport emulado. Se intentó y se revirtió de inmediato al confirmar que
   `window.innerWidth` no cambiaba de forma aislada. `ops-mobile-apple-critical` (4 rutas) no se ejecutó.
4. **`isolation_owner` sin sesión propia verificada**, `master-admin` no ejecutado (autenticación por
   cookie + PIN, fuera del patrón usado en el resto de la campaña).
5. **Analytics subrutas, room-state-events, warehouse-reconciliation, public-api-key-contract** no se
   probaron por rol más allá de la muestra tomada con owner.

## Datos creados

Únicamente registros sintéticos en hoteles 16 y 17 (marcados `"_qa_bootstrap"` en `extra_policies`),
sin reservas, huéspedes ni movimientos de caja reales creados durante la campaña (todas las páginas se
visitaron en modo lectura). Ninguna acción de escritura real (pago, email saliente, webhook de
proveedor) fue ejecutada — consistente con `external_exclusions` del run.

## Veredicto

**No apto como evidencia de release.** Sirve como confirmación operativa de que el hardening de RBAC y
aislamiento de tenant mergeado a `main` funciona correctamente en el entorno compartido, con una
excepción puntual y de bajo esfuerzo de corrección (manager bloqueado de reservas). Se recomienda:
(a) decidir sobre el fix P1/P2 de manager, (b) bootstrapear el gate de release formal documentado como
"needs-verification", antes de considerar cualquier release basado en evidencia de esta campaña.
