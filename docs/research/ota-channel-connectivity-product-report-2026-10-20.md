# Cómo conectan los PMS con las OTAs
## Informe para decisión de producto — Hotel Chipre PMS

**Fecha:** 20 de octubre de 2026
**Audiencia:** Dirección de Producto
**Estado de certeza:** hechos confirmados con documentación pública oficial; recomendación e inferencias identificadas como tales.

## Resumen ejecutivo

Los PMS observados no se limitan a importar reservas. Mantienen una conexión de distribución bidireccional: envían disponibilidad, tarifas y restricciones (ARI) a las OTAs, reciben altas, cambios y cancelaciones de reservas y, después de cada evento, propagan la disponibilidad restante a los demás canales. Para esto suelen combinar una capa propia de channel manager con integraciones certificadas por OTA; también permiten que el hotel conecte su cuenta y mapee habitaciones y planes de tarifa.

**Recomendación:** autorizar una prueba técnico-comercial con **Channex** como primera opción de canalizador API y pedir una propuesta paralela a **SiteMinder**. Channex publica una guía para integrar PMS y documentación para Booking.com, Expedia y Despegar; sus páginas describen alta de propiedades, mapeos, actualización ARI, recepción y confirmación de eventos. Esa cobertura pública hace viable evaluar una sola integración PMS→proveedor en lugar de certificar tres conectores propios de entrada. La documentación pública no confirma precio, SLA, disponibilidad contractual para Hotel Chipre ni comportamiento de cada cuenta argentina; la prueba no debe convertirse en selección de proveedor hasta validar esos puntos.

Guesty y Cloudbeds sirven como referencias de producto, pero sus APIs públicas no son por sí mismas un conector que Hotel Chipre pueda usar para distribuir sus hoteles. Guesty documenta conexiones directas con algunos canales y también conexiones mediante un channel manager. Cloudbeds incorpora su propio módulo de distribución y separa los alcances de disponibilidad, tarifas, restricciones y reservas. Su API PMS expone datos de cuentas Cloudbeds; su API de channel manager descrita para socios permite que una OTA se conecte a Cloudbeds, que es otra dirección de integración.

## Decisión que debe tomar Producto

La decisión principal es **construir y operar conectores oficiales por OTA** o **integrar Hotel Chipre con un channel manager/API de conectividad que ya opera esas conexiones**.

| Ruta | Qué implica | Ventaja | Riesgo o dependencia | Evaluación |
|---|---|---|---|---|
| Integraciones directas con Booking.com, Expedia y Despegar | Una relación, autorización, implementación, certificación y mantenimiento por proveedor | Control directo de capacidades, eventos y roadmap | Alto esfuerzo inicial y continuo; cada OTA tiene contratos, modelos, límites y procesos distintos | Mantener como ruta estratégica si el volumen y diferenciación lo justifican |
| API de channel manager para PMS, por ejemplo Channex | Una integración de Hotel Chipre con el proveedor; el hotel autoriza cada canal y mapea habitaciones y tarifas | Menos conectores a construir y una superficie común para reservas y ARI | Dependencia contractual, operativa y de calidad de datos del proveedor; costos y SLA por validar | **Primera prueba recomendada** |
| API de ecosistema de SiteMinder | Integrar Hotel Chipre a su producto PMS/channel manager para socios | Alternativa con ecosistema maduro de integraciones hoteleras | Requiere admisión y condiciones de partner; confirmar cobertura concreta de Despegar y Argentina | **Comparar en paralelo** |
| API pública de Guesty o Cloudbeds como agregador | Usar la API de los propios PMS | Permite integraciones entre productos | No demuestra acceso de Hotel Chipre a las conexiones OTA de esos PMS | No asumir que reemplaza un channel manager |

La comparación es cualitativa. El precio, tiempos, cargos, SLA, mínimos de propiedades y acceso a sandbox deben pedirse a cada proveedor.

## Cómo funciona el flujo operativo

ARI significa disponibilidad, tarifas y restricciones. La OTA registra la reserva contra la disponibilidad que tiene en su sistema. El channel manager/PMS recibe el evento, registra la reserva y actualiza el inventario compartido en los demás canales. Después envía el nuevo stock y las tarifas/restricciones afectadas. Booking.com recomienda actualizar las copias de inventario al procesar una reserva; Despegar indica ajustar disponibilidad en las otras OTAs; Cloudbeds describe su distribución como sincronización de disponibilidad, tarifas, restricciones y reservas. ([Booking.com: Reservations API](https://developers.booking.com/connectivity/docs/reservations-api/reservations-overview), [Despegar: Booking Handling Pull](https://channel.despegar.com/portal/documentation/booking-handling-pull), [Cloudbeds: Connection Types](https://myfrontdesk.cloudbeds.com/hc/en-us/articles/43460146972955-Configure-Connection-Types-for-Channel-Managers-and-CRSs-Full-One-Way-and-Custom-Connections))

Flujo recomendado para Hotel Chipre:

1. La OTA o el channel manager entrega un evento de reserva nueva, modificada o cancelada.
2. Hotel Chipre deduplica el evento, valida la propiedad y los mapeos, y actualiza reserva, huésped e inventario en una transacción.
3. Una cola/outbox envía el stock actualizado al proveedor de conectividad.
4. El proveedor propaga los cambios a las OTAs y devuelve estado o error.
5. Hotel Chipre muestra última sincronización, errores, reservas sin mapeo y acciones pendientes de recepción.

**No hay evidencia pública de una garantía absoluta de “cero sobreventa”.** Es una inferencia operacional: las conexiones tienen colas, ventanas de consulta, reintentos y demoras de red; algunas reservas ya están confirmadas para el huésped antes de que el PMS reciba el evento. Por ejemplo, Booking.com recomienda una consulta B.XML cada 20 segundos y Expedia mantiene documentación de una notificación antigua que se entrega después de confirmar la reserva. El objetivo debe ser reducir drásticamente la probabilidad, detectar conflictos y evitar pérdidas silenciosas, no prometer una garantía imposible entre sistemas independientes. ([Booking.com: B.XML reservations](https://developers.booking.com/connectivity/docs/reservations-api/managing-reservations-bxml), [Expedia Group: Booking Notification API](https://developers.expediagroup.com/supply/lodging/docs/booking_apis/booking_notification/getting_started/introduction/))

Un punto especial de Despegar: la documentación distingue inventario público compartido de inventario privado/exclusivo. Una reserva sobre inventario privado no debe restarse automáticamente del cupo público que se comparte con las demás OTAs. La decisión se toma por tramo de habitación/noche. Un decremento global sin esa distinción puede hacer que Hotel Chipre cierre ventas de más. ([Despegar: Booking Handling Pull](https://channel.despegar.com/portal/documentation/booking-handling-pull))

## Qué publica cada proveedor

### Booking.com

Booking.com ofrece Connectivity APIs a proveedores aprobados. Las conexiones se otorgan por tipo: reservas, tarifas y disponibilidad, contenido, mensajería y otros alcances. La propiedad concede permiso al proveedor y la API limita endpoints según tipo de conexión, activación y certificación. Los endpoints de reservas requieren certificación PII y PCI para funciones que incluyen datos sensibles. ([Booking.com: Connectivity APIs](https://developers.booking.com/connectivity/docs), [Connections API](https://developers.booking.com/connectivity/docs/connections-api/connections-overview), [Mapping connection types](https://developers.booking.com/connectivity/docs/connections-api/mapping-connections))

Para reservas se publican dos estilos principales: OTA XML con lectura y confirmación/acknowledgement de procesamiento, y B.XML con una única consulta para nuevas, modificadas y canceladas. B.XML no tiene acknowledgement; la documentación recomienda consultar cada 20 segundos y describe envío por email como fallback si el proveedor no procesa a tiempo o hay tarifas/habitaciones sin mapear. El payload puede incluir fechas, ocupación, habitación, tarifa, moneda, totales y datos del huésped, pero algunos elementos son opcionales o requieren habilitación; el teléfono puede venir vacío. ([Reservations API overview](https://developers.booking.com/connectivity/docs/reservations-api/reservations-overview), [B.XML reservations](https://developers.booking.com/connectivity/docs/reservations-api/managing-reservations-bxml))

La API de disponibilidad recibe cantidad de habitaciones a vender por tipo de habitación y fecha, precios y restricciones. Booking.com recomienda enviar disponibilidad con al menos 12 meses de anticipación y usar deltas en actualizaciones ordinarias. ([Availability API](https://developers.booking.com/connectivity/docs/b_xml-availability))

### Expedia Group

Expedia documenta un conjunto de APIs de conectividad para alojamiento: disponibilidad/tarifas, gestión de reservas y productos (habitaciones y planes de tarifa). El proceso público para integrarse pide contactar al equipo, revisar licencia y PCI, consultar con conectividad, desarrollar/probar/hacer un lanzamiento controlado y luego salir a producción. Expedia dice que no acepta conexiones API directas de propiedades individuales; el producto consumidor debe ser un proveedor de conectividad. ([Expedia Group: Connectivity Hub](https://developers.expediagroup.com/supply/lodging), [License Agreement](https://developers.expediagroup.com/supply/lodging/license))

La reserva debe implementar la capacidad actual de Reservation Management GraphQL que Expedia anunció con alcance global en abril de 2025. La antigua Booking Notification API XML no está disponible para nuevas adopciones según su documentación actual; no conviene diseñar un conector nuevo alrededor de ese flujo sin confirmación escrita del equipo técnico de Expedia. ([Expedia Group: Connectivity updates](https://developers.expediagroup.com/supply/lodging/updates), [Booking Notification API — disponibilidad para adopción](https://developers.expediagroup.com/supply/lodging/docs/booking_apis/booking_notification/getting_started/introduction/))

### Despegar

Despegar publica su interfaz de conectividad para socios: enviar disponibilidad, tarifas y restricciones; leer habitaciones y planes; recibir reservas. La documentación usa un subconjunto de mensajes OTA 2013B en XML. Admite manejo de reservas por Pull y Push; el flujo Pull confirma recepción mediante un mensaje de notificación y puede volver a entregar reservas no confirmadas. ([Despegar: API PSP](https://channel.despegar.com/portal/documentation), [Booking Handling Pull](https://channel.despegar.com/portal/documentation/booking-handling-pull), [Booking Handling Push](https://channel.despegar.com/portal/documentation/booking-handling-push))

Despegar indica que entrega una clave propia del channel manager luego de certificar su integración y que cada hotel crea una conexión desde su extranet con credenciales específicas para esa relación. La página pública enumera límites por cliente y hotel, por lo que una integración debe agrupar llamadas y respetar límites. También indica que el dato completo de tarjeta puede estar disponible en el flujo Push; el Pull devuelve datos de tarjeta enmascarados. El producto debe mantener el procesamiento de pagos fuera de la integración de reserva salvo que exista una necesidad aprobada y el cumplimiento PCI correspondiente.

### Guesty y Cloudbeds

Guesty permite conectar directamente algunos canales, entre ellos Booking.com, y también conectar vía channel manager. Su ayuda aclara que Expedia no se integra como una cuenta directa en ese flujo y que se enlazan listados individuales. La API Open de Guesty expone datos de una cuenta Guesty; para socios OTA, Guesty remite a su canal de partners. Esto demuestra que un PMS puede combinar conectores propios con proveedores externos según el canal, pero su API de cuenta no equivale a un API de distribución OTA para Hotel Chipre. ([Guesty: Connecting booking channels](https://help.guesty.com/hc/en-gb/articles/9371351491101-Connecting-your-booking-channels-directly-to-Guesty), [Guesty Open API: scope and partners](https://open-api-docs.guesty.com/reference/get-started))

Cloudbeds documenta Full Connection (el PMS gestiona disponibilidad, tarifas, restricciones y reservas) y Custom Connection (se separan los alcances que controla Cloudbeds y los que controla otro sistema). En su guía para Expedia requiere autorización de conexión, selección del proveedor en la extranet y mapeo de habitación/plan de tarifa. Este modelo es útil para diseñar el onboarding y evitar que dos sistemas sean responsables de los mismos campos. ([Cloudbeds: Connection Types](https://myfrontdesk.cloudbeds.com/hc/en-us/articles/43460146972955-Configure-Connection-Types-for-Channel-Managers-and-CRSs-Full-One-Way-and-Custom-Connections), [Connect Expedia](https://myfrontdesk.cloudbeds.com/hc/en-us/articles/212522067-Connect-Expedia-to-Cloudbeds-PMS))

Su API PMS permite gestionar reservas, huéspedes y habitaciones de una cuenta Cloudbeds. La documentación de “OTA build-to-us” describe la dirección contraria: una OTA implementa un receptor para conectarse al channel manager Cloudbeds. Por eso no se debe interpretar la API pública de Cloudbeds como un API de distribución común para sistemas PMS externos. ([Cloudbeds APIs](https://developers.cloudbeds.com/v1.2/docs/about-cloudbeds-api), [OTA Build-to-us](https://developers.cloudbeds.com/v1.2/reference/ota-build-to-us-introduction))

## Candidato de conectividad: Channex; alternativa: SiteMinder

Channex documenta una API para integrar PMS: crear propiedades/habitaciones/tarifas, enviar ARI y recibir reservas por feed de revisiones. Admite ACK del evento; un webhook puede avisar de una nueva revisión, pero el PMS debe leer la revisión canónica y reconocerla. Channex advierte que los webhooks pueden llegar fuera de orden y recomienda usar la notificación como disparador para consultar el estado correcto, además de mantener un pull de respaldo. ([Channex: PMS Integration Guide](https://docs.channex.io/guides/pms-integration-guide), [Webhook Collection](https://docs.channex.io/api-v.1-documentation/webhook-collection), [Bookings Collection](https://docs.channex.io/api-v.1-documentation/bookings-collection))

Su catálogo público identifica Booking.com (BDC), Expedia (EXP) y Despegar (DDC), y hay guías de conexión específicas. Las guías muestran al hotel autorizando a Channex desde la extranet OTA y después mapeando habitaciones y planes de tarifa en el channel manager. Esto confirma cobertura documentada, pero no prueba que las tres conexiones estén disponibles bajo las condiciones comerciales, países o cuentas que necesitamos. ([Channex: Channel Codes](https://docs.channex.io/api-v.1-documentation/channel-codes), [Booking.com setup](https://docs.channex.io/channel-mapping-guides/booking.com), [Expedia setup](https://docs.channex.io/channel-mapping-guides/expedia), [Despegar setup](https://docs.channex.io/channel-mapping-guides/despegar))

Antes de elegirlo, verificar dos límites publicados: Channex dice que hoy no crea listados en OTAs, así que se deben crear en cada extranet; también dice que un PMS generalmente no puede cambiar fechas o cancelar una reserva OTA a través de Channex, pues el huésped debe gestionar ese cambio en el canal de origen. ([Channex: Start Integration](https://channex.io/start-integration))

SiteMinder ofrece APIs para PMS/RMS, incluyendo pmsXchange, y un proceso de partner. Su criterio público de activación para una integración PMS contempla licencia aplicable, prueba técnica agendada y al menos una conexión OTA activa. Hay que pedirle confirmación explícita de cobertura de Despegar, API disponible a un PMS nuevo, costos y proceso de certificación antes de compararlo con Channex. ([SiteMinder Developer Guide](https://developer.siteminder.com/), [Partner Readiness Criteria](https://www.siteminder.com/partner-programs/readiness/))

## Encaje actual con Hotel Chipre

Revisión estática del código en **HEAD 563ddc01d4b71ee63fce3a7115e02e83600d2ec3**:

- Hay modelos de conexiones OTA, estados, mapeos por propiedad/habitación/plan de tarifa y trabajos de sincronización en app/models/ota_core.py.
- app/services/ota/adapters/booking.py ya contiene una implementación parcial orientada a los endpoints oficiales de Booking.com: consulta reservas, procesa cambios/cancelaciones, confirma reservas y envía disponibilidad/tarifas/restricciones. Cancelar o modificar una reserva en Booking desde Hotel Chipre no está implementado ahí. La presencia del código no prueba acceso de partner, certificación ni éxito operativo.
- app/services/ota/adapters/expedia.py y despegar.py normalizan payloads, pero las consultas devuelven listas vacías y los envíos de inventario/tarifas/restricciones no están implementados.
- Las rutas actuales de webhook aceptan JSON propio de Hotel Chipre y requieren secreto por hotel. Eso no demuestra que implementen el contrato XML o GraphQL de una OTA.
- docs/product-definition.md define Booking y Expedia como integraciones entrantes, deja Despegar por confirmar y registra OTA outbound como futuro. El código de Booking ya incluye algunas operaciones salientes. Esta diferencia de alcance queda como **needs-verification** para Producto.
- El modelo legado OTAReservationMapping contempla guardar el payload completo como texto; el modelo nuevo OTAReservationLink contempla payload cifrado. Antes de recibir reservas reales, confirmar qué ruta persiste los eventos, limitar retención y PII y excluir datos completos de tarjeta.

Archivos revisados: app/services/ota/adapters/{booking,expedia,despegar}.py, app/api/ota_webhooks.py, app/models/ota.py, app/models/ota_core.py, frontend/src/views/onboarding/OnboardingWizard.tsx, docs/product-definition.md, docs/roadmap.md.

## Prueba de concepto propuesta

Autorizar una POC que no toque canales reales hasta tener cuentas de prueba y autorización explícita. Evaluar al menos una propiedad de prueba y una habitación con stock bajo.

1. **Acceso y mercado:** confirmar con Channex y SiteMinder el contrato para PMS partner, precio, sandbox, soporte en Argentina, lista activa de OTAs, cobertura real de Despegar, SLA, límites, retención, subprocesadores y procedimiento de salida.
2. **Onboarding:** enlazar un hotel de prueba desde cada extranet y mapear todos los tipos de habitación y planes de tarifa; verificar moneda, ocupación, impuestos, cancelación y restricciones.
3. **Ciclo de reserva:** simular reserva nueva, modificación, cancelación, reintento, duplicado y llegada fuera de orden. Confirmar que la reserva queda una sola vez y mantiene el identificador original OTA.
4. **Propagación de stock:** reservar en un canal y observar el nuevo stock en los demás. Repetir con dos eventos sobre la última unidad, inventario privado de Despegar, timeout del proveedor y recuperación tras una interrupción.
5. **Operación hotelera:** mostrar en Hotel Chipre salud de conexión, última sincronización, eventos pendientes, campos de huésped no entregados por la OTA y errores de mapeo; permitir resolución manual auditada.
6. **Privacidad:** no almacenar PAN/CVV. Validar si emails o teléfonos llegan en alias o enmascarados y guardar solo los datos necesarios para operar la reserva.

Criterios de aceptación: ningún evento duplicado o perdido después de reintentar y reconciliar; cambios/cancelaciones reflejados correctamente; disponibilidad actualizada y error visible ante fallo; conflictos simultáneos alertados, nunca ocultados; credenciales por hotel cifradas; payload mínimo y sin datos de tarjeta. Definir los objetivos numéricos de latencia después de medir la POC.

## Conclusión

**Propuesta a Dirección:** aprobar la POC con Channex como primera opción y pedir condiciones a SiteMinder en paralelo. Mantener una arquitectura de adaptadores para no acoplar el dominio de reservas a un proveedor. Si la POC falla por cobertura local, precio, latencia, datos o controles, evaluar integraciones directas empezando por Booking.com y Despegar; para Expedia, obtener confirmación del equipo de conectividad sobre el acceso al flujo vigente de Reservation Management GraphQL.

**No mezclar dos autoridades de distribución para la misma propiedad y OTA.** Elegir qué sistema controla disponibilidad y tarifas para cada canal, como Cloudbeds permite hacer mediante Full/Custom Connection. Evita actualizaciones circulares y dobles decrementos.

## Fuentes, validación y límites

Las fuentes consultadas son documentación oficial de Booking.com, Expedia Group, Despegar, Guesty, Cloudbeds, Channex y SiteMinder. Se contrastaron contratos, flujos de reserva, ARI, autorización del hotel, mapeo y certificación. El informe revisa código local de forma estática y documentación pública vigente al 20/10/2026.

**No se probaron conexiones de partner, credenciales, sandbox, contratos, precios, cuentas hoteleras ni APIs de producción. No se ejecutaron pruebas automatizadas ni se modificó código.** La recomendación de POC es una inferencia apoyada en la documentación disponible. Precio, SLA, tiempos y cobertura contractual quedan como **needs-verification**.
