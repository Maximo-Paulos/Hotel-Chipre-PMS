---
title: "Hotel PMS — Technical Orchestrator Backlog"
status: "living-document"
document_type: "technical-executable-backlog"
last_updated: "2026-08-19"
tags: [hotel-pms, orchestrator, technical-backlog, agents, development]
---

> [!IMPORTANT]
> Documento histórico. La fuente maestra única vigente para mandar a desarrollar es `docs/HOTEL_PMS_MASTER_DEVELOPMENT_SPEC.md`.

# Hotel PMS — Technical Orchestrator Backlog

> Este archivo es la **fuente de verdad técnica ejecutable** del proyecto.
>
> Su objetivo es que un agente orquestador pueda leer requisitos, auditar el repositorio, detectar qué ya existe, abrir loops independientes para lo que falta, validar cada entrega y actualizar el estado.
>
> No es el documento principal para pagos de proveedores, contratación de servicios, decisiones comerciales, compra de dominios ni tareas manuales del dueño del proyecto.

---

# 1. Cómo debe usar este archivo el orquestador

Flujo esperado:

```text
Leer este archivo
      ↓
Auditar el repositorio real
      ↓
Comparar código vs requisitos
      ↓
Marcar lo que ya cumple
      ↓
Detectar lo incompleto
      ↓
Separar tareas independientes
      ↓
Crear un loop por tarea
      ↓
Implementar
      ↓
Testear
      ↓
Revisar
      ↓
Verificar criterios de aceptación
      ↓
Registrar evidencia
      ↓
Merge a main cuando sea seguro
```

Reglas:

1. No asumir que una feature falta sin buscarla primero.
2. No asumir que una feature está completa porque existe una clase, endpoint o archivo.
3. No duplicar sistemas existentes.
4. No mezclar tareas no relacionadas en un mismo loop.
5. Tareas independientes pueden correr en paralelo.
6. Tareas con dependencias deben respetar el orden.
7. La implementación debe ser revisada antes de marcarse como terminada.
8. El orquestador debe actualizar este mismo archivo después de cada auditoría o entrega.
9. Si el código existente contradice este documento, este documento representa el estado deseado salvo que el Product/Project Lead lo cambie explícitamente.
10. Cambios destructivos de infraestructura o producción requieren una política explícita o instrucción humana.

---

# 2. Estados permitidos

| Estado | Significado |
|---|---|
| `AUDIT_REQUIRED` | El requisito existe, pero todavía no se verificó el estado real del repo. |
| `TODO` | Se confirmó que falta y está listo para implementar. |
| `IN_PROGRESS` | Hay un loop trabajando activamente. |
| `BLOCKED` | Existe una dependencia concreta que impide continuar. |
| `VERIFY` | Hay implementación, pero falta validación completa. |
| `VERIFIED` | Cumple los criterios y existe evidencia. |
| `DEFERRED` | Se decidió postergar. |
| `REJECTED` | Se eliminó o reemplazó el requisito. |

Nunca usar `VERIFIED` sin evidencia.

---

# 3. Formato obligatorio para nuevas tareas

```md
## TECH-XXXX — Nombre

Status: AUDIT_REQUIRED
Priority: P0 / P1 / P2 / P3
Depends on: ...

### Goal
Resultado que debe existir.

### Required behavior
Comportamiento esperado.

### Acceptance criteria
- [ ] criterio
- [ ] criterio

### Verification
Cómo demostrar que funciona.

### Evidence
- commit:
- tests:
- screenshots/logs:
- files changed:

### Notes / decisions
Contexto importante.
```

---

# 4. Definition of Done general

Una tarea no está terminada hasta que corresponda:

- [ ] implementación completa;
- [ ] tests agregados/actualizados;
- [ ] tests relevantes existentes pasan;
- [ ] no hay regresiones obvias;
- [ ] aislamiento multi-hotel preservado;
- [ ] permisos validados en backend;
- [ ] migraciones seguras cuando aplica;
- [ ] errores manejados;
- [ ] background jobs observables cuando aplica;
- [ ] criterios de aceptación verificados;
- [ ] evidencia registrada;
- [ ] documentación actualizada.

Para UI:

- [ ] desktop;
- [ ] mobile;
- [ ] tablet cuando corresponda;
- [ ] loading state;
- [ ] empty state;
- [ ] error state;
- [ ] no regresiones visuales obvias.

---

# 5. Qué pertenece en este archivo

Sí:

- features;
- UX;
- frontend;
- backend;
- modelos;
- APIs;
- DB;
- permisos;
- seguridad implementada en código;
- analytics;
- Data Warehouse;
- Data Marts;
- búsquedas;
- performance;
- caches;
- background jobs;
- integraciones;
- PWA;
- mobile;
- IA dentro del PMS;
- tests;
- migraciones;
- observabilidad;
- refactors necesarios.

No como fuente principal:

- pagar AWS/GCP/Vercel/Render;
- comprar dominio;
- pagar Apple Developer;
- pagar Google Play;
- contratos;
- facturación administrativa;
- secretos personales;
- tareas comerciales sin cambio de código.

---

# 6. Baseline técnico conocido del repo

## Frontend

Actualmente existe:

- React;
- TypeScript;
- Vite;
- React Router;
- TanStack Query;
- Tailwind;
- Playwright;
- Capacitor.

Ya existen shells/proyectos para:

- iOS;
- Android.

Rutas relevantes:

- `frontend/package.json`
- `frontend/capacitor.config.ts`
- `frontend/ios/`
- `frontend/android/`
- `frontend/CAPACITOR_RELEASE.md`

## Backend

Actualmente existe:

- Python;
- FastAPI;
- SQLAlchemy;
- Alembic;
- PostgreSQL;
- Celery;
- Redis;
- OR-Tools.

También existen dependencias/configuración para:

- MongoDB;
- Cassandra;
- Neo4j.

No asumir que están activas en producción ni que deben activarse.

## Contexto de deploy actual

- Vercel: frontend.
- Render: backend.
- Supabase/PostgreSQL: DB.
- Resend: email.
- GitHub: repositorio y flujo de código.

Este documento no obliga a mantener esos proveedores para siempre.

---

# 7. Principios técnicos obligatorios

## 7.1. Fuente de verdad operacional

PostgreSQL/relacional continúa siendo la fuente de verdad operacional mientras no exista una decisión explícita distinta.

Ejemplos:

- hoteles;
- usuarios;
- membresías;
- roles;
- permisos;
- huéspedes;
- habitaciones;
- categorías;
- reservas;
- tarifas;
- pagos;
- inventario;
- suscripciones;
- integraciones.

## 7.2. Lecturas rápidas

No agregar NoSQL automáticamente.

Antes evaluar:

1. query;
2. índices;
3. búsqueda de PostgreSQL;
4. Redis;
5. materialized views;
6. read models;
7. search engine;
8. recién después una nueva DB si existe un motivo concreto.

## 7.3. OLTP separado de analytics

Recepción no debe ponerse lenta porque un dashboard recalcule años de historia.

```text
Operación → PostgreSQL / OLTP
Analytics → Data Warehouse / Data Marts
```

## 7.4. Multi-tenant

Hotel A nunca puede acceder a datos de Hotel B.

Todo feature nuevo debe preservar aislamiento por hotel.

## 7.5. Permisos

Ocultar UI no es seguridad.

Las autorizaciones deben verificarse server-side.

---

# 8. Backlog técnico

## TECH-0001 — Data Warehouse foundation

Status: `AUDIT_REQUIRED`  
Priority: `P1`

### Goal

Crear una capa analítica separada para evitar que consultas históricas/agregadas pesadas afecten PostgreSQL transaccional.

### Required behavior

- PostgreSQL sigue siendo la fuente de verdad.
- Los datos necesarios para analytics se copian/transforman al warehouse.
- BigQuery es actualmente la opción preferida.
- La sincronización puede ser incremental.
- No todo necesita estar actualizado en tiempo real.
- Debe poder existir una demora controlada de minutos u horas según el KPI.

### Dominios iniciales

- hotels;
- guests;
- guest country/nationality;
- reservations;
- reservation status;
- check-in/check-out;
- rooms;
- categories;
- rates;
- payments;
- revenue;
- source/channel;
- cancellations;
- occupancy;
- length of stay.

Dominios posteriores:

- inventory;
- housekeeping;
- linen/laundry;
- costs;
- subscriptions;
- SaaS usage;
- AI usage;
- integrations.

### Acceptance criteria

- [ ] PostgreSQL sigue siendo autoritativo.
- [ ] Warehouse separado del path normal de requests.
- [ ] Pipeline reproducible.
- [ ] Sincronización incremental o plan claro para llegar a ella.
- [ ] Reejecución no crea duplicados incorrectos.
- [ ] `hotel_id`/tenant se preserva.
- [ ] Fallas del pipeline son observables.
- [ ] PII se minimiza según necesidad analítica.
- [ ] Freshness documentada.
- [ ] Existe al menos una query analítica end-to-end sin escanear OLTP de producción.

### Verification

1. crear o identificar datos de prueba;
2. sincronizar;
3. verificar llegada al warehouse;
4. repetir sync;
5. verificar no duplicación;
6. correr query analítica;
7. inspeccionar failure handling.

### Evidence

- commit:
- tests:
- pipeline:
- sample query:

---

## TECH-0002 — Hotel Analytics Data Mart

Status: `AUDIT_REQUIRED`  
Priority: `P1`  
Depends on: `TECH-0001`

### Goal

Preparar datos por hotel para responder rápidamente preguntas de negocio sin recalcular todo el histórico en cada request.

### Preguntas mínimas

- ¿De qué país vienen más huéspedes?
- ¿Qué porcentaje es argentino/brasileño/etc.?
- ¿Cuál es el huésped que más vuelve?
- ¿Cuál es la ocupación?
- ¿Cuál es el ADR?
- ¿Cuál es el RevPAR?
- ¿Cuál es la estadía promedio?
- ¿Qué categoría factura más?
- ¿Qué canal funciona mejor?
- ¿Cómo se compara un período contra otro?

### Acceptance criteria

- [ ] Todo queda scoped por hotel.
- [ ] Distribución por nacionalidad.
- [ ] Ranking de huéspedes recurrentes.
- [ ] Ocupación por período.
- [ ] ADR por período.
- [ ] RevPAR por período.
- [ ] Average length of stay.
- [ ] Revenue por categoría.
- [ ] Revenue/reservas por canal.
- [ ] Definiciones de KPIs documentadas.
- [ ] Freshness visible.

### Evidence

- commit:
- tests:
- metric definitions:
- sample response:

---

## TECH-0003 — SaaS Owner Analytics Data Mart

Status: `AUDIT_REQUIRED`  
Priority: `P2`  
Depends on: `TECH-0001`

### Goal

Dar al dueño de la plataforma una vista agregada del negocio SaaS.

### Métricas candidatas

- hoteles registrados;
- hoteles activos;
- trials;
- suscripciones;
- distribución por plan;
- habitaciones gestionadas;
- usuarios;
- reservas procesadas;
- uso de API;
- uso de IA;
- integraciones;
- background jobs;
- errores;
- MRR/ARR cuando billing esté disponible.

### Acceptance criteria

- [ ] Métricas SaaS separadas de analytics de un hotel.
- [ ] No depende de joins pesados live contra producción para cada consulta.
- [ ] Guest PII excluida salvo necesidad explícita.
- [ ] Definiciones documentadas.
- [ ] Freshness visible.

---

## TECH-0010 — Fast guest search

Status: `AUDIT_REQUIRED`  
Priority: `P1`

### Goal

La búsqueda de huéspedes debe sentirse inmediata.

### Required behavior

Escribir `Ma` debe devolver rápidamente huéspedes relevantes del hotel actual.

Campos potenciales:

- nombre;
- apellido;
- teléfono;
- email;
- documento.

### Acceptance criteria

- [ ] Tenant scoped.
- [ ] Partial-name search.
- [ ] Ranking razonable.
- [ ] Limit/pagination.
- [ ] No carga toda la tabla en memoria.
- [ ] Índices/query plan adecuados.
- [ ] Frontend cancela/debouncea requests obsoletos cuando corresponda.
- [ ] Target de performance se define después de benchmark real.

---

## TECH-0011 — Fast reservation quote and rate lookup

Status: `AUDIT_REQUIRED`  
Priority: `P1`

### Goal

Recepción debe obtener rápidamente disponibilidad, tarifa y total de una estadía.

### Inputs

- hotel;
- categoría;
- check-in;
- check-out;
- huéspedes;
- rate plan.

### Outputs

- disponibilidad;
- precio actual;
- total;
- restricciones/condiciones relevantes.

### Acceptance criteria

- [ ] Usa tarifa autoritativa.
- [ ] Scoped por hotel.
- [ ] Pricing por rango de fechas correcto.
- [ ] Availability y pricing usan mismas fechas.
- [ ] Un cache viejo no puede devolver silenciosamente un precio incorrecto.
- [ ] Invalidación de cache documentada si existe cache.
- [ ] Tests para cambios de tarifa y límites de fechas.

---

## TECH-0020 — Granular RBAC

Status: `AUDIT_REQUIRED`  
Priority: `P0`

### Goal

Soportar roles y permisos granulares dentro de cada hotel.

### Conceptos

- user;
- hotel;
- membership;
- role;
- permission;
- role_permissions;
- overrides por membership cuando corresponda.

### Ejemplos de permisos

- `reservations.read`
- `reservations.write`
- `reservations.delete`
- `guests.read`
- `guests.write`
- `finance.read`
- `pricing.read`
- `pricing.write`
- `inventory.read`
- `inventory.write`
- `staff.manage`
- `integrations.manage`
- `analytics.read`

### Acceptance criteria

- [ ] Permisos scoped por hotel.
- [ ] Backend rechaza acciones no autorizadas.
- [ ] Owner puede asignar roles.
- [ ] Overrides soportados si la regla de producto lo permite.
- [ ] Finance puede bloquearse.
- [ ] Pricing write puede bloquearse.
- [ ] Tests cross-tenant.
- [ ] UI refleja permisos sin ser la única barrera.

---

## TECH-0021 — Subscription entitlements separados de permisos

Status: `AUDIT_REQUIRED`  
Priority: `P1`

### Goal

Separar:

- lo que el hotel pagó;
- lo que cada empleado puede hacer.

### Conceptos

- plans;
- subscriptions;
- entitlements;
- usage limits;
- room limits;
- hotel feature access;
- user permission access.

### Acceptance criteria

- [ ] Entitlement no se modela como rol.
- [ ] Permiso no se modela como plan.
- [ ] Límites de habitaciones se pueden aplicar.
- [ ] Feature access se valida server-side.
- [ ] API rechaza feature no incluida en plan.
- [ ] API también rechaza usuario sin permiso.

---

## TECH-0030 — Reservation assignment optimizer

Status: `AUDIT_REQUIRED`  
Priority: `P1`

### Goal

Asignar o proponer habitaciones reduciendo huecos y mejorando ocupación.

### Debe considerar

- fechas;
- categoría;
- capacidad;
- habitaciones;
- reservas existentes;
- reservas futuras;
- huecos;
- asignaciones fijas;
- reglas del hotel.

### Existing context

El repo ya contiene OR-Tools, Celery y Redis.

Auditar antes de crear algo nuevo.

### Acceptance criteria

- [ ] No crea overlaps.
- [ ] Respeta categoría/capacidad.
- [ ] Respeta asignaciones no movibles.
- [ ] Puede correr async.
- [ ] No bloquea API normal.
- [ ] Jobs retry-safe/idempotentes.
- [ ] Maneja concurrencia.
- [ ] Resultado auditable.
- [ ] Tests de edge cases.

---

## TECH-0040 — PWA readiness

Status: `AUDIT_REQUIRED`  
Priority: `P1`

### Goal

Que la web sea una excelente primera versión mobile/tablet/desktop e instalable cuando sea posible.

### Acceptance criteria

- [ ] Responsive mobile.
- [ ] Tablet usable.
- [ ] Manifest válido.
- [ ] Installability verificada.
- [ ] Icons correctos.
- [ ] Offline behavior explícito.
- [ ] Auth funciona instalada.
- [ ] Critical screens testeadas en mobile viewport.

---

## TECH-0041 — iOS / Android readiness

Status: `AUDIT_REQUIRED`  
Priority: `P2`  
Depends on: `TECH-0040`

### Goal

Preservar publicación futura sin reescribir frontend.

### Existing context

Ya existe Capacitor iOS/Android.

### Acceptance criteria

- [ ] Build web sincroniza a Capacitor.
- [ ] API de producción accesible desde dispositivo real.
- [ ] Auth funciona en shell nativo.
- [ ] Redirects/deep links compatibles cuando corresponda.
- [ ] Pantallas clave usables.
- [ ] Instrucciones de build actualizadas.

---

## TECH-0050 — Audit log de negocio

Status: `AUDIT_REQUIRED`  
Priority: `P0`

### Goal

Poder rastrear cambios importantes.

### Eventos mínimos candidatos

- reservation create/update/delete;
- rate change;
- payment status;
- room assignment;
- permission change;
- integration change;
- AI action.

### Acceptance criteria

- [ ] hotel;
- [ ] actor;
- [ ] timestamp;
- [ ] action;
- [ ] resource;
- [ ] datos sensibles minimizados;
- [ ] usuarios normales no pueden alterar audit log;
- [ ] mutations críticas cubiertas.

---

## TECH-0060 — Master SaaS admin

Status: `AUDIT_REQUIRED`  
Priority: `P2`

### Goal

Panel seguro del dueño del SaaS.

### Capacidades objetivo

- hoteles;
- plan/subscription;
- usage;
- health;
- analytics SaaS;
- integraciones;
- errores/jobs;
- acciones admin autorizadas.

### Acceptance criteria

- [ ] Auth master fuerte y separada.
- [ ] Acciones auditadas.
- [ ] Impersonation, si existe, explícita y auditada.
- [ ] PII minimizada por defecto.
- [ ] Métricas SaaS accesibles.

---

## TECH-0100 — AI assistant read-only foundation

Status: `DEFERRED`  
Priority: `P3`

### Goal

Futuro asistente conversacional que pueda consultar el hotel.

### Ejemplos

- ¿Cuántas habitaciones disponibles hay?
- ¿Cómo fue mi mes?
- ¿Qué nacionalidad viene más?
- ¿Cuál fue mi ocupación?

### Regla técnica

La IA usa tools/APIs controladas.

No recibe acceso irrestricto a la DB.

### Acceptance criteria

- [ ] Scoped al hotel actual.
- [ ] Hereda permisos del usuario.
- [ ] Respeta entitlements.
- [ ] Tool calls auditables.
- [ ] Analytics puede consultar warehouse/data marts.
- [ ] Operación consulta fuentes autoritativas.
- [ ] PII minimizada.

---

## TECH-0101 — AI assistant controlled write actions

Status: `DEFERRED`  
Priority: `P3`  
Depends on: `TECH-0100`, `TECH-0020`, `TECH-0021`, `TECH-0050`

### Goal

Permitir que la IA modifique el negocio con seguridad.

### Ejemplo

Usuario:

> Subí las tarifas de doble baño compartido para los feriados.

Flujo esperado:

1. IA encuentra fechas relevantes con una herramienta autorizada.
2. Presenta las fechas.
3. Propone cambio.
4. Usuario confirma.
5. Backend vuelve a validar permisos.
6. Ejecuta modificación.
7. Audit log registra resultado.

### Acceptance criteria

- [ ] Tools tipadas/internas.
- [ ] Permission check al ejecutar.
- [ ] Entitlement check.
- [ ] Confirmación para acciones de impacto.
- [ ] Auditabilidad.
- [ ] Validación previa.
- [ ] Manejo de partial failures.
- [ ] Retry no duplica acciones.

---

# 9. Ingreso de nuevos requisitos

Cuando el Product/Project Lead describe una nueva feature:

```text
Hablar / definir
      ↓
Convertir a TECH-XXXX
      ↓
Agregar criterios de aceptación
      ↓
Guardar acá
      ↓
Orquestador audita después
      ↓
Loop de implementación
```

No dejar requisitos importantes únicamente en conversaciones.

---

# 10. Comportamiento al pedir "continuá desarrollando"

Cuando el orquestador recibe una instrucción como:

- "continuá desarrollando";
- "corré el loop";
- "revisá features nuevas";
- "seguí con el backlog";

debe:

1. leer este archivo;
2. recorrer todos los `TECH-XXXX`;
3. respetar dependencias;
4. priorizar P0 > P1 > P2 > P3;
5. auditar `AUDIT_REQUIRED`;
6. convertirlos a:
   - `VERIFIED` si ya cumplen y hay evidencia;
   - `VERIFY` si parecen hechos pero falta prueba;
   - `TODO` si faltan;
   - `BLOCKED` si dependen de otra tarea;
7. iniciar loops para los `TODO` accionables;
8. revisar cada entrega;
9. actualizar estado/evidencia;
10. mergear código validado siguiendo la política del repo.

---

# 11. Changelog

## 2026-08-19

Se redefinió este documento como backlog técnico ejecutable para un agente orquestador.

Se agregó:

- modelo de loops;
- auditoría previa;
- estados;
- Definition of Done;
- formato de tareas;
- separación de trabajo técnico vs tareas manuales del dueño;
- Data Warehouse;
- Hotel Data Mart;
- SaaS Data Mart;
- búsqueda rápida;
- quote/rates;
- RBAC;
- entitlements;
- optimizador;
- PWA;
- mobile;
- audit log;
- master admin;
- IA futura de lectura/escritura.

---

# 12. Product Lead Inbox

Usar esta sección únicamente para notas técnicas todavía no convertidas a `TECH-XXXX`.

## Pending

- None.
