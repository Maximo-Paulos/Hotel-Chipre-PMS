# TECH-0000 — Consolidación de autorización role-based a permission-based

Estado: `IN_PROGRESS` — código migrado de forma conservadora, pero la validación dinámica está bloqueada por el entorno local.

SHA inspeccionado: `8a53fc309758735bf08b2cbe5d3dadfb6e2dd4ea`.

## Inventario

El grep exhaustivo encontró 72 dependencias de ruta con `require_roles` en 14 módulos de API. Se migraron 21 rutas. Quedan 51 rutas ambiguas sin tocar. `require_roles` permanece activo y no se marca deprecado porque todavía tiene consumidores de producción dentro del repo.

La equivalencia se calculó contra la matriz default de `permission_service.py` después de canonicalizar aliases. No se inventaron permisos nuevos.

## Rutas migradas

| Ruta | `require_roles` anterior | Permiso nuevo | Equivalencia de roles default |
|---|---|---|---|
| `GET /api/bookings/price-quote` | `owner, co_owner, manager, receptionist` | `reservation:create` | exactamente los cuatro roles |
| `GET /api/onboarding/status` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/owner` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/identity` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/categories` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/rooms` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/policy` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/payments` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/ota` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/subscription-choice` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/staff` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/onboarding/finish` | `owner, co_owner` | `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/versions` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/versions/{version_id}/publish` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/suggestions` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/suggestions/{suggestion_id}/review` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/suggestions/{suggestion_id}/apply` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/questionnaire-draft` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/allocation/policy/feedback-draft` | `owner, co_owner` | alias `config:manage` → `hotel_settings:update` | exactamente owner/co_owner |
| `POST /api/movement-groups/{group_id}/revert` | `owner, co_owner, manager` | `reservation:move` | exactamente esos tres roles en defaults |
| `POST /api/users/{user_id}/primary-owner` | `owner` | `hotel_settings:property_manage` | owner-only; invariant no delegable |

La prueba de no-regresión parametrizada está en `tests/test_rbac_permission_consolidation.py`. Para cada función migrada verifica que ya no contiene `require_roles`, que usa el permiso esperado y que la matriz default produce exactamente el conjunto legacy permitido/denegado.

## Casos ambiguos no migrados

Se dejan sin tocar porque no hay un permiso semánticamente equivalente con el mismo conjunto default de roles, o porque el candidato existente es más laxo/estricto:

| Módulo y rutas | Roles legacy | Motivo |
|---|---|---|
| `bookings`: `/availability`, `/`, `/{booking_id}`, `/{booking_id}/cancel`, `/{booking_id}/checkin`, `/{booking_id}/checkout`, `PATCH /{booking_id}`, `/demo-seed`, `DELETE /{booking_id}` | `owner, co_owner, manager` | Los permisos naturales de reservas (`read`, `create`, `update`, `cancel`, `checkin`, `checkout`) también habilitan receptionist en la matriz default. No se sustituyó por un permiso semánticamente incorrecto sólo para igualar roles. |
| `commercial`: create/patch de products, rate-plans, tax-policies y fx-policies | `owner, co_owner` | El módulo sólo tiene `reports:financial:view` para lecturas; reutilizarlo para mutaciones comerciales sería una autoridad semántica incorrecta. No existe `commercial:manage`. |
| `gemma_chat`: approve, reject, review-draft y apply-draft de acciones | `owner, co_owner` | No existe permiso catalogado para aprobar/aplicar acciones de IA; `reports:financial:view` no es equivalente. |
| `notifications`: GET/PUT `/daily-report-schedule` | `owner, co_owner` | No existe permiso de scheduling/reportes con exactamente ese alcance; `reports:operational:view` también habilita manager. |
| `payment_link_tests`: list/create/refresh/cancel MercadoPago | `owner, co_owner` | No existe permiso específico de payment-link tests con el mismo conjunto; se evita tocar esta superficie de pagos. |
| `permissions`: restore role override, restore user override, pending/approve/deny temporary grants | `owner, co_owner` | `permissions:manage` es owner-only en la matriz; migrarlo quitaría acceso a co_owner. |
| `settings_security`: overview, events, audit-timeline, export y revoke-all | `owner, co_owner` | `hotel_settings:security_manage` es owner-only; usar `hotel_settings:update` mezclaría seguridad con configuración y permitiría una capacidad distinta. |
| `subscription`: status, plans, plan, trial, entitlements y overrides | `owner, co_owner` | El catálogo actual no tiene permiso de suscripción equivalente. |
| `users`: list, invite, resend/revoke invitation, revoke user y update role | `owner, co_owner` | No hay permiso canónico de staff-management con exactamente ambos roles; `permissions:manage` es más estricto. |

Estas 51 rutas conservan deliberadamente `require_roles`. No se modifica `app/api/payments.py`, `app/api/reservations.py` ni otras rutas de pagos/caja con patrones distintos.

## Validación

Comprobaciones estáticas realizadas:

- `python3` con `PYTHONPYCACHEPREFIX=/private/tmp/hcp-pycache` compiló correctamente los cinco módulos API modificados y el nuevo test.
- `git diff --check` no reportó errores.
- El grep final confirmó 51 usos de ruta restantes de `require_roles` y 21 rutas migradas.

Pruebas focales y completas intentadas por tanda:

| Tanda | Comando focal | Comando completo | Resultado exacto |
|---|---|---|---|
| bookings | `.venv/bin/python -m pytest -q tests/test_api_scaffolding.py tests/test_guest_restriction_api.py` | no se ejecutó por el bloqueo del entorno antes de separar la tanda siguiente | focal: `.venv/bin/python: No module named pytest` |
| onboarding | `.venv/bin/python -m pytest -q tests/test_onboarding_flow.py tests/smoke/test_api_smoke.py` | `.venv/bin/python -m pytest -q` | ambos: `.venv/bin/python: No module named pytest` |
| allocation | `.venv/bin/python -m pytest -q tests/test_allocation_policy_api.py tests/test_allocation_product_compatibility.py` | `.venv/bin/python -m pytest -q` | ambos: `.venv/bin/python: No module named pytest` |
| movement groups | `.venv/bin/python -m pytest -q tests/test_room_movement_groups_api.py tests/test_v72_movement_groups.py` | `.venv/bin/python -m pytest -q` | ambos: `.venv/bin/python: No module named pytest` |
| users | `.venv/bin/python -m pytest -q tests/test_invitations.py` | `.venv/bin/python -m pytest -q` | ambos: `.venv/bin/python: No module named pytest` |

Se intentó preparar `.venv` con `uv`; la instalación de `requirements.txt` no pudo resolver `https://pypi.org/simple/cassandra-driver/` por fallo DNS tras tres reintentos. Por eso no hay un resultado válido de `pytest` ni puede declararse el criterio de aceptación de 0 fallos.

## Estado y siguiente paso

Estado de certeza: `needs-verification` para la validación dinámica; equivalencias de matriz y alcance de grep: `confirmed` por código fuente.

Antes de cerrar o fusionar: instalar las dependencias en `.venv` con acceso al índice autorizado, ejecutar cada prueba focal y el `pytest -q` completo por tanda, y revertir cualquier migración que produzca una regresión. Sólo cuando las 72 rutas estén resueltas sin ambigüedad podrá marcarse `require_roles` como deprecado en `app/dependencies/auth.py`.
