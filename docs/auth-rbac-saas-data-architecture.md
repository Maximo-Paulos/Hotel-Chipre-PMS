# Arquitectura de identidad, autorización y datos para el SaaS

> **Documento histórico especializado.** La fuente maestra única vigente para mandar a desarrollar es `docs/HOTEL_PMS_MASTER_DEVELOPMENT_SPEC.md`.

Estado: especificación objetivo adaptable al repositorio  
Proyecto: Hotel-Chipre-PMS  
Última actualización: 2026-08-20

## 1. Propósito y criterio de decisión

Este documento consolida la dirección de producto y arquitectura para preparar Hotel-Chipre-PMS como SaaS multi-tenant público, capaz de operar con miles de hoteles y múltiples usuarios por hotel.

La decisión de negocio es mantener bajo control propio las capacidades que definen el producto:

- identidad interna, cuentas, memberships y sesiones;
- hoteles, roles, permisos y overrides;
- planes, límites, descuentos, bonificaciones y entitlements;
- auditoría de negocio y métricas SaaS.

No se propone contratar Clerk, Auth0 u otro proveedor que cobre por usuario como dependencia central. “Propio” no significa inventar criptografía ni protocolos: contraseñas, OAuth/OIDC, TOTP y WebAuthn deben implementarse con estándares y librerías maduras. Email transaccional, entrega de mensajes, infraestructura y proveedores OAuth pueden seguir siendo servicios externos reemplazables.

Principio rector:

> Adaptar y fortalecer lo que ya existe antes de reemplazarlo. El agente implementador debe verificar código, migraciones, tests y runtime actuales; este documento define resultados y límites, no obliga a una reescritura ni a nombres de tablas exactos.

## 2. Estado observado en el repositorio

La auditoría inicial confirma que no se parte de cero:

- FastAPI/PostgreSQL ya implementan registro, login, verificación y recuperación de contraseña con JWT.
- El frontend conserva actualmente un access token en `localStorage`; debe evaluarse su migración hacia sesiones web revocables con cookie segura.
- Existe una matriz configurable de permisos con `permissions`, defaults por rol y overrides por hotel.
- La pantalla actual de Permisos presenta columnas Owner, Co-owner, Manager, Recepción y Housekeeping, permisos atómicos agrupables y el indicador `Base`. Esta es la referencia UX que debe conservarse y madurarse.
- Existen invitaciones hotel-scoped y controles de roles asignables.
- Existen audit logs tenant-scoped y eventos separados del panel master.
- Existen suscripciones, límites de habitaciones/staff, entitlements, overrides por hotel, estado `comped` y eventos de suscripción.
- Existe `/adminpmsmaster` con autenticación, CSRF, dashboard, políticas de billing, integraciones y auditoría master.
- Analytics ya contiene facts diarios y jobs hotel-scoped; esto es una base útil para una futura capa analítica.

Estos puntos son una fotografía del checkout revisado, no garantía de cobertura completa. Antes de implementar se debe clasificar cada área como `existente`, `parcial`, `faltante` o `needs-verification` y comprobar su seguridad con tests.

## 3. Separación de dominios

Los controles deben permanecer separados:

```text
Identidad       ¿Quién es la persona?
Sesión          ¿Qué dispositivo/sesión autenticó a esa persona?
Membership      ¿A qué hotel pertenece y en qué estado?
Autorización    ¿Puede ejecutar esta acción en este hotel y recurso?
Entitlement     ¿El hotel contrató esta funcionalidad o capacidad?
Step-up         ¿La acción requiere autenticación reforzada ahora?
Auditoría       ¿Quién intentó o ejecutó qué, dónde y con qué resultado?
```

Una autorización positiva requiere, como mínimo:

```text
sesión válida
AND membership activa en el hotel solicitado
AND entitlement del hotel habilitado
AND permiso efectivo del usuario/rol
AND condiciones del recurso satisfechas
AND step-up vigente si la acción es sensible
```

El frontend puede ocultar o deshabilitar controles para mejorar la experiencia, pero el backend es la autoridad y debe denegar por defecto.

## 4. Identidad y multi-hotel

Una persona debe tener una identidad global única y poder pertenecer a uno o más hoteles:

```text
User 1 ──< Membership >── Hotel N
                    ├── estado
                    ├── roles
                    ├── overrides personales opcionales
                    └── fechas de alta/baja
```

El rol no debe ser un atributo global de `users`. La misma persona puede ser Owner en un hotel y Recepcionista en otro. Todo acceso operativo debe resolver el `hotel_id` desde un contexto confiable y validar la membership contra la base, nunca aceptar como verdad un rol o hotel enviado por el navegador.

Restricciones recomendadas:

- email normalizado e identidad interna estable;
- unicidad de membership activa por `(user_id, hotel_id)`;
- FKs e índices compuestos que incluyan `hotel_id` en datos tenant-scoped;
- prohibición de mezclar IDs de recursos de hoteles diferentes;
- tests negativos sistemáticos de aislamiento A/B;
- RLS en PostgreSQL como defensa adicional sólo si puede operarse correctamente con el pool y el contexto de cada transacción; nunca como sustituto de controles de servicio.

## 5. Auth propio y sesiones

### 5.1 Métodos de ingreso

La cuenta interna debe admitir:

1. email + contraseña;
2. Google mediante OAuth 2.0/OpenID Connect;
3. Sign in with Apple mediante OpenID Connect;
4. posteriormente, passkeys/WebAuthn.

Google y Apple son proveedores de identidad, no dueños de la cuenta de negocio. La aplicación conserva su propio `user_id`, memberships, permisos, sesiones, auditoría y recuperación.

Modelo conceptual:

```text
users
auth_identities
  user_id
  provider            # password | google | apple | passkey
  provider_subject    # sub estable, no email como identidad primaria
  provider_email
  email_verified
  linked_at
  last_used_at
```

Debe permitirse vincular/desvincular proveedores desde una sesión autenticada, con reautenticación para cambios sensibles. El linking automático sólo por coincidencia de email puede producir account takeover; requiere email verificado, reglas explícitas y, preferentemente, confirmación desde la cuenta ya autenticada. Apple puede entregar email relay y el nombre sólo la primera vez: deben persistirse cuando se reciben sin depender de que vuelvan a aparecer.

### 5.2 Sesiones web revocables

Objetivo preferido para web:

- cookie `HttpOnly`, `Secure`, `SameSite` apropiado y Path/Domain mínimos;
- identificador de sesión aleatorio y opaco; en DB se guarda sólo su hash;
- expiración absoluta e inactividad deslizante acotada;
- rotación al autenticar, elevar privilegio o cambiar contraseña;
- protección CSRF en operaciones mutantes cuando el navegador envía cookies automáticamente;
- revocación individual y global;
- pantalla “Dispositivos conectados” con alta, último uso aproximado y cierre de sesión;
- no registrar cookies, tokens, secretos, códigos MFA ni datos sensibles.

La migración desde JWT/localStorage debe ser progresiva y compatible con clientes móviles/API. Puede conservarse un access token corto para APIs, pero el refresh debe estar controlado por una sesión server-side revocable. No se debe cambiar el contrato actual sin inventario de consumidores y plan de transición.

### 5.3 Registro, verificación y recuperación

- respuestas que no permitan enumerar cuentas;
- tokens aleatorios, de un solo uso, con vencimiento y guardados hasheados;
- rate limit por cuenta, IP y señal de riesgo, sin bloquear masivamente usuarios legítimos;
- revocación de sesiones al resetear contraseña, salvo política explícita más acotada;
- emails transaccionales sin secretos persistidos en logs;
- auditoría de eventos de seguridad con minimización de PII.

## 6. Migración bcrypt a Argon2id

Usar una implementación mantenida de Argon2id y parámetros calibrados con benchmark en el hardware real. La migración recomendada es “rehash on login”:

```text
login → detectar esquema del hash
      → verificar bcrypt existente
      → si es válido, generar Argon2id y reemplazar dentro de una operación segura
      → nuevas contraseñas se guardan sólo con Argon2id
```

Requisitos:

- mantener verificación bcrypt durante la ventana de transición;
- almacenar/identificar versión y parámetros del hash;
- usar `needs_rehash` para elevar parámetros en el futuro;
- evitar migración masiva porque los hashes no son reversibles;
- no truncar contraseñas silenciosamente;
- permitir frases largas y filtrar contraseñas comprometidas;
- no imponer reglas arbitrarias de composición (mayúscula, número y símbolo) ni rotaciones periódicas sin evidencia de compromiso;
- definir la longitud mínima según el tipo de autenticación y la normativa vigente; como referencia de diseño, admitir al menos 64 caracteres y evaluar un mínimo de 15 cuando la contraseña sea el único factor;
- medir latencia, memoria y capacidad bajo concurrencia antes de fijar parámetros;
- tests de hash nuevo, login antiguo + upgrade, password incorrecta y concurrencia.

## 7. MFA TOTP y autenticación reforzada

### 7.1 MFA de cuenta

Primera etapa: TOTP compatible con aplicaciones estándar, más recovery codes de un solo uso guardados hasheados.

Flujo de alta:

1. usuario reautentica su sesión;
2. servidor genera secreto TOTP;
3. secreto se cifra en reposo con una clave fuera de la base;
4. usuario escanea QR y confirma con un código válido;
5. recién entonces se marca MFA activo;
6. se generan recovery codes mostrados una sola vez.

Aplicar rate limiting, ventana temporal pequeña, protección contra replay del mismo timestep y auditoría. MFA debe ser obligatorio para Master Admin y recomendable/gradualmente obligatorio para Owners y usuarios con permisos críticos.

### 7.2 Step-up para acciones sensibles

No toda sesión necesita pedir MFA todo el tiempo. Acciones como administrar permisos, emitir API keys, cambiar datos de cobro, exportar PII o aprobar una excepción crítica pueden exigir una autenticación reciente. El servidor emite una prueba de step-up corta y vinculada a usuario, sesión, hotel y propósito.

## 8. RBAC configurable por hotel

### 8.1 Modelo efectivo

La matriz de la captura es la referencia principal de experiencia:

- filas: permisos atómicos, con nombre humano, explicación y código técnico;
- columnas: roles del hotel;
- checkbox: estado efectivo;
- badge `Base` u `Override`;
- advertencia visible para permisos críticos;
- guardado auditado por cambio.

La resolución recomendada es:

```text
default del rol del sistema
→ override de rol para ese hotel
→ rol personalizado del hotel (si existe)
→ override explícito de membership/persona (sólo si el producto lo necesita)
→ restricciones de seguridad no anulables
```

Debe documentarse una precedencia determinista. Un `deny` explícito debería ganar sobre grants generales cuando existan múltiples roles, salvo una regla más específica y deliberada. Owner no debe poder retirarse accidentalmente el acceso necesario para recuperar la administración del hotel; definir break-glass seguro, no una puerta trasera invisible.

### 8.2 Catálogo de permisos

Usar códigos estables por recurso y acción, por ejemplo:

```text
reservation:read
reservation:create
reservation:update
reservation:discount
reservation:delete
guest:read
guest:pii.read
cash:operate
cash:approve_difference
staff:invite
permissions:manage
audit:view
apikey:manage
```

Evitar checks dispersos como `role == "owner"`. Los permisos críticos deben tener metadata (`critical`, `step_up_required`, `delegable`, categoría, descripción). Cambiar el código de un permiso es una migración de contrato.

### 8.3 Evolución UX

- filtros/búsqueda y agrupación por módulo;
- encabezado fijo y manejo accesible de tablas anchas;
- indicador de cambios sin guardar o autosave con estado inequívoco;
- “restaurar valor base” por celda/rol;
- resumen antes de aplicar cambios masivos;
- explicación del impacto y usuarios afectados;
- prohibir editar permisos fuera del hotel activo;
- versión/ETag para evitar que dos owners sobrescriban cambios concurrentes;
- historial de quién cambió cada permiso y cuándo.

## 9. Permiso temporal de una sola acción

### 9.1 Caso de uso

Un recepcionista intenta aplicar un descuento sin `reservation:discount`. En vez de recibir sólo un 403, puede crear una solicitud precisa. Un Owner/Manager autorizado la revisa y aprueba; el recepcionista repite la operación usando una autorización de uso único.

### 9.2 Modelo sugerido

```text
authorization_requests
  id, hotel_id, requester_membership_id
  permission_code
  resource_type, resource_id
  action_fingerprint        # hash de parámetros relevantes
  reason
  status                    # pending/approved/denied/used/expired/revoked
  requested_at, expires_at
  decided_by_membership_id, decided_at
  approval_method

one_time_grants
  request_id
  token_hash
  bound_session_id
  valid_until
  used_at
```

El grant debe estar ligado a una acción concreta: hotel, actor, sesión, permiso, recurso, límites y parámetros relevantes (por ejemplo porcentaje/monto máximo y moneda). Debe vencer rápidamente y consumirse atómicamente en la misma transacción que ejecuta la acción para impedir replay o doble gasto.

### 9.3 Qué significa “PIN que cambia”

El TOTP del aprobador debe autenticar al aprobador, no convertirse en un PIN maestro que se entrega al empleado. Flujos aceptables:

- aprobación remota: el Owner abre su sesión, revisa contexto y confirma con MFA;
- aprobación presencial: el Owner introduce su TOTP en una pantalla de aprobación que no lo expone al recepcionista y el backend verifica identidad/contexto;
- futuro: aprobación push o passkey.

Nunca aceptar un TOTP aislado como autorización universal. Exigir que el aprobador tenga permiso `authorization_request:approve`, pertenezca al mismo hotel y no apruebe su propia solicitud si la política requiere separación de funciones.

### 9.4 Concurrencia, idempotencia y auditoría

- estado actualizado con compare-and-swap/lock;
- idempotency key en la acción final;
- un grant no puede usarse después de cambio de parámetros;
- aprobación, rechazo, expiración, intento fallido y consumo generan eventos append-only;
- la UI muestra claramente alcance, expiración y resultado;
- nunca almacenar el código TOTP ni el token en audit logs.

## 10. Invitaciones y ciclo de vida del staff

Flujo objetivo:

1. usuario autorizado elige hotel, email, rol(es) y vencimiento;
2. backend valida entitlement de staff, rol asignable y que no exista conflicto;
3. se crea invitación con token hasheado, single-use y hotel-scoped;
4. destinatario inicia sesión/crea cuenta con password, Google o Apple;
5. se muestra explícitamente qué hotel invita y qué rol recibirá;
6. aceptación crea/reactiva membership de forma idempotente;
7. se auditan invitación, reenvío, revocación, aceptación y cambios de rol.

Debe poder revocarse una membership, invalidar sus sesiones/contexto de hotel y conservar el actor histórico en auditoría. Reenviar no debe crear memberships duplicadas. Evitar revelar si un email ya pertenece a otro hotel.

### 10.1 Primary Owner y propiedad del hotel

El rol operativo `Owner` no debe confundirse con la propiedad final de la cuenta del hotel. Cada hotel debe tener un `primary_owner_membership_id` o contrato equivalente, con invariantes que impidan quedar sin responsable.

Acciones reservables al Primary Owner, aun cuando otros usuarios tengan permisos administrativos amplios:

- transferir la propiedad del hotel;
- cambiar el responsable principal de facturación;
- cancelar definitivamente la suscripción;
- solicitar eliminación/cierre del tenant;
- designar un nuevo Primary Owner.

La transferencia exige reautenticación/step-up de ambas partes cuando corresponda, confirmación explícita, protección contra auto-bloqueo y auditoría completa. Debe existir un procedimiento de recuperación manual controlado para pérdida de acceso, sin crear una puerta trasera cotidiana.

## 11. Passkeys y Face ID

Face ID no se integra enviando datos biométricos al backend. La biometría permanece en el dispositivo y desbloquea una clave/passkey o una credencial guardada en Keychain.

### 11.1 Preparación del backend

- soporte WebAuthn/passkeys con challenge aleatorio, de un solo uso y expiración;
- almacenar credential ID, public key, sign counter/flags, transports y metadata mínima;
- múltiples credenciales por usuario, nombres de dispositivo y revocación;
- RP ID/origins correctos por ambiente y HTTPS;
- login y step-up con passkey;
- recuperación segura que no degrade la protección;
- evitar depender de email como identificador WebAuthn.

### 11.2 Lo que debe completar el responsable de Apple

Para una app iOS nativa:

- cuenta Apple Developer activa;
- App ID, bundle identifier y capabilities correspondientes;
- dominio HTTPS propio y archivo `apple-app-site-association` para Associated Domains;
- entitlement `webcredentials:` configurado;
- Keychain/AuthenticationServices y política de fallback;
- textos de privacidad, revisión, pruebas en dispositivos reales y publicación en App Store;
- para Sign in with Apple: Service ID/keys/redirect URIs según la arquitectura elegida y rotación de secretos.

Para desbloqueo diario local puede usarse `LocalAuthentication`/Face ID para liberar una credencial en Keychain; para autenticación phishing-resistant y sincronizable, preferir passkeys. El backend nunca recibe plantilla facial.

## 12. Auditoría del hotel y privacidad del proveedor

### 12.1 Auditoría visible por el Owner

Cada hotel puede consultar eventos relevantes de sus empleados:

- actor y rol/membership al momento del evento;
- acción, recurso, fecha y resultado;
- antes/después redactado cuando sea necesario;
- solicitudes y aprobaciones temporales;
- cambios de permisos, staff, caja, reservas, tarifas e integraciones;
- filtros, paginación y exportación con entitlement si corresponde.

El audit log debe ser append-only a nivel aplicación, tenant-scoped, con retención definida, integridad verificable para eventos críticos y redacción de secretos/PII. No exponer update/delete ordinarios.

### 12.2 Separación del panel Master SaaS

El proveedor no necesita observar el movimiento operativo cotidiano de cada hotel. El Master Admin debe trabajar principalmente con metadatos y agregados:

- hotel, estado, fecha de alta y actividad agregada;
- habitaciones activas/cargadas y empleados/memberships activos/invitados;
- plan, estado de cobro, período, límites, uso y consumo agregado;
- descuentos, créditos, bonificaciones, comped y extensiones con motivo/vencimiento;
- catálogo y precio versionado de planes;
- entitlements y restricciones por plan/hotel;
- métricas globales: hoteles activos, conversión, churn, MRR/ARR si aplica, uso por feature, salud técnica;
- acciones administrativas del proveedor auditadas separadamente.

Aplicar mínimo privilegio y purpose limitation. El soporte excepcional sobre datos operativos debe ser un flujo explícito, temporal, consentido/auditado y no la navegación normal del panel master.

### 12.3 Plano de control del Master Admin

El Master Admin no debe implementarse como `SUPER_OWNER` dentro de las memberships de hoteles. Debe conservar un plano separado (`platform_admins`, sesiones y permisos administrativos equivalentes), con:

- MFA obligatorio;
- sesiones más cortas que las sesiones operativas ordinarias;
- reautenticación para cambios críticos;
- permisos master de mínimo privilegio;
- auditoría completa e independiente de toda acción administrativa;
- ausencia de acceso implícito a la operación privada de los hoteles.

## 13. Planes, precios, descuentos y entitlements

Separar:

- `plan_catalog`: definición comercial versionada;
- `plan_entitlements`: features y límites incluidos;
- `hotel_subscription`: contrato/estado del hotel;
- `billing_adjustments`: descuento, crédito, bonificación o comped con motivo, autor y vigencia;
- `hotel_entitlement_overrides`: excepción técnica/comercial explícita;
- `subscription_events`: historial append-only.

No sobrescribir retrospectivamente el precio contratado al editar el catálogo. Guardar versión/snapshot contractual y moneda/impuestos según jurisdicción. Toda modificación master debe requerir step-up, motivo, idempotencia y auditoría. Los entitlements deben impedir la acción en backend; la UI sólo comunica el límite.

## 14. Eficiencia de PostgreSQL y arquitectura OLTP

PostgreSQL sigue siendo la fuente de verdad para datos transaccionales relacionados. No agregar NoSQL sólo por escala anticipada.

Decenas o cientos de miles de usuarios no constituyen por sí solos un problema extraordinario para PostgreSQL correctamente modelado. Los riesgos principales a esa escala serán el aislamiento, los errores de autorización, las credenciales robadas, la recuperación, la disponibilidad y las integraciones, no la mera cantidad de emails almacenados.

Modelo conceptual orientativo (los nombres pueden adaptarse):

```text
users, auth_identities/credentials, sessions, login_events
mfa_factors, recovery_codes, webauthn_credentials
hotels, hotel_memberships, primary_ownership
roles, permissions, role_permissions, permission_overrides
invitations, authorization_requests, one_time_grants
plans, subscriptions, plan_entitlements, billing_adjustments
platform_admins, admin_sessions, admin_permissions
audit_logs, subscription_events
```

Lineamientos:

- índices derivados de consultas reales; priorizar compuestos que comiencen por `hotel_id` y soporten filtros/orden;
- constraints, FKs, uniques e invariantes en DB además de validación de servicio;
- paginación por cursor para historiales grandes;
- evitar N+1 y cargas completas de relaciones;
- selects explícitos y payloads acotados;
- `EXPLAIN (ANALYZE, BUFFERS)` en staging con datos representativos;
- connection pooling y límites coherentes con la capacidad de DB;
- transacciones cortas, locks deliberados e idempotencia;
- particionamiento sólo cuando volumen y mantenimiento lo justifiquen (audit/eventos por fecha es candidato, no requisito inicial);
- read models/materialized views para dashboards caros;
- Redis para cache/locks/rate limiting cuando aporte valor medido; nunca como fuente de verdad de autorización crítica sin estrategia fail-closed;
- observabilidad por query, p95/p99, locks, pool, cache hit ratio y crecimiento de tablas/índices.

Evitar cachear permisos por largos períodos. Si se cachean, incluir versión de política por hotel/membership e invalidación inmediata tras cambios, revocaciones o salida del staff.

## 15. Data Warehouse y Data Marts

### 15.1 Objetivo

Separar analytics pesados del OLTP para proteger reservas/check-in/caja durante picos y habilitar análisis histórico consistente. El warehouse no participa en autorización ni decisiones transaccionales en tiempo real.

```text
PostgreSQL OLTP
   → CDC/outbox o cargas incrementales
   → staging/raw inmutable
   → transformaciones versionadas
   → Data Warehouse
       ├── Mart SaaS (proveedor, agregado)
       ├── Mart Hotel Operations (tenant-scoped)
       ├── Mart Revenue/Occupancy
       └── Mart Billing/Subscriptions
```

### 15.2 Reglas de diseño

- comenzar con facts/read models actuales si cubren la carga; no introducir warehouse prematuramente;
- cargas incrementales con watermark/idempotencia y reconciliación;
- dimensiones conformadas: hotel, fecha, plan, canal, habitación/categoría, sin duplicar PII innecesaria;
- SCD cuando se necesite historia de plan/configuración;
- freshness SLA explícito: no presentar datos batch como tiempo real;
- aislamiento por hotel también en marts y BI;
- catálogo, lineage, tests de calidad, totales reconciliados y alertas por lag;
- eliminación/retención propagada según política y obligaciones legales;
- el mart SaaS usa agregados/metadatos y evita movimientos privados del hotel.

BigQuery es una opción válida, no un mandato. Antes de elegirlo, comparar con la infraestructura real y volumen: PostgreSQL + materialized views, ClickHouse, Redshift, Snowflake u otra solución pueden ser mejores. La decisión debe documentar costo total, latencia, operación, residencia de datos, lock-in, integración y capacidad del equipo.

## 16. IA y autorización

La IA nunca recibe autoridad propia ni un atributo equivalente a `SUPERUSER`. Toda herramienta que pueda consultar o mutar datos debe entrar por los mismos servicios y controles que una acción humana:

```text
usuario → sesión → hotel → membership → entitlement → permiso → herramienta → servicio
```

Ejemplo: si un usuario pide “subí todas las tarifas un 10 %”, el modelo puede proponer o invocar `pricing.update`, pero el backend debe verificar `pricing.write`, el hotel y el alcance de cada recurso. Si el usuario carece del permiso, la respuesta es denegada aunque el modelo considere razonable la acción.

Además, el hotel debe tener habilitado el entitlement de IA correspondiente. Ser Owner no habilita una feature que el plan no incluye. Las acciones de IA deben ser acotadas, explicables, idempotentes cuando corresponda y auditadas con actor humano, herramienta, parámetros relevantes y resultado. El LLM no decide permisos ni ejecuta SQL directo.

## 17. Seguridad transversal

- secretos en un secret manager, nunca en Git/frontend/logs;
- cifrado en tránsito y reposo;
- rotación de claves y separación por ambiente;
- rate limits y detección de abuso en auth, invitaciones, MFA y aprobaciones;
- eventos de seguridad separados de audit de negocio cuando corresponda;
- backups con PITR y pruebas de restauración;
- protección de integraciones con scopes mínimos;
- dependencia/librería mantenida para Argon2id, OAuth/OIDC, TOTP y WebAuthn;
- threat model de account takeover, cross-tenant access, confused deputy, replay, CSRF, XSS, privilege escalation e insider abuse;
- Master Admin completamente separado del contexto de hotel y con MFA obligatorio;
- logs estructurados sin tokens, passwords, TOTP, recovery codes ni payloads sensibles.

### 17.1 Qué conservar propio y qué tercerizar

| Componente | Decisión objetivo |
|---|---|
| Usuarios, memberships y RBAC | Propio |
| Password auth y sesiones | Propio, con librerías/estándares maduros |
| Entitlements y audit logs | Propio |
| MFA TOTP | Propio sobre estándar |
| Passkeys | Propio sobre WebAuthn |
| Hashing y criptografía | Librerías mantenidas y capacidades del sistema operativo |
| Entrega de email | Proveedor externo reemplazable |
| SMS OTP | Evitar inicialmente salvo necesidad demostrada |
| PostgreSQL | Servicio administrado aceptable; los datos y contratos siguen siendo propios |
| TLS, DDoS y WAF | Proveedor cloud/infraestructura |
| Auditoría independiente y pentest | Tercero especializado antes del lanzamiento público |

No se busca eliminar toda dependencia externa, sino evitar dependencia comercial innecesaria en la identidad y autorización centrales y usar especialistas donde operar internamente sería menos seguro o eficiente.

### 17.2 Pentest previo al lanzamiento

Antes de aceptar hoteles reales, contratar una revisión independiente enfocada como mínimo en:

- Auth, MFA, recuperación y sesiones;
- RBAC, overrides y escalamiento de privilegios;
- aislamiento multi-hotel y acceso directo a objetos;
- invitaciones, OAuth linking y permisos temporales;
- APIs, pagos, integraciones y webhooks;
- Master Admin y accesos de soporte;
- exposición de PII, secretos y datos de huéspedes.

Los hallazgos críticos/altos deben corregirse y revalidarse antes del lanzamiento. Escaneos automáticos, tests internos o una certificación del proveedor cloud no sustituyen este pentest.

## 18. Plan de implementación recomendado

### Fase 0 — Descubrimiento y contratos

- inventariar modelos, rutas, servicios, frontend, migraciones y tests existentes;
- mapear el flujo real de auth, permisos, invitaciones, audit, master y suscripciones;
- identificar duplicaciones (incluidas versiones de suscripción/RBAC) y autoridad canónica;
- fijar amenazas, SLOs, volumen esperado y decisiones ADR;
- producir matriz `existente/parcial/faltante` sin implementar aún.

### Fase 1 — P0: confianza, identidad y aislamiento

- migración bcrypt→Argon2id compatible;
- sesiones revocables y dispositivos;
- hardening de registro/reset/verificación;
- MFA TOTP + recovery codes;
- MFA obligatorio para master.
- aislamiento multi-tenant y pruebas negativas exhaustivas;
- autorización backend y audit log de acciones críticas.

### Fase 2 — P0/P1: identidades externas y passkey-ready

- Google OIDC;
- Sign in with Apple;
- linking seguro de identidades;
- tablas/contratos WebAuthn y documentación Apple, sin forzar lanzamiento de passkeys.

### Fase 3 — P0/P1: autorización madura

- consolidar permisos efectivos y precedencia;
- evolucionar matriz UX respetando la captura;
- roles personalizados y, sólo si es necesario, overrides por persona;
- autorización temporal de una sola acción + step-up;
- cobertura backend de todos los endpoints sensibles.

### Fase 4 — P1: operación, staff, resiliencia y Master SaaS

- cerrar ciclo de invitaciones/memberships;
- audit del hotel consultable por Owner;
- panel master centrado en métricas, catálogo, contratos y ajustes;
- barreras de privacidad entre operación del hotel y administración SaaS.
- backups, restauración verificada, observabilidad e infraestructura de protección.

### Fase 5 — P2: performance y analítica

- benchmarks y optimización OLTP basada en evidencia;
- read models/facts/materialized views;
- diseñar pipeline incremental;
- introducir warehouse/marts sólo al superar umbrales acordados.

Cada fase debe poder desplegarse con feature flags/migraciones backward-compatible, rollback documentado y métricas.

La prioridad explícita es:

```text
P0  Auth, sesiones, tenant isolation, RBAC, audit, recovery y MFA
P1  Operación PMS, performance, backups, infraestructura y panel SaaS necesario
P2  Data Warehouse, Data Marts y analytics avanzado
P3  expansión de apps móviles y capacidades de IA no esenciales
```

La preparación técnica para passkeys/Face ID puede comenzar antes, pero no debe retrasar los controles P0. El Data Warehouse no tiene prioridad sobre una autorización y recuperación seguras.

## 19. Criterios de aceptación mínimos

- un usuario de Hotel A no puede leer ni modificar recursos, roles, auditoría o solicitudes de Hotel B;
- todo endpoint sensible verifica sesión, membership, entitlement y permiso en backend;
- cambiar una celda de la matriz altera sólo el hotel correcto, muestra Base/Override y queda auditado;
- una aprobación temporal sólo ejecuta la acción, recurso y parámetros aprobados, una vez y antes de vencer;
- Google/Apple se vinculan a una identidad interna sin duplicar ni secuestrar cuentas;
- un hash bcrypt válido se actualiza a Argon2id al autenticar sin reset obligatorio;
- MFA enrola, verifica, evita replay, recupera con códigos single-use y puede revocarse con step-up;
- sesiones se enumeran y revocan; password reset invalida las definidas por política;
- invitaciones vencen, se revocan, son idempotentes y respetan límites de staff;
- Owner consulta auditoría de su hotel; Master no recibe movimientos internos en su dashboard normal;
- planes/ajustes tienen vigencia, motivo, autor, historial y enforcement server-side;
- sólo el Primary Owner o un flujo explícitamente autorizado puede transferir propiedad, cancelar definitivamente o cambiar el responsable principal;
- ninguna herramienta de IA evita permisos, entitlements, scoping o auditoría del backend;
- el pentest independiente de pre-lanzamiento no conserva hallazgos críticos/altos sin remediar y revalidar;
- dashboards pesados no degradan el p95 de operaciones críticas por encima del presupuesto acordado;
- pipeline analítico reconcilia totales, informa freshness y mantiene aislamiento.

## 20. Entregables esperados del agente implementador

Antes de escribir código:

1. informe corto de estado actual por área;
2. diagrama del modelo vigente y objetivo;
3. amenazas y decisiones abiertas;
4. plan por migraciones pequeñas, tests y rollout;
5. lista explícita de lo que se reutiliza, adapta, depreca o elimina.

Durante la ejecución:

- migraciones reversibles o estrategia de forward-fix documentada;
- tests unitarios, integración, autorización negativa, concurrencia y E2E;
- mediciones antes/después para cambios de performance;
- documentación de operación, recuperación y configuración externa;
- ninguna credencial, token, PIN, OTP o PII real en fixtures/evidencias.

## 21. Decisiones abiertas que deben resolverse con evidencia

- cookies server-side completas vs access/refresh híbrido para web y futuros clientes móviles;
- mantener el esquema actual de defaults/overrides o converger con el RBAC histórico documentado;
- permitir múltiples roles y overrides personales en la primera versión;
- quién puede aprobar cada permiso temporal y límites máximos por acción;
- proveedor/operación de claves para secretos TOTP y credenciales OAuth;
- obligatoriedad y calendario de MFA para Owners;
- estrategia RLS compatible con el pool actual;
- retención y nivel de detalle de auditoría por plan/jurisdicción;
- modelo canónico entre implementaciones de suscripción existentes;
- umbrales cuantitativos que justifican warehouse y tecnología elegida;
- alcance iOS nativo, PWA y passkeys para el lanzamiento.
- modelo y recuperación del Primary Owner;
- alcance, proveedor y ventana del pentest externo previo al lanzamiento.

Cuando estas respuestas contradigan el runtime o contratos existentes, marcar `needs-verification` y no decidir silenciosamente. La prioridad es preservar seguridad, aislamiento multi-hotel, continuidad de servicio y libertad de evolución.

## 22. Trazabilidad con los puntos conversados

| Punto original | Cobertura en este documento |
|---|---|
| 1. Separar Auth, membership, permisos y plan | §3 |
| 2. Una identidad en varios hoteles | §4 |
| 3. Permisos granulares | §8.2 |
| 4. Excepciones por hotel/persona | §8.1 |
| 5–6. Autorización y backend como autoridad | §3–4 y §8 |
| 7–9. Auth propio, sesiones, dispositivos y cookies | §5 |
| 10–11. bcrypt→Argon2id y política de contraseñas | §6 |
| 12–14. MFA TOTP y recovery codes | §7 |
| 15. Passkeys, Face ID, Touch ID y Windows Hello | §11 |
| 16. Recuperación de contraseña | §5.3 |
| 17. Invitaciones | §10 |
| 18. Primary Owner | §10.1 |
| 19. Master Admin separado | §12.2–12.3 |
| 20. Audit log | §12.1 |
| 21. IA sometida a permisos | §16 |
| 22. Entitlements además de permisos | §3, §13 y §16 |
| 23. Modelo conceptual de datos | §14 |
| 24. Escala de miles de hoteles | §14–15 |
| 25. Qué desarrollar y qué tercerizar | §17.1 |
| 26. Pentest externo previo al lanzamiento | §17.2 |
| 27. Decisión y prioridades P0–P3 | §1 y §18 |
| Matriz de permisos de la captura | §8 |
| Permiso único aprobado con PIN/TOTP | §9 |
| Google y Apple | §5.1 y §18 |
| Panel SaaS, planes, descuentos y bonificaciones | §12.2 y §13 |
| Eficiencia de base de datos | §14 |
| Data Warehouse y Data Marts | §15 |
