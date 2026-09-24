# Piloto sintético de motor de autorización (OpenFGA) — acceso a reservas por hotel/miembro

**Fecha:** 2026-09-24
**Código base:** `f895899` (worktree `hotel-chipre-rbac-claude-20260924`)
**Relacionado:** `docs/decisions/authorization-engine-evaluation-adr.md` (ADR completo, recomendación: no migrar runtime ahora)

## Qué es esto

Un modelo OpenFGA de juguete (`reservation-access.fga.yaml`) que ejercita el patrón ReBAC
"un usuario puede ver una reserva si es miembro del hotel dueño de la reserva, o si se le
asignó directamente" con datos **100% sintéticos**: hoteles `hotel-1`/`hotel-2`, reservas
`res-1`/`res-2`, usuarios `anne`/`bob`/`carla`/`dave`/`owner1` — nombres inventados, no
corresponden a ningún hotel, usuario o reserva real.

## Qué NO es esto

- **No prueba paridad con el PMS real.** El RBAC de producción (`docs/design/RBAC_DESIGN.md`)
  tiene overrides por usuario, ventanas de visibilidad configurables, y una cadena de
  resolución `invariant > user > hotel role > role default > deny`
  (`app/services/permission_service.py:779-787`) que este modelo de juguete no replica.
- **No reemplaza ni prueba PostgreSQL RLS.** El aislamiento multi-tenant real del PMS tiene
  una segunda capa a nivel de base de datos (`app/services/tenant_context.py`,
  `tests/test_rls_live_verification.py`) que este piloto no toca ni simula.
  Ver §2 del ADR para el análisis completo de esta distinción.
- **No se conectó a ningún servicio cloud ni dato real.** Ningún proveedor, credencial,
  base de datos ni endpoint de este repo fue tocado para armar este piloto.
- **No se agregó ninguna dependencia** de producto ni de CI. Este directorio es solo
  documentación.

## Cómo se probó

```sh
fga model test --tests reservation-access.fga.yaml
```

**Resultado: 6/6 tests y 6/6 checks pasaron** con la CLI oficial OpenFGA `fga v0.8.1`
(release del 2026-09-24). El binario se descargó a un directorio temporal y se validó
contra el SHA-256 publicado en los metadatos oficiales del release; no se instaló
globalmente ni se agregó como dependencia del producto.

La sintaxis sigue el formato `.fga.yaml` descrito en la [documentación oficial de tests de
modelos](https://openfga.dev/docs/modeling/testing). Para repetir la validación, instalar
una versión aprobada de la CLI y correr el comando de arriba.

## Casos cubiertos

| Test | Resultado esperado | Qué prueba |
|---|---|---|
| `allow_correct_hotel_member` | **allow** | Miembro del hotel correcto ve una reserva de ese hotel |
| `deny_wrong_hotel` | **deny** | Miembro de otro hotel no ve la reserva (hotel equivocado) |
| `deny_wrong_role_for_action` | **deny** | Miembro (no admin) no puede administrar la reserva (rol/acción incorrectos) |
| `deny_unassigned_resource` | **deny** | Usuario sin ninguna relación con el hotel ni la reserva (recurso no asignado) |
| `allow_assigned_agent_before_revoke` | **allow** | Agente con asignación directa vigente puede ver la reserva |
| `deny_assigned_agent_after_revoke` | **deny** | Mismo agente sin la tupla de asignación (relación eliminada) pierde el acceso |

## Límite conocido del modelo (no cubierto por los tests)

`admin` no implica `member` en este modelo de juguete: `can_view` solo mira
`member from hotel or assigned_agent`, así que `owner1` (admin de hotel-1) no
puede ver la reserva bajo este esquema aunque administre el hotel. No hay test
que ejercite ese caso — se deja anotado como límite conocido, no como bug: un
modelo real tendría que decidir explícitamente si admin hereda member.

## Por qué este caso y no otro

Se eligió "acceso a reserva por hotel/miembro, con una asignación directa opcional" porque
es el ejemplo ReBAC mínimo que distingue tres fuentes de autorización distintas (membership
heredada, rol dentro del hotel, asignación directa al recurso) sin inventar un caso de
producto que hoy no existe. El ADR (§3) es explícito: **no hay evidencia en este repo de
que el PMS necesite hoy un modelo ReBAC** — este piloto es una referencia técnica lista
para usar si ese caso aparece, no una propuesta de que el caso ya exista.
