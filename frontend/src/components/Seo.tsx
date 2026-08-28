import { useEffect } from "react";

import { resolveAssetUrl, resolveCanonicalUrl } from "../config/publicUrls";

type StructuredData = Record<string, unknown> | Array<Record<string, unknown>>;

type SeoProps = {
  title: string;
  description: string;
  canonicalPath?: string;
  noindex?: boolean;
  structuredData?: StructuredData | null;
  breadcrumbLabel?: string;
};

const socialImage = {
  url: resolveAssetUrl("/brand/og-default.png"),
  width: "1200",
  height: "630",
  type: "image/png",
  alt: "Hotels-PMS: sistema de gestión hotelera para hoteles independientes"
};

const setMetaTag = (selector: string, key: "name" | "property" | "content", value: string) => {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    const match = selector.match(/\[(name|property)="([^"]+)"\]/);
    if (match) {
      element.setAttribute(match[1], match[2]);
    }
    document.head.appendChild(element);
  }
  element.setAttribute(key, value);
};

export function Seo({
  title,
  description,
  canonicalPath = "/",
  noindex = false,
  structuredData = null,
  breadcrumbLabel
}: SeoProps) {
  useEffect(() => {
    document.title = title;
    document.documentElement.lang = "es";

    const normalizedPath = canonicalPath.startsWith("/") ? canonicalPath : `/${canonicalPath}`;
    const canonicalUrl =
      noindex && typeof window !== "undefined"
        ? `${window.location.origin}${normalizedPath}`
        : resolveCanonicalUrl(normalizedPath);
    setMetaTag('meta[name="description"]', "content", description);
    setMetaTag('meta[name="robots"]', "content", noindex ? "noindex, nofollow" : "index, follow");
    setMetaTag('meta[property="og:title"]', "content", title);
    setMetaTag('meta[property="og:description"]', "content", description);
    setMetaTag('meta[property="og:type"]', "content", "website");
    setMetaTag('meta[property="og:site_name"]', "content", "Hotels-PMS");
    setMetaTag('meta[property="og:url"]', "content", canonicalUrl);
    setMetaTag('meta[property="og:image"]', "content", socialImage.url);
    setMetaTag('meta[property="og:image:width"]', "content", socialImage.width);
    setMetaTag('meta[property="og:image:height"]', "content", socialImage.height);
    setMetaTag('meta[property="og:image:type"]', "content", socialImage.type);
    setMetaTag('meta[property="og:image:alt"]', "content", socialImage.alt);
    setMetaTag('meta[name="twitter:card"]', "content", "summary_large_image");
    setMetaTag('meta[name="twitter:title"]', "content", title);
    setMetaTag('meta[name="twitter:description"]', "content", description);
    setMetaTag('meta[name="twitter:image"]', "content", socialImage.url);
    setMetaTag('meta[name="twitter:image:alt"]', "content", socialImage.alt);

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.appendChild(canonical);
    }
    canonical.href = canonicalUrl;

    const existingSchema = document.head.querySelector<HTMLScriptElement>('script[data-seo-jsonld="true"]');
    if (existingSchema) {
      existingSchema.remove();
    }
    const shouldAddBreadcrumb = !noindex && normalizedPath !== "/";
    const breadcrumbSchema = shouldAddBreadcrumb
      ? {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: [
            {
              "@type": "ListItem",
              position: 1,
              name: "Inicio",
              item: resolveCanonicalUrl("/")
            },
            {
              "@type": "ListItem",
              position: 2,
              name: breadcrumbLabel || title.split("|")[0].trim(),
              item: canonicalUrl
            }
          ]
        }
      : null;
    const schemas = [
      ...(Array.isArray(structuredData) ? structuredData : structuredData ? [structuredData] : []),
      ...(breadcrumbSchema ? [breadcrumbSchema] : [])
    ];
    if (schemas.length > 0) {
      const schema = document.createElement("script");
      schema.type = "application/ld+json";
      schema.setAttribute("data-seo-jsonld", "true");
      schema.textContent = JSON.stringify(schemas);
      document.head.appendChild(schema);
    }
  }, [breadcrumbLabel, canonicalPath, description, noindex, structuredData, title]);

  return null;
}
