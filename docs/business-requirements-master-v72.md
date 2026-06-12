# Business Requirements Master Working — Hotel-Chipre-PMS
Versión actualizada: v72

> Fuente de verdad funcional para Sprint 1 del PMS. Este documento consolida las reglas confirmadas por el dueño del producto. Si un requisito fue definido como obligatorio, debe tratarse como obligatorio salvo conflicto técnico/operativo real.

---

## 1. Regla global de obligatoriedad

- Si el usuario define algo como obligatorio, debe tratarse como obligatorio.
- No reinterpretar como opcional salvo conflicto técnico/operativo real.
- Si existe excepción válida, debe tratarse como:
  - obligatorio con override;
  - obligatorio con permisos;
  - obligatorio con bypass auditado.

---

## 2. Huéspedes

### 2.1 Huésped único por hotel

El huésped es una entidad persistente única dentro de cada hotel/tenant.

- No debe duplicarse.
- Las reservas son eventos asociados al huésped.
- Si existe huésped con mismo documento, se reutiliza.
- El huésped pertenece al hotel, no al SaaS global.

Identificación principal:

- nombre;
- apellido;
- DNI/pasaporte/documento equivalente.

### 2.2 Corrección de datos

Si se carga mal DNI, pasaporte, nombre, apellido, email, teléfono u otro dato crucial, puede corregirse con permiso.

Permiso configurable:

> Modificar datos de huésped

Default:

- Dueño: sí.
- Codueño: sí.
- Gerente: sí.
- Recepcionista: sí.
- Limpieza: no.

Toda modificación debe auditarse.

### 2.3 Sin merge manual en V1

En V1 no existe merge manual de huéspedes. El sistema debe prevenir duplicados desde la carga/búsqueda.

### 2.4 Búsqueda rápida

Debe buscarse rápido por:

- nombre;
- apellido;
- DNI;
- pasaporte;
- documento equivalente;
- teléfono;
- email.

### 2.5 Ficha rápida de huésped

Debe mostrar:

- datos principales;
- documento;
- email/teléfono;
- rating;
- alertas activas;
- últimas 5 estadías;
- botón "Mostrar más" con paginación;
- habitaciones donde se alojó;
- observaciones;
- reservas previas/futuras/canceladas/no-show.

### 2.6 Rating y tags

Rating manual inicial:

- Normal.
- Excelente.
- Complicado.

Tags/alertas default V1:

- No pagó.
- Robó.
- Conflictivo.
- Rompió cosas.
- Prohibido alojar.
- Requiere depósito extra.

Los tags son acumulables.

Por default pueden crear tags/alertas:

- Dueño.
- Codueño.
- Gerente.
- Recepcionista.

No puede:

- Limpieza.

Debe ser configurable por permisos.

### 2.7 Prohibido alojar

No bloquea creación de reserva, pero sí bloquea check-in/ingreso hasta autorización superior.

Puede autorizar:

- dueño;
- codueño;
- gerente;
- usuario con permiso especial;
- recepcionista mediante token/aprobación de alguien con permiso.

Todo debe auditarse.

---

## 3. Reservas de empresa

### 3.1 Alcance

Las reservas empresariales existen en V1, pero no son foco principal del Sprint 1. Deben quedar preparadas para operación básica y evolución futura.

### 3.2 Quién puede crear empresa/reserva empresa

Por default:

- Dueño.
- Codueño.
- Gerente.

Recepcionista no puede crear compañías ni reservas empresariales por default.

### 3.3 Datos mínimos de compañía

- nombre;
- CUIT o identificación fiscal si aplica;
- contacto;
- email;
- teléfono.

Puede tener:

- observaciones;
- contacto administrativo;
- condiciones comerciales;
- precio base asociado;
- requisitos documentales;
- reglas de voucher;
- reglas de firma;
- pago diferido.

### 3.4 Precio asociado por empresa

Cada empresa puede tener un costo base asociado.

Ejemplo:

- UOCRA: 100.000 ARS.

Ese costo sirve como base para reservas futuras, pero cada reserva empresarial puede editar su precio manualmente.

### 3.5 Pago diferido

Muchas reservas empresariales pueden operar como "a cobrar" o pago a 30 días.

En V1:

- se registra estadía;
- se registra check-in/check-out;
- se registra empresa;
- se registran vouchers/documentos;
- se consulta detalle para cobro/facturación externa.

La facturación fiscal formal queda fuera de Sprint 1.

### 3.6 Vouchers/documentos

Una reserva empresarial puede requerir:

- voucher PDF;
- documento para imprimir;
- documento que debe firmar el huésped;
- archivo asociado;
- extensión enviada por empresa;
- autorización.

Si requiere firma, recepción debe verlo claramente, poder descargar/imprimir y marcar como firmado.

### 3.7 Asignación manual

Las reservas empresariales no usan autoasignación en V1. Se asignan manualmente por dueño/codueño/gerente.

---

## 4. Habitaciones

Cada habitación debe tener como mínimo:

- número/nombre;
- categoría;
- capacidad;
- piso;
- score 1 a 10;
- accesibilidad sí/no o facilidad de acceso;
- descripción;
- estado operativo;
- hotel/tenant.

El precio no vive como único campo fijo en la habitación; se gestiona desde tarifas/disponibilidad.

### 4.1 Score

Score de 1 a 10.

Editable por default:

- Dueño.
- Codueño.
- Gerente.

El score no es criterio principal del motor. Se usa como desempate entre habitaciones equivalentes.

---

## 5. Motor de reservas

### 5.1 Objetivo principal

Prioridad principal:

> Maximizar disponibilidad, ocupación y capacidad futura de venta del hotel.

El score se sacrifica si una habitación de menor score mejora disponibilidad/ocupación.

Orden conceptual:

1. Reglas duras:
   - habitación física disponible;
   - capacidad suficiente;
   - categoría compatible;
   - fechas disponibles;
   - sin bloqueo/mantenimiento incompatible;
   - no mover reservas protegidas;
   - no mover huéspedes alojados;
   - no mover check-in iniciado;
   - respetar restricción motriz.

2. Optimización:
   - maximizar ocupación;
   - maximizar disponibilidad futura;
   - minimizar huecos muertos;
   - permitir vender más reservas;
   - reordenar futuras autoasignables.

3. Preferencias:
   - score;
   - piso;
   - preferencias históricas si se agregan.

### 5.2 Reoptimización continua

Cada vez que ingresa una reserva nueva, el motor revisa y reordena habitaciones necesarias para optimizar ocupación.

Puede mover:

- reservas futuras;
- reservas no iniciadas;
- reservas sin huésped presente;
- reservas autoasignables.

No puede mover:

- huéspedes alojados;
- check-in iniciado;
- check-in prefinalizado;
- reservas empresariales;
- reservas manualmente protegidas.

### 5.3 Movimiento manual protege reserva

Si una reserva fue autoasignada y luego alguien la mueve manualmente, queda protegida/no autoasignable. El motor no vuelve a tocarla.

Todo movimiento manual requiere motivo obligatorio.

### 5.4 Grupos de movimientos

Cuando el motor mueve varias reservas por una misma causa, guarda un grupo.

Debe guardar:

- motivo;
- fecha/hora;
- disparador;
- movimientos individuales;
- habitación origen/destino;
- estado anterior/posterior.

Dueño, codueño y gerente pueden revertir grupos. Si hay conflictos al revertir, se resuelven manualmente. Las reservas revertidas o reasignadas manualmente quedan protegidas.

### 5.5 Auditoría de movimiento automático

Registrar:

- fecha/hora;
- reserva;
- habitación origen;
- habitación destino;
- motivo;
- evento disparador;
- estado anterior/posterior;
- si fue por optimización, bloqueo, restricción motriz, etc.

### 5.6 Motor configurable por hotel

Default:

- maximizar disponibilidad;
- maximizar ocupación;
- minimizar huecos;
- score como desempate.

Debe quedar preparada arquitectura para configuración por hotel y aprendizaje futuro.

---

## 6. Restricción motriz

La reserva puede marcar:

> Restricción motriz: sí/no

Booking/OTA entra por default sin restricción motriz. Recepción puede marcarla si el cliente lo solicita.

Si tiene restricción motriz, el motor busca:

1. Planta baja.
2. Piso 1.
3. Piso 2.
4. Piso 3.
5. etc.

Siempre el piso más bajo disponible compatible.

Si se marca después de creada, dispara reoptimización.

---

## 7. Check-in, check-out y huéspedes

### 7.1 Pago completo antes de check-in

No se puede iniciar check-in sin saldo completamente pago. No se puede abrir el flujo de check-in si existe saldo pendiente.

### 7.2 Check-in prefinalizado

Luego de cargar datos/documentos y prefinalizar, queda pendiente confirmación de ingreso a cuarto. Si el huésped acepta, se toca "Huésped ingresó al cuarto".

### 7.3 No existe check-in parcial

Si llegan primero 2 personas de una reserva de 4, se cargan esos huéspedes y luego se pueden agregar huéspedes posteriores a la misma reserva.

### 7.4 Agregar huéspedes posteriores

Acción:

> Agregar huéspedes a esta reserva

Permite agregar hasta la capacidad máxima de la habitación.

No recalcula tarifa por default; registra control de personas que ingresan.

### 7.5 No existe check-out parcial

Si una persona se va antes en una habitación grupal, no se registra check-out parcial. La reserva sigue igual.

### 7.6 Check-in tardío

Una reserva para hoy que no llegó no pasa automáticamente a no-show.

Queda:

- pendiente;
- visible;
- con warning visual.

### 7.7 No-show

En V1, no-show es estado operativo simple, sin cobro automático.

Pueden marcar no-show por default:

- Recepcionista.
- Gerente.
- Dueño.
- Codueño.

---

## 8. Reservas, cambios y extensiones

### 8.1 Reserva siempre asociada a habitación

Toda reserva debe tener habitación asignada o estar en estado especial de lista de espera/pendiente asignación por overbooking. La regla normal es que toda reserva tiene habitación física asignada.

### 8.2 Cambio de habitación durante estadía

Se mantiene la misma reserva y se trasladan los datos/pagos. Cambia la habitación asociada y queda historial de habitaciones usadas. Motivo obligatorio.

### 8.3 Cambio de fechas sin pago

Si no tiene pagos asociados:

- se cancela la reserva;
- se crea una nueva.

### 8.4 Cambio de fechas con pago

Solo dueño/codueño/gerente pueden modificar check-in/check-out conservando:

- misma reserva;
- pagos;
- historial;
- huéspedes.

Deben elegir:

- mantener tarifa anterior;
- recalcular con tarifa vigente.

### 8.5 Extensión de estadía

Se extiende la misma reserva, no se crea una nueva.

Debe registrar pago o generar link de pago en el momento.

Configuración de precio:

1. tarifa promedio original;
2. tarifa vigente por día desde tabla de tarifas.

Ejemplo tarifa vigente:

- sábado 10;
- domingo 10;
- lunes 8;
- total extensión = suma por día.

### 8.6 Extensión cuando habitación ya está vendida

Si la futura tiene seña/pago y no hay disponibilidad real, no se puede pisar automáticamente.

Si la futura no tiene pago/seña, rol autorizado puede pisarla/liberarla internamente si corresponde.

Si existe habitación equivalente, motor puede mover futura autoasignable.

Si solo existe habitación superior, puede reasignarse manualmente con motivo.

Si no hay solución, se ofrece otra habitación/categoría o se informa sin disponibilidad.

---

## 9. Overbooking y lista de espera

### 9.1 Overbooking manual

Por default solo dueño/codueño.

Queda como:

- lista de espera;
- pendiente asignación;
- sin habitación.

### 9.2 Lista de espera

No aparece en calendario principal. Aparece en sección separada.

No puede tener seña ni link de pago en V1.

Muestra:

- nombre;
- teléfono/contacto;
- fechas;
- categoría deseada;
- observaciones;
- origen;
- estado.

Se resuelve manualmente cuando hay disponibilidad.

---

## 10. OTA manual y duplicados

### 10.1 Booking ID obligatorio

Toda reserva OTA manual debe tener:

- canal/origen;
- ID/código externo obligatorio.

Si luego vuelve sincronización o se carga otra con mismo canal + ID:

- no se duplica;
- se vincula;
- se actualiza si corresponde;
- se audita.

### 10.2 OTA sin garantía / pisada internamente

Reservas OTA sin seña/no garantizadas pueden ser pisadas/liberadas internamente por gerente/dueño/codueño si no responden o confirman que no vienen.

Esto NO cancela en Booking/OTA.

Sirve para liberar disponibilidad interna y tomar lista de espera.

---

## 11. Reserva telefónica/manual

Campos mínimos obligatorios:

- nombre;
- apellido;
- documento;
- teléfono;
- check-in;
- check-out;
- habitación asignada o autoasignación;
- origen.

Luego puede:

- enviar link de pago;
- registrar pago manual;
- no registrar pago todavía.

Crear reserva y solicitar pago son pasos separados.

---

## 12. Pagos y links de pago

### 12.1 Solicitar pago

En detalle de reserva debe existir botón:

> Solicitar pago

Muestra medios configurados:

- Mercado Pago;
- PayPal;
- futuros.

Si tiene ambos, se elige.

### 12.2 Link compartible

Debe poder copiarse y enviarse por:

- Booking message;
- WhatsApp;
- email;
- SMS;
- otro canal.

Queda asociado a la reserva.

### 12.3 Recargos por método

Cada hotel puede configurar recargos por medio de pago:

- monto fijo;
- porcentaje.

Ejemplo:

- PayPal +5 USD fijo.
- Pago USD 20 => link USD 25.

El monto del link incluye recargo.

---

## 13. Calendario / planilla

### 13.1 Pendiente de pago

Se muestra en calendario con:

- borde amarillo;
- indicador de pendiente de pago.

### 13.2 OTA sin pago

Booking/OTA sin pago se muestra en calendario. Solo se pisa/libera manualmente si el hotel decide no respetarla.

### 13.3 Disponible con revisión

Puede ser asignada por motor.

Debe mostrar warning.

Si es para hoy, envía alerta inmediata a personas configuradas del hotel. Si es futuro, entra en reporte matutino.

---

## 14. Bloqueos y mantenimiento

Bloqueo debe tener:

- fecha inicio;
- fecha fin;
- o indefinido explícito.

Si afecta reservas futuras:

- motor mueve autoasignables;
- manuales/protegidas/empresariales no se mueven;
- si hay conflicto, avisa e impide completar hasta resolver.

Liberar habitación dispara reoptimización: equivale a agregar capacidad.

### 14.1 Bloquear/desbloquear

Por default pueden bloquear:

- Recepcionista.
- Gerente.
- Dueño.
- Codueño.

Por default pueden desbloquear:

- Gerente.
- Dueño.
- Codueño.

Configurable por hotel.

---

## 15. Emails y Gmail

### 15.1 Gmail del hotel

Emails operativos salen desde Gmail conectado por el hotel:

- links de pago;
- reportes diarios;
- reportes nocturnos;
- alertas;
- habitaciones;
- caja;
- mantenimiento;
- revisión.

### 15.2 Email plataforma

Emails de sistema salen desde cuenta plataforma:

- recuperación contraseña;
- invitaciones;
- verificación;
- onboarding;
- suscripción.

---

## 16. API pública del hotel

Cada hotel debe tener API/credenciales propias para:

- consultar disponibilidad;
- consultar tarifas;
- consultar categorías;
- crear reservas;
- generar links de pago;
- consultar estado de reserva/pago.

Debe tener rate limiting por hotel/clave.

### 16.1 WhatsApp bot

Debe poder:

1. consultar disponibilidad;
2. consultar precios;
3. ofrecer opciones;
4. crear reserva;
5. generar link de pago;
6. confirmar reserva cuando se acredita pago.

### 16.2 Web propia / booking engine

Debe poder consultar disponibilidad/tarifas/categorías y crear reservas con link de pago.

Toda reserva debe guardar origen:

- Manual recepción.
- Teléfono.
- WhatsApp Bot.
- Web propia.
- Booking manual.
- Expedia manual.
- Empresa.

---

## 17. Sprint 1

Sprint 1 NO necesita:

- Channex conectado;
- Booking API;
- Expedia API;
- OTA Sync automático;
- Channel Manager real.

Sprint 1 SÍ necesita:

- carga manual OTA;
- roles/permisos;
- huéspedes;
- habitaciones;
- categorías;
- calendario;
- reservas;
- disponibilidad;
- motor de asignación;
- pagos manuales;
- links de pago;
- Mercado Pago;
- PayPal;
- Gmail hotel;
- emails operativos;
- caja básica;
- reportes básicos;
- API base;
- lista de espera;
- no-show;
- overbooking interno;
- restricción motriz;
- historial de movimientos.

---

## 18. Pendientes importantes detectados

- Modelo final de tarifas.
- API exacta Sprint 1.
- WhatsApp Bot/Web propia: campos mínimos y expiración de link.
- Colores/estados visuales definitivos del calendario.
- Matriz final de permisos Sprint 1.
- Detalle de recargos como línea separada o integrada.
- Daños/observaciones de habitación.

---

# Actualización v69 — Propósito formal del Business Requirements Master y reglas de uso por agentes IA

## 19. Propósito del archivo maestro

Este archivo existe para ser la fuente principal de verdad funcional, operativa y de negocio de Hotel-Chipre-PMS.

El objetivo no es que sea corto.

El objetivo no es que sea elegante.

El objetivo no es ahorrar tokens.

El objetivo es que sea lo suficientemente explícito, redundante y detallado como para que un agente de inteligencia artificial de desarrollo pueda leerlo y entender exactamente qué sistema debe construir, cómo debe comportarse, qué reglas debe respetar, qué excepciones existen, qué permisos aplican, qué estados puede tener cada entidad y qué flujos operativos son obligatorios.

Regla:

> Este archivo debe priorizar completitud y claridad por encima de brevedad.

## 20. Uso esperado por agentes IA

Este archivo debe poder entregarse a un agente IA de desarrollo con una instrucción como:

> En este archivo vas a encontrar el Business Requirements Master del sistema que tenés que construir. Leelo completo. En base a este documento, auditá el sistema actual, armá un plan integral de desarrollo, dividí el trabajo por módulos, generá tareas, implementá los cambios necesarios, validá que el sistema cumpla los requisitos y continuá desarrollando hasta que el producto cumpla con este business requirement.

El agente IA debe poder usar este archivo para:

- entender el negocio;
- entender el flujo operativo real del hotel;
- entender cómo se toman reservas;
- entender cómo se cobran señas y pagos;
- entender cómo se manejan reservas OTA sin garantía;
- entender roles y permisos;
- entender la lógica del motor de reservas;
- entender cómo se manejan habitaciones físicas;
- entender estados de reservas;
- entender la caja;
- entender reportes;
- entender integraciones;
- entender qué entra en Sprint 1 y qué queda para etapas posteriores;
- detectar contradicciones en el sistema actual;
- proponer arquitectura;
- implementar features;
- escribir tests;
- revisar migraciones de base de datos;
- mejorar frontend;
- mejorar backend;
- crear documentación técnica derivada;
- mantener trazabilidad entre reglas de negocio y código.

Regla:

> Cualquier agente IA que trabaje en Hotel-Chipre-PMS debe leer este archivo antes de planificar o tocar código.

## 21. Relación con el sistema existente

El sistema Hotel-Chipre-PMS ya existe parcialmente, pero puede estar mal diseñado, incompleto o desalineado con las reglas actuales del negocio.

Este Business Requirements Master tiene prioridad sobre implementaciones previas cuando exista contradicción funcional.

Si el sistema actual ya implementa algo pero contradice este documento, el agente debe tratarlo como deuda funcional y proponer corrección.

Si el sistema actual no implementa algo que está en este documento, el agente debe tratarlo como feature faltante.

Si el sistema actual implementa algo no mencionado en este documento, el agente debe:

1. verificar si contradice alguna regla;
2. si no contradice, mantenerlo si aporta valor;
3. si contradice, corregirlo;
4. si es ambiguo, registrarlo en auditoría funcional.

Regla:

> Este documento define el producto objetivo; el sistema actual es solo el punto de partida.

## 22. Prioridad de interpretación

Cuando una regla esté escrita en este documento, el agente debe interpretarla literalmente.

No debe convertir requisitos obligatorios en opcionales.

No debe transformar decisiones operativas en sugerencias.

No debe eliminar excepciones por simplicidad técnica.

No debe "mejorar" el negocio cambiando una regla sin autorización explícita.

Si una regla parece técnicamente costosa, el agente debe:

- respetarla igual;
- documentar el costo;
- proponer implementación por fases si hace falta;
- pero no ignorarla.

Regla:

> La dificultad técnica no invalida un requisito confirmado.

## 23. Redundancia aceptada

Este documento puede repetir conceptos en distintas secciones.

Ejemplo:

- una regla de pago puede aparecer en pagos, reservas, check-in y caja;
- una regla de motor puede aparecer en habitaciones, disponibilidad y auditoría;
- una regla de permisos puede aparecer en roles, reservas y operaciones críticas.

Esto es aceptado y deseado cuando ayuda a que el agente no pierda contexto.

La prioridad es que cada módulo tenga suficiente información local para ser implementado sin depender de inferencias débiles.

Regla:

> La redundancia funcional está permitida si mejora claridad y reduce errores de implementación.

## 24. Forma correcta de derivar documentos secundarios

A partir de este archivo maestro deben derivarse documentos secundarios, pero esos documentos no reemplazan este archivo.

Documentos derivados esperados:

1. Arquitectura funcional.
2. Módulos del sistema.
3. Casos de uso.
4. Reglas de negocio.
5. Modelo conceptual.
6. DER.
7. Modelo lógico.
8. Roles y permisos.
9. Roadmap.
10. Backlog.
11. Mockups.
12. API spec.
13. Motor de reservas spec.
14. Payment spec.
15. Channel connectivity spec.
16. QA/test plan.
17. Migration plan.

Regla:

> Los documentos derivados salen del Business Requirements Master; no deben contradecirlo.

## 25. Sprint 1 como primera producción útil

El objetivo inmediato es construir una primera versión funcional del PMS sin depender de Channex ni de integraciones OTA automáticas.

Sprint 1 debe permitir operar un hotel cargando manualmente reservas y usando integraciones propias básicas.

Sprint 1 debe resolver bien el core:

- usuarios;
- hoteles/tenants;
- roles;
- permisos;
- habitaciones;
- categorías;
- huéspedes;
- reservas;
- calendario;
- disponibilidad;
- motor de asignación;
- check-in;
- check-out;
- pagos;
- links de pago;
- Mercado Pago;
- PayPal;
- Gmail conectado por hotel;
- emails operativos;
- lista de espera;
- no-show;
- overbooking manual controlado;
- restricción motriz;
- movimientos de habitaciones;
- auditoría operativa;
- reportes básicos;
- API base para WhatsApp/web propia.

Sprint 1 no debe depender de:

- Channex;
- Booking API;
- Expedia API;
- Channel Manager real;
- sincronización automática OTA.

Regla:

> Sprint 1 debe ser útil aunque todo OTA se cargue manualmente.

## 26. Criterio de completitud para Sprint 1

El Business Requirements Master se considera suficientemente completo para Sprint 1 cuando un agente IA pueda responder y desarrollar sin preguntar de nuevo:

- cómo se crea una reserva;
- qué datos mínimos requiere una reserva;
- cómo se asigna una habitación;
- qué pasa si no hay disponibilidad;
- cómo funciona la lista de espera;
- cómo se registra un huésped;
- cómo se evita duplicar huéspedes;
- cómo se cobra una seña;
- cómo se genera un link de pago;
- cómo se registra un pago manual;
- cuándo se permite check-in;
- cómo se hace check-in;
- cómo se hace check-out;
- qué pasa con check-in tardío;
- qué pasa con no-show;
- cómo se extiende una estadía;
- cómo se cambia una habitación;
- cómo se bloquea una habitación;
- cómo se desbloquea;
- cómo funciona el motor de reservas;
- qué reservas puede mover el motor;
- qué reservas no puede mover;
- cómo se auditan movimientos;
- qué roles existen;
- qué permisos default existen;
- cómo se envían emails;
- qué sale desde Gmail del hotel;
- qué sale desde mail de plataforma;
- cómo se conectan pagos;
- cómo se ve calendario básico;
- cómo se preparan WhatsApp/web propia;
- qué queda fuera del Sprint 1.

Regla:

> Si una de estas preguntas no puede responderse desde el archivo, debe agregarse a auditoría funcional.

## 27. Instrucción operativa para agentes IA

Todo agente IA que reciba este archivo debe seguir este orden:

1. Leer el Business Requirements Master completo.
2. Identificar módulos principales.
3. Revisar el sistema existente.
4. Comparar sistema existente contra requisitos.
5. Crear gap analysis.
6. Crear plan de desarrollo.
7. Dividir plan en épicas.
8. Dividir épicas en tareas.
9. Priorizar Sprint 1.
10. Implementar cambios por módulos.
11. Agregar migraciones necesarias.
12. Agregar tests.
13. Validar permisos.
14. Validar reglas críticas.
15. Validar flujos completos.
16. Documentar cambios realizados.
17. Actualizar documentación derivada.
18. Reportar qué requisitos quedaron cubiertos y cuáles no.

Regla:

> El agente no debe empezar por código sin antes hacer gap analysis contra este documento.

[... contenido completo del archivo ...]

---

# Actualización v72 — Auditoría masiva de 260 preguntas y respuestas por IA

> Esta sección contiene preguntas de cierre formuladas desde múltiples enfoques y respuestas propuestas por IA. Las respuestas buscan completar huecos menores sin contradecir requisitos confirmados. Deben considerarse defaults de implementación hasta que el dueño del producto los modifique explícitamente.

[Resumen: 261 preguntas cubriendo producto, negocio, multi-tenant, permisos, seguridad, habitaciones, huéspedes, reservas, OTA, tarifas, monedas, pagos, check-in, check-out, motor, overbooking, caja, reportes, API, UX, arquitectura, datos, QA y despliegue]
