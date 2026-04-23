import { useEffect } from "react";

import { resolveAssetUrl, resolveCanonicalUrl } from "../config/publicUrls";

type StructuredData = Record<string, unknown> | Array<Record<string, unknown>>;

type SeoProps = {
  title: string;
  description: string;
  canonicalPath?: string;
  noindex?: boolean;
  structuredData?: StructuredData | null;
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

export function Seo({ title, description, canonicalPath = "/", noindex = false, structuredData = null }: SeoProps) {
  useEffect(() => {
    document.title = title;
    document.documentElement.lang = "es";

    const canonicalUrl = resolveCanonicalUrl(canonicalPath);
    setMetaTag('meta[name="description"]', "content", description);
    setMetaTag('meta[name="robots"]', "content", noindex ? "noindex, nofollow" : "index, follow");
    setMetaTag('meta[property="og:title"]', "content", title);
    setMetaTag('meta[property="og:description"]', "content", description);
    setMetaTag('meta[property="og:type"]', "content", "website");
    setMetaTag('meta[property="og:image"]', "content", resolveAssetUrl("/brand/logo-full.png"));
    setMetaTag('meta[name="twitter:card"]', "content", "summary_large_image");
    setMetaTag('meta[name="twitter:title"]', "content", title);
    setMetaTag('meta[name="twitter:description"]', "content", description);
    setMetaTag('meta[name="twitter:image"]', "content", resolveAssetUrl("/brand/logo-full.png"));

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
    if (structuredData) {
      const schema = document.createElement("script");
      schema.type = "application/ld+json";
      schema.setAttribute("data-seo-jsonld", "true");
      schema.textContent = JSON.stringify(structuredData);
      document.head.appendChild(schema);
    }
  }, [canonicalPath, description, noindex, structuredData, title]);

  return null;
}
