export const brandName = "Hotel Chipre PMS";
export const tagline = "Todo tu hotel, en un solo sistema.";
export const positioning =
  "Hotel Chipre PMS es un sistema de gestión hotelera para hoteles independientes que centraliza reservas, habitaciones, huéspedes y cobros en un solo lugar.";

export const heroBullets = [
  "Onboarding guiado para configurar tu hotel paso a paso",
  "Operación centralizada desde una sola plataforma",
  "Prueba de 14 días para conocer el sistema"
];

export const problemPoints = [
  {
    title: "Información dispersa",
    body: "Reservas, huéspedes y cobros quedan repartidos entre planillas, mensajes y herramientas sueltas."
  },
  {
    title: "Más fricción operativa",
    body: "Cada cambio cuesta más cuando no existe una sola base de trabajo para el equipo."
  },
  {
    title: "Menos control diario",
    body: "Sin un sistema central, el hotel pierde visibilidad sobre la operación real del día."
  }
];

export const systemPoints = [
  {
    title: "Reservas",
    body: "Carga, seguimiento y operación desde un mismo lugar."
  },
  {
    title: "Habitaciones",
    body: "Inventario y estado operativo para trabajar con más claridad."
  },
  {
    title: "Huéspedes",
    body: "Datos del huésped y contexto operativo vinculados a cada reserva."
  },
  {
    title: "Cobros",
    body: "Pagos y medios de cobro dentro del flujo del hotel."
  },
  {
    title: "Reportes",
    body: "Visibilidad operativa para entender qué está pasando en el hotel."
  }
];

export const integrationPoints = [
  "Conexiones visibles desde la configuración del hotel",
  "Integraciones ligadas a operación, canales y cobros",
  "Un solo lugar para administrar el día a día sin sumar complejidad innecesaria"
];

export const onboardingSteps = [
  "Crear tu cuenta y validar el acceso",
  "Completar la configuración inicial del hotel",
  "Empezar a operar desde una sola plataforma"
];

export const benefitPoints = [
  {
    title: "Para recepción",
    body: "Un solo lugar para consultar y operar reservas y huéspedes."
  },
  {
    title: "Para operación",
    body: "Menos fricción entre habitaciones, cobros y estado diario."
  },
  {
    title: "Para dirección",
    body: "Más claridad para tomar decisiones sin depender de planillas aisladas."
  }
];

export const pricingCards = [
  {
    code: "starter",
    name: "Starter",
    description: "Para empezar a ordenar la operación de tu hotel desde un solo sistema. Incluye prueba de 14 días.",
    cta: "Probar 14 días"
  },
  {
    code: "pro",
    name: "Pro",
    description: "Para hoteles que necesitan más capacidad operativa y más margen para crecer dentro de la plataforma.",
    cta: "Hablar con ventas"
  },
  {
    code: "ultra",
    name: "Ultra",
    description: "Para operaciones con mayor exigencia y una necesidad más amplia de control dentro del sistema.",
    cta: "Hablar con ventas"
  }
];

export const faqItems = [
  {
    question: "¿Qué es Hotel Chipre PMS?",
    answer:
      "Es un sistema de gestión hotelera pensado para centralizar reservas, habitaciones, huéspedes y cobros desde una sola plataforma web."
  },
  {
    question: "¿Para qué tipo de hoteles sirve?",
    answer:
      "La propuesta está pensada para hoteles independientes, boutique y pequeños/medianos dentro del rango definido por el producto."
  },
  {
    question: "¿Qué cubre el sistema hoy?",
    answer:
      "El foco público está en reservas, habitaciones, huéspedes, cobros, reportes y un onboarding guiado para empezar con orden."
  },
  {
    question: "¿La prueba de 14 días está incluida en Starter?",
    answer:
      "Sí. Starter es el plan de entrada y se presenta públicamente con una prueba de 14 días para conocer el sistema antes de decidir."
  },
  {
    question: "¿Qué hago si ya tengo cuenta?",
    answer: "Usá el acceso actual de la app para iniciar sesión."
  },
  {
    question: "¿Cómo consulto planes pagos?",
    answer:
      "Pro y Ultra se gestionan con el equipo comercial hasta que la compra online esté abierta."
  },
  {
    question: "¿La landing y la app están separadas?",
    answer:
      "Sí. La landing vive en el dominio marketing y la app opera en el subdominio del producto con indexación controlada."
  }
];

export const screenshotFrames = [
  {
    title: "Dashboard operativo",
    description: "Vista general con indicadores, próximas reservas y acciones del día.",
    src: "/marketing/screenshots/dashboard.png"
  },
  {
    title: "Reservas",
    description: "Operación de reservas con estado, fechas y detalle del huésped.",
    src: "/marketing/screenshots/reservas.png"
  },
  {
    title: "Conexiones",
    description: "Integraciones y conexiones del hotel desde la configuración del sistema.",
    src: "/marketing/screenshots/conexiones.png"
  }
];

export const marketingRoutes = [
  { label: "Funciones", to: "/funciones" },
  { label: "Precios", to: "/precios" },
  { label: "FAQ", to: "/faq" }
];
