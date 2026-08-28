/**
 * Every word the public site says.
 *
 * Ground rule: nothing here may claim something the product does not do today.
 * `docs/marketing/landing-page/00-executive-summary.md` keeps the explicit
 * do-not-say list -- no testimonials, no customer counts, no SLA, no "channel
 * manager", no prices we have not published. Where a limitation is real we say
 * it out loud instead of writing around it; a hotelier who catches one dodge
 * stops believing the rest of the page.
 */

export const brandName = "Hotels-PMS";
export const tagline = "Todo el hotel, en un solo sistema.";

export const positioning =
  "Hotels-PMS es el sistema de gestión que reúne reservas, recepción, housekeeping, tarifas, caja, stock y lavandería en un solo lugar, para hoteles chicos y medianos que hoy trabajan con una herramienta distinta para cada cosa.";

export const hero = {
  title: "El estado real del hotel, siempre en el mismo lugar.",
  subtitle:
    "Reservas, recepción, housekeeping, tarifas, caja, stock y lavandería trabajando sobre los mismos datos. Cada turno le entrega al siguiente un hotel que ya está al día.",
  note: "Estamos abriendo el acceso por tandas. Dejanos tu mail y te escribimos cuando le toque a tu hotel."
};

/** The six places the state of a hotel actually lives before a PMS. */
export const scatteredPlaces = [
  { label: "Planilla de Excel", detail: "la que sabe abrir una sola persona" },
  { label: "Cuaderno de recepción", detail: "y lo que quedó anotado al margen" },
  { label: "Grupo de WhatsApp", detail: "donde se pasa el turno" },
  { label: "Correo de las OTA", detail: "reservas que alguien tiene que copiar" },
  { label: "Carpeta de comprobantes", detail: "para cuando haya que buscarlos" },
  { label: "La cabeza del encargado", detail: "el día que se toma vacaciones" }
];

export const problemPoints = [
  {
    title: "Nadie mira el mismo número",
    body: "Recepción, housekeeping y administración leen tres versiones distintas del mismo día, y ninguna está del todo al día."
  },
  {
    title: "El turno arranca reconstruyendo",
    body: "La primera media hora se va en averiguar qué pasó anoche en vez de en atender a los huéspedes que llegan."
  },
  {
    title: "El error aparece tarde",
    body: "La habitación doble asignada, el cobro sin registrar y la diferencia de caja se descubren cuando ya cuestan plata."
  }
];

/** Grouped the way a hotel is actually staffed, not the way the code is split. */
export const moduleGroups = [
  {
    id: "recepcion",
    label: "Recepción",
    summary: "Todo lo que pasa en el mostrador, sobre una sola planilla.",
    modules: [
      { name: "Planilla de ocupación", body: "La grilla de habitaciones por noche, con arrastre y bloqueos." },
      { name: "Reservas", body: "Alta, modificación, acompañantes, cambios de categoría y tarifa manual." },
      { name: "Check-in y check-out", body: "Incluye check-in parcial y checkout forzado con permiso aparte." },
      { name: "Huéspedes", body: "Ficha, etiquetas, restricciones y habitaciones a evitar." },
      { name: "Lista de espera", body: "Quién quedó afuera y qué se libera primero." }
    ]
  },
  {
    id: "operacion",
    label: "Operación",
    summary: "El trabajo que sostiene la noche y no se ve desde el mostrador.",
    modules: [
      { name: "Estado de habitaciones", body: "Housekeeping con historial de cada cambio de estado." },
      { name: "Tareas y pase de turno", body: "Lo pendiente viaja con el turno en vez de con la persona." },
      { name: "Lavandería y ropa blanca", body: "Lotes, proveedores, remitos y precios por prenda." },
      { name: "Stock y depósito", body: "Ubicaciones, movimientos, mínimos y consumo." },
      { name: "Auditoría operativa", body: "Qué cambió, quién lo cambió y cuándo." }
    ]
  },
  {
    id: "dinero",
    label: "Dinero",
    summary: "Desde la tarifa hasta el arqueo, sin pasar por una planilla aparte.",
    modules: [
      { name: "Caja y arqueo", body: "Apertura, movimientos, cierre y aprobación de diferencias." },
      { name: "Cobros y links de pago", body: "MercadoPago con webhook verificado, y cobro manual." },
      { name: "Comprobantes y recargos", body: "Comprobante adjunto y recargo según el medio de pago." },
      { name: "Tarifas y promociones", body: "Calendario diario, planes, ocupación y tipo de cambio." },
      { name: "Empresas", body: "Cuentas corporativas con su documentación." }
    ]
  },
  {
    id: "direccion",
    label: "Dirección",
    summary: "Para decidir sobre datos del sistema, no sobre un resumen escrito a mano.",
    modules: [
      { name: "Analítica", body: "Por habitación, categoría, canal, segmento y empresa." },
      { name: "Reportes operativos", body: "Diario, alertas y cierre de la noche, exportables." },
      { name: "Permisos", body: "84 permisos por rol, por persona y con vigencia." },
      { name: "Seguridad", body: "Segundo factor, sesiones activas y registro de auditoría." },
      { name: "Asistente", body: "Redacta y propone; aplicar siempre lo decide una persona." }
    ]
  }
];

/** Each one is checkable in the product. Nothing aspirational in this list. */
export const differentiators = [
  {
    title: "Permisos que siguen a la operación real",
    body: "No son cinco roles fijos. Son 84 permisos que se abren por rol o por persona, con ventanas de visibilidad y permisos temporales que alguien pide, alguien aprueba y se apagan solos.",
    proof: "Mover una reserva de categoría, poner tarifa manual o forzar un checkout son permisos distintos."
  },
  {
    title: "Todos ven lo mismo, al mismo tiempo",
    body: "Los cambios viajan en vivo a las pantallas abiertas. Si dos personas editan la misma reserva, el sistema resuelve campo por campo en lugar de dejar que la última en guardar pise a la otra.",
    proof: "Conexión en vivo con recuperación: si una pantalla se queda sin señal, al volver se pone al día sola."
  },
  {
    title: "La asignación de habitaciones la resuelve un solver",
    body: "Repartir reservas entre habitaciones respetando categorías, bloqueos y preferencias es un problema de optimización, y lo resolvemos como tal en vez de con reglas sueltas.",
    proof: "Motor CP-SAT de Google OR-Tools."
  },
  {
    title: "Cada diferencia de caja queda firmada",
    body: "El arqueo compara lo esperado con lo contado. Si no cierra, la diferencia necesita aprobación explícita y queda registrada con quién la aprobó.",
    proof: "Aprobar una diferencia es un permiso propio, separado de operar la caja."
  },
  {
    title: "El asistente propone, la persona aprueba",
    body: "Redacta respuestas y sugiere acciones, pero no toca la operación. Todo pasa por borrador, revisión y aprobación humana antes de aplicarse.",
    proof: "Se ejecuta contra un modelo local; viene apagado y se enciende cuando el hotel quiere."
  }
];

export const integrations = [
  { name: "Booking.com", detail: "Reservas entrantes por webhook" },
  { name: "Expedia", detail: "Reservas entrantes por webhook" },
  { name: "Despegar", detail: "Reservas entrantes por webhook" },
  { name: "MercadoPago", detail: "Links de pago y cobro verificado" },
  { name: "WhatsApp Business", detail: "Consultas y reservas asistidas" },
  { name: "Gmail", detail: "Correo del hotel conectado" }
];

/** Said out loud on the page. A dodge that gets caught costs more than the gap. */
export const integrationsCaveat =
  "Las reservas de las OTA entran por webhook y también se cargan a mano. Todavía no somos un channel manager: el envío de tarifas y disponibilidad hacia todos los canales está en camino, y lo vas a ver acá cuando esté.";

/**
 * What a hotel is usually paying for separately. Deliberately unpriced: we do
 * not know what any given hotel pays for these, and inventing a saving would
 * be the first claim a buyer could catch.
 */
export const replacedTools = [
  { name: "La planilla de ocupación", detail: "en Excel, que abre una sola persona" },
  { name: "El control de caja", detail: "en otra planilla, cuadrada a mano" },
  { name: "El cuaderno de recepción", detail: "y el grupo de WhatsApp del turno" },
  { name: "El control de stock y ropa blanca", detail: "cuando existe" },
  { name: "Los reportes para dirección", detail: "armados a fin de mes, a mano" }
];

export const riskReversal = [
  {
    title: "14 días con todo abierto",
    body: "La prueba no recorta funciones ni pide tarjeta para empezar."
  },
  {
    title: "Tus datos salen cuando quieras",
    body: "Reservas, ingresos y ocupación se exportan a CSV y Excel desde la analítica. No quedan secuestrados adentro."
  },
  {
    title: "Sin contrato de permanencia",
    body: "Es una suscripción mensual por hotel. Si no te sirve, dejás de pagarla."
  }
];

/** The honest disqualification. It costs a few leads and buys the rest. */
export const notForYou = [
  "Cadenas con casa matriz y consolidación entre hoteles.",
  "Hoteles de más de 80 habitaciones: hoy los planes no llegan a esa escala.",
  "Quien necesita hoy envío automático de tarifas y cupos a todos los canales.",
  "Quien busca un motor de reservas para su propia web: eso no lo cubrimos."
];

export const founder = {
  title: "Lo construí para mi propio hotel.",
  body: [
    "Hotel Chipre es mi hotel. Todo lo que ves acá salió de necesitarlo un martes a las siete de la mañana, con gente esperando en el mostrador y la planilla desactualizada.",
    "Por eso el sistema está armado alrededor del turno y no alrededor de un módulo de facturación: porque el problema real no es cargar la reserva, es que la persona que entra a las seis sepa exactamente en qué estado quedó el hotel.",
    "Y por eso también, cuando algo todavía no está, lo digo. Prefiero perder una venta antes que explicarte en el mes dos por qué el sistema no hace lo que la landing prometía."
  ],
  signature: "Máximo, dueño de Hotel Chipre"
};

export const onboardingSteps = [
  {
    title: "Cargás el hotel",
    body: "Categorías, habitaciones y los datos con los que facturás. El asistente de alta te lleva paso a paso."
  },
  {
    title: "Definís las reglas",
    body: "Políticas, medios de cobro, tarifas base y quién puede hacer qué dentro del sistema."
  },
  {
    title: "Entra el equipo",
    body: "Invitás a recepción, housekeeping y administración, y el hotel empieza a operar sobre una sola base."
  }
];

export const faqItems = [
  {
    question: "¿Para qué tamaño de hotel es?",
    answer:
      "Para hoteles independientes, boutique y chicos o medianos. Los planes están armados por cantidad de habitaciones y de usuarios, hasta 80 habitaciones."
  },
  {
    question: "¿Reemplaza a todos los sistemas que uso hoy?",
    answer:
      "Reemplaza la planilla de ocupación, el cuaderno de recepción, la caja en Excel, el control de stock y de ropa blanca, y los reportes armados a mano. No reemplaza tu facturación electrónica ni tu motor de reservas web."
  },
  {
    question: "¿Sincroniza tarifas y disponibilidad con Booking y Expedia?",
    answer:
      "Todavía no en las dos direcciones. Las reservas entran por webhook y se pueden cargar a mano, pero el envío automático de tarifas y cupos hacia los canales sigue en desarrollo. Preferimos decirlo antes y no después."
  },
  {
    question: "¿Cuánto sale?",
    answer:
      "Es una suscripción mensual por hotel, con tres planes según cuántas habitaciones y cuántas personas del equipo lo usan. Estamos cerrando los precios definitivos y los publicamos acá apenas estén."
  },
  {
    question: "¿Puedo probarlo antes de pagar?",
    answer: "Sí. La prueba es de 14 días con el sistema completo, sin cargar una tarjeta para empezar."
  },
  {
    question: "¿Qué pasa con mis datos?",
    answer:
      "Cada hotel opera aislado del resto: los datos de un hotel no son alcanzables desde otro, y eso está verificado con pruebas automáticas. Hay segundo factor, sesiones revocables y registro de auditoría."
  },
  {
    question: "¿Puedo entrar ahora mismo?",
    answer:
      "Estamos abriendo por tandas mientras terminamos de endurecer la plataforma. Dejá tu mail y te avisamos cuando le toque a tu hotel."
  },
  {
    question: "¿Puedo traer los datos que ya tengo cargados?",
    answer:
      "Todavía no hay importación masiva desde Excel. El alta guiada carga categorías, habitaciones y tarifas, y las reservas se van cargando a medida que entran. Si tenés mucho volumen histórico, escribinos antes de arrancar y lo vemos."
  },
  {
    question: "¿Y si después me quiero ir?",
    answer:
      "Te llevás tus datos. Reservas, ingresos y ocupación se exportan a CSV y a Excel desde la analítica, sin pedir permiso a nadie. No hay contrato de permanencia."
  },
  {
    question: "¿Funciona en el celular?",
    answer:
      "Sí. Es una aplicación web que se instala en el teléfono, pensada para que housekeeping y recepción trabajen desde el pasillo y no desde el escritorio."
  }
];

export const marketingRoutes = [
  { label: "El sistema", to: "/funciones" },
  { label: "Precios", to: "/precios" },
  { label: "Preguntas", to: "/faq" },
  { label: "Contacto", to: "/contacto" }
];

/* ---------------------------------------------------------------------------
   Kept for the SEO landing pages (/pms-hotelero, /software-para-hoteles,
   /funciones), which still read these shapes. Content refreshed to match the
   real product; structure unchanged so those pages keep compiling.
   ------------------------------------------------------------------------ */

export const heroBullets = [
  "Alta guiada del hotel, paso a paso",
  "Toda la operación sobre los mismos datos",
  "14 días de prueba con el sistema completo"
];

export const systemPoints = moduleGroups.flatMap((group) =>
  group.modules.slice(0, 2).map((module) => ({ title: module.name, body: module.body }))
);

export const benefitPoints = [
  {
    title: "Para recepción",
    body: "Una planilla que ya está al día cuando arranca el turno, con la reserva, el huésped y el cobro en el mismo lugar."
  },
  {
    title: "Para operación",
    body: "Housekeeping, lavandería y stock dejan de depender de que alguien avise, porque el estado lo escribe el sistema."
  },
  {
    title: "Para dirección",
    body: "Ocupación, ingresos y diferencias de caja salen del sistema, no de un resumen que alguien armó a mano."
  }
];

export const screenshotFrames = [
  {
    title: "Planilla de ocupación",
    description:
      "La grilla de habitaciones por noche. Se arrastra una reserva de una habitación a otra y el sistema avisa si el cambio rompe una regla.",
    src: "/marketing/screenshots/planilla.webp",
    mobileSrc: "/marketing/screenshots/planilla-mobile.webp"
  },
  {
    title: "Visión general",
    description:
      "Ocupación del día, tarifa promedio, ingresos del mes y lo que quedó pendiente, calculado sobre la operación real y no sobre una planilla aparte.",
    src: "/marketing/screenshots/dashboard.webp",
    mobileSrc: "/marketing/screenshots/dashboard-mobile.webp"
  },
  {
    title: "Reservas",
    description:
      "Alta, cambios, acompañantes y estado de cobro de cada reserva, con el historial de lo que tocó cada persona del equipo.",
    src: "/marketing/screenshots/reservas.webp",
    mobileSrc: "/marketing/screenshots/reservas-mobile.webp"
  },
  {
    title: "Caja",
    description:
      "Apertura de turno, movimientos y cierre de arqueo. Si lo contado no coincide con lo esperado, la diferencia necesita aprobación y queda firmada.",
    src: "/marketing/screenshots/caja.webp",
    mobileSrc: "/marketing/screenshots/caja-mobile.webp"
  },
  {
    title: "Tarifas",
    description:
      "Calendario de precios por día y por categoría, con promociones y tipo de cambio, sin tener que recalcular a mano cada temporada.",
    src: "/marketing/screenshots/tarifas.webp",
    mobileSrc: "/marketing/screenshots/tarifas-mobile.webp"
  },
  {
    title: "Analítica",
    description:
      "Ocupación e ingresos abiertos por habitación, categoría, canal, segmento y empresa, exportables a CSV o Excel.",
    src: "/marketing/screenshots/analitica.webp",
    mobileSrc: "/marketing/screenshots/analitica-mobile.webp"
  }
];
