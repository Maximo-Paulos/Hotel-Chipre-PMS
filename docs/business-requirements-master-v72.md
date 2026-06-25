# Business Requirements Master Working — Hotel-Chipre-PMS
Versión actualizada: v68

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
- botón “Mostrar más” con paginación;
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

Muchas reservas empresariales pueden operar como “a cobrar” o pago a 30 días.

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

Luego de cargar datos/documentos y prefinalizar, queda pendiente confirmación de ingreso a cuarto. Si el huésped acepta, se toca “Huésped ingresó al cuarto”.

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

No debe “mejorar” el negocio cambiando una regla sin autorización explícita.

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

## 28. No depender de memoria conversacional

Este archivo debe contener las reglas.

No se debe depender de memoria del chat.

No se debe depender de que el agente “se acuerde”.

No se debe depender de contexto externo no pegado en el repo.

Si una regla importa, debe estar escrita acá.

Regla:

> Lo que no está en el Business Requirements Master no debe considerarse requisito confirmado.

## 29. Reglas de actualización futura del documento

Cada vez que el dueño del producto aclare una regla nueva:

1. Se agrega al Business Requirements Master.
2. Se revisa si contradice reglas anteriores.
3. Si contradice, se actualiza la regla anterior o se marca como reemplazada.
4. Se actualiza la auditoría funcional.
5. Se eliminan preguntas ya resueltas.
6. Se agregan nuevas dudas si aparecen.
7. Se genera nueva versión descargable.

Regla:

> El Business Requirements Master y la auditoría funcional deben evolucionar juntos.

## 30. Nivel de detalle requerido

Este documento debe explicar:

- qué se hace;
- quién puede hacerlo;
- cuándo se puede hacer;
- cuándo no se puede hacer;
- qué pasa si falla;
- qué pasa si hay conflicto;
- qué queda auditado;
- qué estado cambia;
- qué entidad se modifica;
- qué ve el usuario;
- qué se notifica;
- qué queda pendiente;
- qué es configurable;
- cuál es el default;
- qué queda para futuro.

Regla:

> Cada requisito importante debe incluir regla, default, permisos, auditoría y comportamiento esperado.

## 31. Filosofía del producto

Hotel-Chipre-PMS no es solo una planilla digital.

Debe funcionar como sistema operativo del hotel.

Debe ayudar a:

- ordenar reservas;
- evitar sobreventas;
- evitar errores de caja;
- controlar huéspedes;
- controlar habitaciones;
- auditar acciones;
- centralizar pagos;
- enviar reportes;
- reducir dependencia de memoria humana;
- permitir operar incluso si OTA/Channex no están conectados;
- preparar evolución futura hacia automatización OTA, WhatsApp, web booking engine e inteligencia de asignación.

Regla:

> El PMS debe modelar la operación real del hotel, no una operación idealizada simplificada.

## 32. Resultado esperado del agente de producción

Cuando se entregue este archivo a un agente de producción, el resultado esperado no es solo “leerlo”.

El agente debe producir:

- plan de desarrollo;
- arquitectura propuesta;
- lista de módulos;
- entidades de base de datos;
- migraciones;
- endpoints;
- pantallas;
- permisos;
- flujos;
- pruebas;
- validaciones;
- backlog;
- roadmap;
- reporte de cumplimiento.

Regla:

> El agente debe convertir este Business Requirements Master en producto funcional verificable.



---

# Actualización v70 — Tarifas, Caja, Monedas y Criterios finales del motor

## 33. Modelo de tarifas

### 33.1 Tarifas por categoría

En Sprint 1 las tarifas se gestionan por categoría y no por habitación individual.

Ejemplos:

- Doble baño privado.
- Doble baño compartido.
- Triple baño privado.
- Cuádruple baño privado.

Las habitaciones heredan la tarifa de su categoría.

### 33.2 Calendario de tarifas

La interfaz debe funcionar de forma similar al calendario de tarifas de Booking.

Características:

- calendario continuo;
- navegación infinita hacia adelante;
- filtrado por categoría;
- edición masiva por rango de fechas;
- edición por día de semana;
- soporte para temporadas y fines de semana.

### 33.3 Fuente de precio

Cuando se genera una reserva:

- el precio proviene de la tabla de tarifas;
- no proviene de la habitación individual.

Regla:

> En Sprint 1 el precio vive en la categoría y en el calendario tarifario.

## 34. Capacidad y menores

### 34.1 Menores

- Menores de 4 años no consumen capacidad.
- Desde los 4 años inclusive consumen capacidad completa.

Ejemplo:

Habitación doble:

- padre;
- madre;
- hijo de 3 años.

Capacidad utilizada: 2.

Habitación doble:

- padre;
- madre;
- hijo de 4 años.

Capacidad utilizada: 3.

## 35. Caja operativa

### 35.1 Caja única

No existe caja por turno.

Existe una única caja operativa que acumula movimientos hasta el cierre.

### 35.2 Cobros por usuario

Cada cobro queda asociado al usuario autenticado que lo registró.

Debe registrarse:

- usuario;
- fecha;
- hora;
- reserva;
- importe;
- método de pago.

### 35.3 Cierre de caja

El cierre debe mostrar:

- total caja;
- ingresos;
- egresos;
- ajustes;
- faltantes;
- sobrantes;
- detalle por usuario.

Ejemplo:

- Lucas: 70.000 ARS.
- Máximo: 30.000 ARS.

Total caja: 100.000 ARS.

## 36. Caja mensual

### 36.1 Concepto

La caja mensual es una consolidación de todas las cajas cerradas dentro de un período mensual.

No reemplaza las cajas individuales.

### 36.2 Contenido

Debe incluir:

- total facturación;
- total ingresos;
- total egresos;
- faltantes;
- sobrantes;
- compras registradas;
- historial de cajas incluidas;
- usuarios involucrados.

### 36.3 Exportación

Formatos:

- PDF.
- CSV.

La exportación se genera bajo demanda.

No se generan archivos automáticamente.

### 36.4 Auditoría de exportación

Registrar:

- usuario;
- fecha;
- hora;
- tipo de archivo;
- período exportado.

### 36.5 Permisos

Permiso:

> Acceso caja mensual

Default:

- Dueño.
- Codueño.

### 36.6 Recalculo

Si una caja histórica se modifica:

- recalcular indicadores;
- recalcular caja mensual;
- recalcular reportes financieros.

El proceso puede ejecutarse en segundo plano.

## 37. Monedas

### 37.1 Sprint 1

Monedas soportadas:

- ARS.
- USD.

### 37.2 Conversión configurable

Cada hotel puede seleccionar:

- dólar compra;
- dólar venta;
- oficial;
- MEP;
- blue;
- tarjeta;
- otra cotización disponible.

Regla:

> El hotel puede elegir la referencia de conversión que utilizará.

## 38. Desempates finales del motor

Cuando existen soluciones equivalentes:

Orden de prioridad:

1. Menor cantidad de movimientos.
2. Mantener asignaciones/historial previo cuando sea posible.
3. Score de habitación.
4. Otros criterios secundarios configurables.

## 39. Protección por movimiento manual

Si una reserva fue movida manualmente:

- deja de ser autoasignable;
- el motor no vuelve a moverla;
- queda protegida hasta intervención manual futura.

Regla:

> Un movimiento manual transforma la reserva en protegida.

## 40. Estado del Business Requirements

Con la información disponible actualmente, el Sprint 1 posee definición funcional suficiente para iniciar planificación técnica, auditoría del repositorio existente y desarrollo guiado por agentes IA.


---

# Actualización v71 — Supuestos de cierre para desarrollo (IA)

## Objetivo

Esta sección contiene decisiones tomadas por IA para cerrar huecos funcionales menores que no bloquean el desarrollo.

Todas estas decisiones pueden modificarse en versiones futuras, pero permiten iniciar construcción sin detener el proyecto.

## 41. Convenciones generales

### 41.1 Timezone

Default:

- America/Argentina/Buenos_Aires

Todas las auditorías guardan:

- fecha UTC;
- fecha local del hotel.

### 41.2 Soft delete

No se eliminan registros críticos.

Se utilizan estados:

- activo;
- inactivo;
- cancelado;
- archivado.

## 42. Auditoría

Toda acción crítica debe registrar:

- usuario;
- fecha;
- hora;
- entidad afectada;
- valor anterior;
- valor nuevo;
- motivo si corresponde.

Aplica a:

- reservas;
- huéspedes;
- habitaciones;
- pagos;
- movimientos;
- bloqueos;
- permisos;
- configuraciones.

## 43. Estados mínimos de reserva

Estados mínimos Sprint 1:

- Draft.
- Pendiente pago.
- Confirmada.
- Check-in pendiente.
- Check-in iniciado.
- Alojado.
- Check-out realizado.
- Cancelada.
- No Show.
- Lista de espera.
- Pendiente asignación.

## 44. Estados mínimos de habitación

- Disponible.
- Reservada.
- Ocupada.
- Limpieza pendiente.
- Fuera de servicio.
- Bloqueada.
- Mantenimiento.

## 45. Concurrencia

La fuente de verdad es la base de datos.

Si dos actores intentan tomar la última disponibilidad:

gana:

1. pago confirmado;
2. transacción confirmada en base de datos.

## 46. API pública del hotel

Sprint 1 debe dejar preparada API para:

- disponibilidad;
- categorías;
- tarifas;
- crear reserva;
- consultar reserva;
- generar link de pago.

Destinos previstos:

- WhatsApp.
- Sitio web.
- Aplicaciones futuras.

## 47. Integraciones

Sprint 1:

- Gmail.
- Mercado Pago.
- PayPal.

Preparado para:

- Chanex.
- Booking.
- Expedia.
- WhatsApp.

## 48. Diseño multi-tenant

Todo dato pertenece a un hotel.

Ningún hotel puede acceder a:

- huéspedes;
- reservas;
- pagos;
- habitaciones;
- configuraciones;

de otro hotel.

## 49. Rendimiento

Objetivo operativo:

- búsquedas de huésped menores a 1 segundo;
- apertura de calendario menor a 2 segundos;
- creación de reserva menor a 3 segundos.

## 50. Arquitectura recomendada

La IA de desarrollo puede utilizar:

- PostgreSQL como fuente principal.
- Redis para cache.
- MongoDB o Cassandra para analítica/eventos si aporta valor.

No se autoriza duplicar lógica de negocio entre motores.

PostgreSQL permanece como fuente de verdad.

## 51. Supuestos aprobados por IA

Si una situación no está explícitamente documentada:

priorizar:

1. evitar pérdida de datos;
2. evitar sobreventa;
3. preservar auditoría;
4. preservar trazabilidad;
5. maximizar ocupación del hotel;
6. minimizar intervención manual.

## 52. Criterio de cierre Sprint 1

El Sprint 1 se considera funcionalmente completo cuando permite:

- administrar habitaciones;
- administrar huéspedes;
- administrar reservas;
- administrar pagos;
- check-in;
- check-out;
- extensiones;
- motor de asignación;
- lista de espera;
- reservas OTA manuales;
- reservas empresa básicas;
- Gmail;
- Mercado Pago;
- PayPal;
- roles y permisos;
- auditoría completa.



---

# Actualización v72 — Auditoría masiva de 260 preguntas y respuestas por IA

> Esta sección contiene preguntas de cierre formuladas desde múltiples enfoques y respuestas propuestas por IA. Las respuestas buscan completar huecos menores sin contradecir requisitos confirmados. Deben considerarse defaults de implementación hasta que el dueño del producto los modifique explícitamente.

## A. Alcance, producto y gobernanza

### Q1. ¿Cuál es la fuente de verdad funcional del producto?

**Respuesta IA:** Este Business Requirements Master es la fuente de verdad funcional. El código existente, mockups y documentos derivados deben alinearse a él.

### Q2. ¿Qué ocurre si el sistema actual contradice este documento?

**Respuesta IA:** Se considera deuda funcional. Debe documentarse el gap y corregirse mediante plan de migración.

### Q3. ¿Quién puede modificar requisitos confirmados?

**Respuesta IA:** El dueño del producto o una decisión explícitamente aprobada por él.

### Q4. ¿Cómo se diferencian requisitos confirmados de supuestos IA?

**Respuesta IA:** Los supuestos IA se agrupan en una sección separada y deben poder reemplazarse sin reescribir decisiones confirmadas.

### Q5. ¿Qué prioridad tiene Sprint 1?

**Respuesta IA:** Operación hotelera real, estable y testeable sin depender de Channex ni OTA Sync.

### Q6. ¿Qué módulos pueden posponerse?

**Respuesta IA:** Integraciones OTA automáticas, analítica avanzada, IA adaptativa, facturación fiscal completa y automatizaciones secundarias.

### Q7. ¿Se permite eliminar una función existente no mencionada?

**Respuesta IA:** No automáticamente. Primero se audita si aporta valor, si contradice requisitos y si tiene usuarios o datos dependientes.

### Q8. ¿Qué significa terminado para una funcionalidad?

**Respuesta IA:** Implementada, probada, auditada, autorizada por permisos, documentada y validada en flujo end-to-end.

### Q9. ¿Cómo se manejan contradicciones internas del documento?

**Respuesta IA:** Prevalece la regla más reciente y más específica; la anterior debe marcarse como reemplazada.

### Q10. ¿Debe el agente IA pedir confirmación antes de cada cambio?

**Respuesta IA:** No. Debe trabajar autónomamente dentro de los requisitos, pero registrar decisiones técnicas y riesgos.

## B. Multi-tenant y aislamiento de datos

### Q11. ¿Cada hotel es un tenant aislado?

**Respuesta IA:** Sí. Todo dato operativo debe estar asociado a un hotel/tenant.

### Q12. ¿Un usuario puede pertenecer a más de un hotel?

**Respuesta IA:** Sí, si es invitado explícitamente a cada hotel, con roles y permisos independientes.

### Q13. ¿Un huésped puede verse entre hoteles?

**Respuesta IA:** No. La entidad huésped es aislada por hotel.

### Q14. ¿Puede una reserva cruzar hoteles?

**Respuesta IA:** No. Una reserva pertenece a un único hotel.

### Q15. ¿Las configuraciones de tarifas son por hotel?

**Respuesta IA:** Sí.

### Q16. ¿Las integraciones Gmail, Mercado Pago y PayPal son por hotel?

**Respuesta IA:** Sí, salvo credenciales de plataforma para emails de sistema.

### Q17. ¿Cómo se evita fuga de datos entre tenants?

**Respuesta IA:** Filtrado obligatorio por tenant_id en backend, políticas de autorización y pruebas automatizadas de aislamiento.

### Q18. ¿Puede el platform admin ver datos de hoteles?

**Respuesta IA:** Solo si su rol de plataforma lo permite y toda visualización queda auditada.

### Q19. ¿Se permite compartir catálogos entre hoteles?

**Respuesta IA:** Solo como plantillas copiables, nunca como registros operativos compartidos.

### Q20. ¿Qué pasa si un usuario cambia de hotel activo?

**Respuesta IA:** La UI y API deben cambiar explícitamente de contexto y limpiar caches del tenant anterior.

## C. Usuarios, roles y permisos

### Q21. ¿Cuáles son los roles default?

**Respuesta IA:** Dueño, Codueño, Gerente, Recepcionista y Limpieza.

### Q22. ¿El dueño tiene todos los permisos?

**Respuesta IA:** Sí, por default y sin posibilidad de dejar el hotel sin al menos un dueño funcional.

### Q23. ¿Los roles pueden personalizarse?

**Respuesta IA:** Sí, especialmente en planes superiores, sin romper los roles base.

### Q24. ¿Los permisos deben ser granulares?

**Respuesta IA:** Sí: ver, crear, editar, aprobar, cancelar, exportar y administrar.

### Q25. ¿Puede un recepcionista ver tarifas?

**Respuesta IA:** Solo si el permiso correspondiente está habilitado.

### Q26. ¿Puede un recepcionista cambiar tarifas?

**Respuesta IA:** No por default. Requiere permiso explícito y, si aplica, aprobación.

### Q27. ¿Puede Limpieza cambiar estados de habitación?

**Respuesta IA:** Sí por default para estados operativos de limpieza, configurable.

### Q28. ¿Quién puede configurar integraciones?

**Respuesta IA:** Dueño y codueño por default; gerente solo con permiso.

### Q29. ¿Quién puede invitar usuarios?

**Respuesta IA:** Dueño y codueño por default; gerente con permiso.

### Q30. ¿Toda modificación de permisos queda auditada?

**Respuesta IA:** Sí, incluyendo actor, cambio anterior, cambio nuevo y fecha.

## D. Autorizaciones, tokens y acciones críticas

### Q31. ¿Qué acciones requieren aprobación superior?

**Respuesta IA:** Devoluciones, cambios tarifarios sensibles, cierres con diferencias, pisar reservas, modificar permisos y acciones configuradas como críticas.

### Q32. ¿El token es reutilizable?

**Respuesta IA:** No. Es de un solo uso y asociado a una acción concreta.

### Q33. ¿Cuánto dura un token?

**Respuesta IA:** Default IA: 2 minutos, configurable dentro de límites de seguridad.

### Q34. ¿El token por sí solo ejecuta la acción?

**Respuesta IA:** No siempre. Puede habilitar acceso o crear una solicitud que un superior aprueba.

### Q35. ¿Quién puede generar/aprobar tokens?

**Respuesta IA:** Dueño, codueño, gerente o rol con permiso específico.

### Q36. ¿La aprobación ejecuta automáticamente la acción?

**Respuesta IA:** Sí cuando la solicitud fue creada con parámetros completos y la acción sigue siendo válida.

### Q37. ¿Qué pasa si cambian los datos antes de aprobar?

**Respuesta IA:** La solicitud se invalida y debe recrearse.

### Q38. ¿Debe verse quién pidió y quién aprobó?

**Respuesta IA:** Sí.

### Q39. ¿Puede aprobarse desde móvil/PWA?

**Respuesta IA:** Sí.

### Q40. ¿Qué ocurre con solicitudes vencidas?

**Respuesta IA:** Quedan expiradas, auditadas y no ejecutables.

## E. Habitaciones y categorías

### Q41. ¿La categoría define capacidad y tarifa base?

**Respuesta IA:** Sí.

### Q42. ¿La habitación tiene precio propio en V1?

**Respuesta IA:** No. Hereda tarifa de categoría.

### Q43. ¿La habitación tiene score?

**Respuesta IA:** Sí, de 1 a 10.

### Q44. ¿El piso es obligatorio?

**Respuesta IA:** Sí.

### Q45. ¿La accesibilidad es obligatoria?

**Respuesta IA:** Sí como atributo simple en V1.

### Q46. ¿Se permiten atributos personalizados?

**Respuesta IA:** Sí, como metadata configurable y no destructiva.

### Q47. ¿Puede cambiarse la categoría de una habitación?

**Respuesta IA:** Sí, con validación de reservas futuras afectadas y auditoría.

### Q48. ¿Qué pasa con tarifas al cambiar categoría?

**Respuesta IA:** La habitación hereda la nueva categoría desde la fecha efectiva configurada.

### Q49. ¿Puede una habitación quedar inactiva?

**Respuesta IA:** Sí, sin eliminar historial.

### Q50. ¿Se puede borrar una habitación con historial?

**Respuesta IA:** No. Debe archivarse.

## F. Estados de habitación y mantenimiento

### Q51. ¿Estados mínimos?

**Respuesta IA:** Disponible, Reservada, Ocupada, Requiere limpieza, Disponible con revisión, Mantenimiento y Bloqueada.

### Q52. ¿Mantenimiento bloquea venta por default?

**Respuesta IA:** Sí.

### Q53. ¿Disponible con revisión puede venderse?

**Respuesta IA:** Sí, con warning.

### Q54. ¿Bloqueo requiere fecha fin?

**Respuesta IA:** Puede tener fecha fin o ser indefinido explícito.

### Q55. ¿Qué ocurre con reservas autoasignables al bloquear?

**Respuesta IA:** El motor intenta reubicarlas automáticamente.

### Q56. ¿Qué ocurre con reservas protegidas al bloquear?

**Respuesta IA:** El bloqueo no se confirma hasta resolverlas manualmente.

### Q57. ¿Quién puede desbloquear por default?

**Respuesta IA:** Dueño, codueño y gerente.

### Q58. ¿Se registra quién cambió estado?

**Respuesta IA:** Sí.

### Q59. ¿Se puede adjuntar foto al marcar limpia?

**Respuesta IA:** Sí; opcional por default, configurable como obligatoria.

### Q60. ¿Se puede indicar necesidad de mantenimiento al limpiar?

**Respuesta IA:** Sí, con detalle obligatorio si se marca.

## G. Huéspedes e identidad

### Q61. ¿Cuál es la clave funcional de deduplicación?

**Respuesta IA:** Tipo de documento + número dentro del hotel.

### Q62. ¿Qué pasa si no hay documento?

**Respuesta IA:** Para reservas manuales Sprint 1 es obligatorio; para excepciones futuras se requerirá override auditado.

### Q63. ¿El teléfono identifica un huésped?

**Respuesta IA:** Es dato auxiliar, no identificador único.

### Q64. ¿Puede cambiarse el documento?

**Respuesta IA:** Sí con permiso y auditoría.

### Q65. ¿Se guarda historial de cambios de identidad?

**Respuesta IA:** Sí.

### Q66. ¿Puede haber múltiples contactos?

**Respuesta IA:** Sí, pero uno principal.

### Q67. ¿El rating se calcula automáticamente?

**Respuesta IA:** No en V1.

### Q68. ¿Las alertas caducan?

**Respuesta IA:** Pueden tener fecha de expiración opcional; por default permanecen activas hasta desactivación.

### Q69. ¿Quién puede desactivar una alerta?

**Respuesta IA:** Usuario con permiso específico.

### Q70. ¿El huésped puede pedir eliminación de datos?

**Respuesta IA:** Debe contemplarse flujo legal de anonimización cuando corresponda, preservando datos contables y auditoría obligatoria.

## H. Reservas y estados

### Q71. ¿Estados mínimos de reserva?

**Respuesta IA:** Borrador, Pendiente pago, Confirmada, Check-in pendiente, Check-in iniciado, Alojado, Check-out realizado, Cancelada, No-show, Lista de espera, Pendiente asignación y Liberada internamente.

### Q72. ¿Toda reserva normal requiere habitación?

**Respuesta IA:** Sí.

### Q73. ¿Lista de espera requiere habitación?

**Respuesta IA:** No.

### Q74. ¿Reserva empresa usa motor?

**Respuesta IA:** No en V1.

### Q75. ¿Una reserva puede tener múltiples huéspedes?

**Respuesta IA:** Sí.

### Q76. ¿Una reserva puede cambiar de habitación?

**Respuesta IA:** Sí conservando la misma reserva.

### Q77. ¿Se permite duplicar reserva OTA?

**Respuesta IA:** No si coincide canal + external_id.

### Q78. ¿Una reserva directa sin pago puede existir?

**Respuesta IA:** Sí, según configuración de bloqueo/garantía.

### Q79. ¿Se guarda origen?

**Respuesta IA:** Sí, siempre.

### Q80. ¿Puede cancelarse físicamente un registro?

**Respuesta IA:** No. Se cambia estado y se audita.

## I. Creación manual y telefónica

### Q81. ¿Campos mínimos?

**Respuesta IA:** Nombre, apellido, documento, teléfono, fechas, origen y habitación/asignación.

### Q82. ¿El email es obligatorio?

**Respuesta IA:** No por default si existe teléfono; requerido si se enviará link por email.

### Q83. ¿Se puede crear sin pago?

**Respuesta IA:** Sí.

### Q84. ¿Se puede generar link después?

**Respuesta IA:** Sí.

### Q85. ¿Puede elegirse autoasignar o asignar manualmente?

**Respuesta IA:** Sí.

### Q86. ¿Asignar manualmente protege la reserva?

**Respuesta IA:** Sí.

### Q87. ¿Debe indicarse motivo al asignar manualmente?

**Respuesta IA:** Sí.

### Q88. ¿Puede marcarse restricción motriz al crear?

**Respuesta IA:** Sí.

### Q89. ¿Puede marcarse hora estimada de llegada?

**Respuesta IA:** Sí, opcional.

### Q90. ¿Debe validarse capacidad?

**Respuesta IA:** Sí.

## J. OTA manual y modo degradado

### Q91. ¿Qué campos son obligatorios?

**Respuesta IA:** Canal y external reservation ID.

### Q92. ¿Qué ocurre si vuelve la integración?

**Respuesta IA:** Se matchea por canal + external ID.

### Q93. ¿La OTA es fuente de verdad para cambios originados allí?

**Respuesta IA:** Sí para datos externos, salvo campos internos del PMS.

### Q94. ¿Qué campos internos no debe sobrescribir OTA?

**Respuesta IA:** Asignación interna, notas internas, permisos, auditoría y estados internos como liberada internamente.

### Q95. ¿Puede cargarse una reserva Booking manualmente?

**Respuesta IA:** Sí.

### Q96. ¿Se puede mensajear desde PMS sin integración?

**Respuesta IA:** No; la UI debe indicar función no disponible.

### Q97. ¿Se puede liberar internamente sin cancelar OTA?

**Respuesta IA:** Sí.

### Q98. ¿Debe quedar alerta de riesgo?

**Respuesta IA:** Sí.

### Q99. ¿Se reconcilian cancelaciones OTA?

**Respuesta IA:** Sí cuando la integración vuelve.

### Q100. ¿Se guarda payload original futuro?

**Respuesta IA:** Sí, recomendable para auditoría e integración.

## K. Tarifas y rate plans

### Q101. ¿Las tarifas son por categoría?

**Respuesta IA:** Sí en Sprint 1.

### Q102. ¿La grilla inicia hoy?

**Respuesta IA:** Sí, con navegación hacia futuro.

### Q103. ¿Se permite editar rango?

**Respuesta IA:** Sí.

### Q104. ¿Se permite editar por día de semana?

**Respuesta IA:** Sí.

### Q105. ¿Se permiten múltiples planes de tarifa?

**Respuesta IA:** Sí, al menos estándar y capacidad de agregar otros.

### Q106. ¿Booking/Expedia pueden tener refundable/non-refundable?

**Respuesta IA:** Sí como rate plans por canal en fases con integración.

### Q107. ¿Venta directa tiene tarifa estándar?

**Respuesta IA:** Sí por default.

### Q108. ¿Puede agregarse flexible/directa?

**Respuesta IA:** Sí.

### Q109. ¿Se guardan cambios históricos?

**Respuesta IA:** Sí.

### Q110. ¿Quién puede modificar tarifas?

**Respuesta IA:** Dueño por default; otros con permiso.

### Q111. ¿Las tarifas tienen moneda?

**Respuesta IA:** Sí.

## L. Monedas y tipo de cambio

### Q112. ¿Monedas Sprint 1?

**Respuesta IA:** ARS y USD.

### Q113. ¿Se guardan importes originales?

**Respuesta IA:** Sí, siempre en moneda original.

### Q114. ¿Se guarda tipo de cambio aplicado?

**Respuesta IA:** Sí.

### Q115. ¿Se recalculan pagos históricos si cambia cotización?

**Respuesta IA:** No.

### Q116. ¿Fuente de cotización?

**Respuesta IA:** Proveedor oficial/configurable por hotel; debe abstraerse detrás de un servicio.

### Q117. ¿Qué criterio favorece al hotel?

**Respuesta IA:** Usar el lado de compra/venta que maximiza el valor recibido por el hotel según dirección de conversión.

### Q118. ¿Puede el dueño elegir otra cotización?

**Respuesta IA:** Sí.

### Q119. ¿El recepcionista puede cambiarla?

**Respuesta IA:** No por default.

### Q120. ¿Se guarda fecha/hora de cotización?

**Respuesta IA:** Sí.

### Q121. ¿Qué pasa si la API cae?

**Respuesta IA:** Usar última cotización válida con warning y permitir override autorizado.

## M. Pagos, señas y links

### Q122. ¿Una reserva puede tener múltiples pagos?

**Respuesta IA:** Sí.

### Q123. ¿Puede combinar métodos?

**Respuesta IA:** Sí.

### Q124. ¿Un pago parcial por transferencia fija tarifa de transferencia?

**Respuesta IA:** Sí según reglas confirmadas.

### Q125. ¿Se guardan recargos como línea separada?

**Respuesta IA:** Sí, supuesto IA para transparencia.

### Q126. ¿Un link puede tener monto fijo o porcentaje de seña?

**Respuesta IA:** Sí.

### Q127. ¿Cuántos links activos por concepto?

**Respuesta IA:** Uno por concepto y moneda; generar uno nuevo invalida el anterior.

### Q128. ¿Los links vencidos se guardan?

**Respuesta IA:** Sí como historial.

### Q129. ¿Se puede cancelar un link?

**Respuesta IA:** Sí.

### Q130. ¿Pago confirmado bloquea habitación?

**Respuesta IA:** Sí.

### Q131. ¿Qué gana en concurrencia?

**Respuesta IA:** El primer pago confirmado y transacción aceptada por base de datos.

## N. Mercado Pago y PayPal

### Q132. ¿Las credenciales son por hotel?

**Respuesta IA:** Sí.

### Q133. ¿Puede haber recargo fijo?

**Respuesta IA:** Sí.

### Q134. ¿Puede haber recargo porcentual?

**Respuesta IA:** Sí.

### Q135. ¿El recargo puede diferir OTA vs directa?

**Respuesta IA:** Sí.

### Q136. ¿Se valida webhook?

**Respuesta IA:** Sí, firma obligatoria.

### Q137. ¿Se procesan webhooks idempotentemente?

**Respuesta IA:** Sí.

### Q138. ¿Qué pasa si llega webhook duplicado?

**Respuesta IA:** No duplica pago.

### Q139. ¿Se almacena provider_payment_id?

**Respuesta IA:** Sí.

### Q140. ¿Se permite conciliación manual?

**Respuesta IA:** Sí con permiso.

### Q141. ¿PayPal puede operar en USD?

**Respuesta IA:** Sí.

## O. Check-in

### Q142. ¿Se puede iniciar con saldo pendiente?

**Respuesta IA:** No.

### Q143. ¿Se puede hacer excepción?

**Respuesta IA:** Solo mediante override futuro explícito; no en Sprint 1 normal.

### Q144. ¿Se verifica documento de todos?

**Respuesta IA:** Sí.

### Q145. ¿Se puede agregar huéspedes después?

**Respuesta IA:** Sí hasta capacidad.

### Q146. ¿Se guarda hora real de ingreso?

**Respuesta IA:** Sí.

### Q147. ¿Se guarda usuario que completó?

**Respuesta IA:** Sí.

### Q148. ¿Se puede cambiar habitación antes de finalizar?

**Respuesta IA:** Sí.

### Q149. ¿Se recalcula tarifa si cambia categoría?

**Respuesta IA:** Sí o se aplica override autorizado.

### Q150. ¿Qué pasa con huésped prohibido?

**Respuesta IA:** Bloquea hasta autorización.

### Q151. ¿La habitación pasa a ocupada al confirmar ingreso?

**Respuesta IA:** Sí.

## P. Check-out y extensiones

### Q152. ¿Existe checkout parcial?

**Respuesta IA:** No.

### Q153. ¿Se puede hacer checkout anticipado?

**Respuesta IA:** Sí, sin devolución automática.

### Q154. ¿Se libera habitación al checkout?

**Respuesta IA:** Pasa a Requiere limpieza.

### Q155. ¿Extensión mantiene reserva?

**Respuesta IA:** Sí.

### Q156. ¿Extensión requiere pago?

**Respuesta IA:** Sí.

### Q157. ¿Puede extensión usar tarifa promedio original?

**Respuesta IA:** Sí.

### Q158. ¿Puede usar tarifa vigente?

**Respuesta IA:** Sí.

### Q159. ¿Qué pasa si la habitación está vendida?

**Respuesta IA:** Motor intenta resolver sin romper reservas pagas.

### Q160. ¿Se guarda historial de fechas anteriores?

**Respuesta IA:** Sí.

### Q161. ¿Se puede cancelar extensión no pagada?

**Respuesta IA:** Sí; pagada requiere autorización.

## Q. Motor de asignación y optimización

### Q162. ¿Objetivo principal?

**Respuesta IA:** Maximizar disponibilidad y ocupación.

### Q163. ¿Score es principal?

**Respuesta IA:** No.

### Q164. ¿Primer desempate?

**Respuesta IA:** Menor cantidad de movimientos.

### Q165. ¿Segundo desempate?

**Respuesta IA:** Mantener asignación/historial previo cuando sea equivalente.

### Q166. ¿Tercer desempate?

**Respuesta IA:** Mayor score.

### Q167. ¿El motor mueve reservas manuales?

**Respuesta IA:** No.

### Q168. ¿El motor mueve reservas empresa?

**Respuesta IA:** No.

### Q169. ¿Se ejecuta automáticamente?

**Respuesta IA:** Sí ante eventos relevantes.

### Q170. ¿Se puede revertir un grupo?

**Respuesta IA:** Sí por roles superiores.

### Q171. ¿Debe registrar explicación humana?

**Respuesta IA:** Sí.

## R. Lista de espera y overbooking

### Q172. ¿Quién crea overbooking?

**Respuesta IA:** Dueño/codueño por default.

### Q173. ¿Tiene habitación?

**Respuesta IA:** No.

### Q174. ¿Tiene pago?

**Respuesta IA:** No en V1.

### Q175. ¿Aparece en calendario?

**Respuesta IA:** No.

### Q176. ¿Se asigna automáticamente al liberarse cupo?

**Respuesta IA:** No, manualmente.

### Q177. ¿Se conserva orden de creación?

**Respuesta IA:** Sí como criterio informativo, no obligatorio.

### Q178. ¿Puede priorizarse manualmente?

**Respuesta IA:** Sí con motivo.

### Q179. ¿Se notifica automáticamente al huésped?

**Respuesta IA:** No en V1; contacto manual.

### Q180. ¿Se guarda categoría deseada?

**Respuesta IA:** Sí.

### Q181. ¿Se puede convertir en reserva real?

**Respuesta IA:** Sí al asignar habitación y luego solicitar pago.

## S. Caja y movimientos financieros

### Q182. ¿Existe caja por turno?

**Respuesta IA:** No.

### Q183. ¿Existe caja única?

**Respuesta IA:** Sí.

### Q184. ¿Cada cobro se asocia a usuario?

**Respuesta IA:** Sí.

### Q185. ¿La caja física incluye transferencias?

**Respuesta IA:** No, solo efectivo físico; transferencias aparecen en resumen financiero.

### Q186. ¿Se separa por moneda?

**Respuesta IA:** Sí.

### Q187. ¿Quién cierra caja?

**Respuesta IA:** Usuario con permiso específico.

### Q188. ¿Se permiten ajustes?

**Respuesta IA:** Sí con motivo.

### Q189. ¿Compras urgentes impactan caja y gastos?

**Respuesta IA:** Sí.

### Q190. ¿Se guarda comprobante?

**Respuesta IA:** Opcional o obligatorio según configuración.

### Q191. ¿Se puede editar caja cerrada?

**Respuesta IA:** Solo últimas tres cajas, con motivo y auditoría.

## T. Caja mensual, reportes y exportación

### Q192. ¿Caja mensual es una caja real?

**Respuesta IA:** No, es consolidado analítico.

### Q193. ¿Se cierra automáticamente por mes?

**Respuesta IA:** Sí como período lógico.

### Q194. ¿Se puede editar caja mensual?

**Respuesta IA:** No directamente.

### Q195. ¿Se recalcula si cambia una caja?

**Respuesta IA:** Sí.

### Q196. ¿Exporta PDF?

**Respuesta IA:** Sí.

### Q197. ¿Exporta CSV?

**Respuesta IA:** Sí.

### Q198. ¿Se genera bajo demanda?

**Respuesta IA:** Sí.

### Q199. ¿Se registra quién exportó?

**Respuesta IA:** Sí.

### Q200. ¿Quién accede por default?

**Respuesta IA:** Dueño/codueño.

### Q201. ¿Incluye detalle por caja?

**Respuesta IA:** Sí.

## U. Emails, reportes y notificaciones

### Q202. ¿Quién envía emails operativos?

**Respuesta IA:** Gmail conectado por el hotel.

### Q203. ¿Quién envía recuperación de cuenta?

**Respuesta IA:** Mail de plataforma.

### Q204. ¿Reporte matutino horario default?

**Respuesta IA:** 10:00 local.

### Q205. ¿Reporte nocturno horario default?

**Respuesta IA:** 23:00 local.

### Q206. ¿Reporte matutino incluye dinero?

**Respuesta IA:** No.

### Q207. ¿Reporte nocturno financiero llega a todos?

**Respuesta IA:** No; solo roles autorizados.

### Q208. ¿Alertas críticas se envían inmediatamente?

**Respuesta IA:** Sí.

### Q209. ¿Se puede configurar destinatarios?

**Respuesta IA:** Sí.

### Q210. ¿Si Gmail falla?

**Respuesta IA:** Se registra error, reintenta y muestra alerta.

### Q211. ¿Se guarda historial de envío?

**Respuesta IA:** Sí.

## V. API, WhatsApp y web propia

### Q212. ¿Cada hotel tiene credenciales API?

**Respuesta IA:** Sí.

### Q213. ¿La API tiene rate limit?

**Respuesta IA:** Sí.

### Q214. ¿La API devuelve disponibilidad?

**Respuesta IA:** Sí.

### Q215. ¿Devuelve tarifas?

**Respuesta IA:** Sí.

### Q216. ¿Devuelve categorías?

**Respuesta IA:** Sí.

### Q217. ¿Puede crear reservas?

**Respuesta IA:** Sí.

### Q218. ¿Puede generar link de pago?

**Respuesta IA:** Sí.

### Q219. ¿Las reservas guardan origen?

**Respuesta IA:** Sí.

### Q220. ¿WhatsApp y web usan el mismo motor?

**Respuesta IA:** Sí, vía servicios de dominio compartidos.

### Q221. ¿Puede un bot crear sobreventa?

**Respuesta IA:** No.

## W. Seguridad, privacidad y cumplimiento

### Q222. ¿Contraseñas se almacenan hasheadas?

**Respuesta IA:** Sí con algoritmo robusto.

### Q223. ¿Se requiere MFA para dueño?

**Respuesta IA:** Recomendado y preparado; obligatorio para acciones críticas futuras.

### Q224. ¿Cookies seguras?

**Respuesta IA:** Sí, Secure, HttpOnly y SameSite apropiado.

### Q225. ¿CSRF protegido?

**Respuesta IA:** Sí.

### Q226. ¿Se cifra información sensible?

**Respuesta IA:** Sí en tránsito y secretos en reposo.

### Q227. ¿Logs contienen documentos completos?

**Respuesta IA:** No; deben enmascararse.

### Q228. ¿Se auditan accesos sensibles?

**Respuesta IA:** Sí.

### Q229. ¿Se pueden descargar datos de huésped?

**Respuesta IA:** Solo con permiso.

### Q230. ¿Se contemplan backups?

**Respuesta IA:** Sí.

### Q231. ¿Se prueban restauraciones?

**Respuesta IA:** Sí periódicamente.

## X. Datos, SQL, NoSQL y rendimiento

### Q232. ¿Fuente de verdad principal?

**Respuesta IA:** PostgreSQL.

### Q233. ¿Se puede usar MongoDB/Cassandra?

**Respuesta IA:** Sí solo para casos justificados como eventos, logs o analítica.

### Q234. ¿Se puede duplicar lógica de negocio en NoSQL?

**Respuesta IA:** No.

### Q235. ¿Redis puede usarse?

**Respuesta IA:** Sí para cache, locks y colas.

### Q236. ¿Cómo se evita doble reserva?

**Respuesta IA:** Transacciones, constraints y locks a nivel de base de datos.

### Q237. ¿Se indexa búsqueda de huéspedes?

**Respuesta IA:** Sí.

### Q238. ¿Se indexa calendario?

**Respuesta IA:** Sí por hotel, fechas, habitación y estado.

### Q239. ¿Se requiere idempotencia?

**Respuesta IA:** Sí en pagos, webhooks e integraciones.

### Q240. ¿Se permiten migraciones destructivas directas?

**Respuesta IA:** No sin plan de backfill y rollback.

### Q241. ¿Se mide rendimiento?

**Respuesta IA:** Sí con métricas y alertas.

## Y. UX, PWA y accesibilidad

### Q242. ¿Debe funcionar como PWA?

**Respuesta IA:** Sí.

### Q243. ¿Debe agregarse a pantalla de inicio?

**Respuesta IA:** Sí.

### Q244. ¿Sidebar en desktop?

**Respuesta IA:** Sí.

### Q245. ¿Menú hamburguesa en móvil?

**Respuesta IA:** Sí.

### Q246. ¿Debe ser responsive?

**Respuesta IA:** Sí.

### Q247. ¿Estados críticos tienen iconos y texto?

**Respuesta IA:** Sí, no solo color.

### Q248. ¿Se preservan filtros del usuario?

**Respuesta IA:** Sí cuando sea útil.

### Q249. ¿La grilla debe virtualizarse?

**Respuesta IA:** Sí para rendimiento.

### Q250. ¿Acciones destructivas piden confirmación?

**Respuesta IA:** Sí.

### Q251. ¿Errores deben ser accionables?

**Respuesta IA:** Sí, explicar causa y próximo paso.

## Z. QA, pruebas y despliegue

### Q252. ¿Se requieren tests unitarios?

**Respuesta IA:** Sí.

### Q253. ¿Se requieren tests de integración?

**Respuesta IA:** Sí.

### Q254. ¿Se requieren tests end-to-end?

**Respuesta IA:** Sí para flujos críticos.

### Q255. ¿Se prueba aislamiento multi-tenant?

**Respuesta IA:** Sí.

### Q256. ¿Se prueba concurrencia de última habitación?

**Respuesta IA:** Sí.

### Q257. ¿Se prueban webhooks duplicados?

**Respuesta IA:** Sí.

### Q258. ¿Se prueban permisos?

**Respuesta IA:** Sí con matriz automatizada.

### Q259. ¿Se requiere entorno staging?

**Respuesta IA:** Sí.

### Q260. ¿Se permite desplegar sin migración validada?

**Respuesta IA:** No.

### Q261. ¿Debe existir rollback?

**Respuesta IA:** Sí.


## Resumen de cobertura

- Total de preguntas respondidas: 261.
- Enfoques cubiertos: producto, negocio, multi-tenant, permisos, seguridad, habitaciones, huéspedes, reservas, OTA, tarifas, monedas, pagos, check-in, check-out, motor, overbooking, caja, reportes, API, UX, arquitectura, datos, QA y despliegue.
- Estas respuestas no reemplazan decisiones explícitas del dueño del producto; funcionan como defaults de desarrollo y criterios de cierre.
