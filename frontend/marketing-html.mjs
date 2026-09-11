/**
 * Emits one static HTML file per marketing route, with that route's title,
 * description, canonical and og:url already in the markup.
 *
 * Without this, every public page ships the same index.html and only gets its
 * real metadata once React mounts and components/Seo.tsx runs. A crawler that
 * does not execute JavaScript — which includes most link unfurlers — sees one
 * title and one description for the whole site.
 *
 * The copy is duplicated from the page components on purpose: this runs at
 * build time in plain Node and cannot import a .tsx module. Keep the two in
 * sync when a page title changes; marketing-html.test.mjs checks that every
 * route listed here is also routed in vercel.json.
 */
const SITE_URL = "https://hotels-pms.com";
const OG_IMAGE = `${SITE_URL}/brand/og-default.png`;

export const MARKETING_ROUTES = [
  {
    path: "/funciones",
    file: "funciones.html",
    title: "El sistema | Hotels-PMS",
    description:
      "Reservas, planilla de ocupación, recepción, housekeeping, tarifas, caja y arqueo, stock, lavandería, empresas, analítica y permisos por rol, en un solo sistema."
  },
  {
    path: "/precios",
    file: "precios.html",
    title: "Precios | Hotels-PMS",
    description:
      "Una suscripción mensual por hotel, con planes por cantidad de habitaciones y de usuarios. Prueba de 14 días con el sistema completo."
  },
  {
    path: "/faq",
    file: "faq.html",
    title: "Preguntas frecuentes | Hotels-PMS",
    description:
      "Qué cubre el sistema, qué todavía no, cómo funciona la prueba de 14 días y qué pasa con tus datos si te vas."
  },
  {
    path: "/pms-hotelero",
    file: "pms-hotelero.html",
    title: "PMS hotelero | Hotels-PMS",
    description:
      "Qué es un PMS hotelero y qué tiene que resolver en un hotel chico o mediano que hoy trabaja con planillas y herramientas sueltas."
  },
  {
    path: "/software-para-hoteles",
    file: "software-para-hoteles.html",
    title: "Software para hoteles | Hotels-PMS",
    description:
      "Software de gestión hotelera en español para hoteles independientes y boutique, con la operación diaria sobre una sola base de datos."
  },
  {
    path: "/terms",
    file: "terms.html",
    title: "Términos y Condiciones | Hotels-PMS",
    description: "Términos y condiciones del servicio Hotels-PMS."
  },
  {
    path: "/privacy",
    file: "privacy.html",
    title: "Política de Privacidad | Hotels-PMS",
    description: "Cómo Hotels-PMS recolecta, usa y protege los datos personales de usuarios y huéspedes."
  }
];

const replaceTag = (html, pattern, replacement) =>
  pattern.test(html) ? html.replace(pattern, replacement) : html;

export function renderRouteHtml(indexHtml, route) {
  const url = `${SITE_URL}${route.path}`;
  let html = indexHtml;
  html = replaceTag(html, /<title>[\s\S]*?<\/title>/, `<title>${route.title}</title>`);
  html = replaceTag(
    html,
    /<meta name="description" content="[^"]*" \/>/,
    `<meta name="description" content="${route.description}" />`
  );
  html = replaceTag(
    html,
    /<meta property="og:title" content="[^"]*" \/>/,
    `<meta property="og:title" content="${route.title}" />`
  );
  html = replaceTag(
    html,
    /<meta property="og:description" content="[^"]*" \/>/,
    `<meta property="og:description" content="${route.description}" />`
  );
  html = replaceTag(
    html,
    /<meta property="og:url" content="[^"]*" \/>/,
    `<meta property="og:url" content="${url}" />`
  );
  html = replaceTag(
    html,
    /<meta property="og:image" content="[^"]*" \/>/,
    `<meta property="og:image" content="${OG_IMAGE}" />`
  );
  html = replaceTag(
    html,
    /<meta name="twitter:title" content="[^"]*" \/>/,
    `<meta name="twitter:title" content="${route.title}" />`
  );
  html = replaceTag(
    html,
    /<meta name="twitter:description" content="[^"]*" \/>/,
    `<meta name="twitter:description" content="${route.description}" />`
  );
  html = replaceTag(html, /<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url}" />`);
  return html;
}

export function marketingHtmlPlugin() {
  return {
    name: "hotels-pms-marketing-html",
    enforce: "post",
    generateBundle(_options, bundle) {
      const index = bundle["index.html"];
      if (!index || typeof index.source !== "string") return;
      for (const route of MARKETING_ROUTES) {
        this.emitFile({
          type: "asset",
          fileName: route.file,
          source: renderRouteHtml(index.source, route)
        });
      }
    }
  };
}
