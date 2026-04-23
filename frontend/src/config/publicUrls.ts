const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");
const ensureLeadingSlash = (value: string) => (value.startsWith("/") ? value : `/${value}`);

const normalizeUrl = (value?: string | null) => {
  const trimmed = value?.trim();
  return trimmed ? trimTrailingSlash(trimmed) : "";
};

export const PUBLIC_SITE_URL = normalizeUrl(import.meta.env.VITE_PUBLIC_SITE_URL as string | undefined);
export const PUBLIC_APP_URL = normalizeUrl(import.meta.env.VITE_PUBLIC_APP_URL as string | undefined);
export const PUBLIC_APP_HOSTNAME =
  (import.meta.env.VITE_PUBLIC_APP_HOSTNAME as string | undefined)?.trim() || "app.hoteles-pms.com";
export const ALLOW_INDEXING = String(import.meta.env.VITE_ALLOW_INDEXING ?? "").toLowerCase() === "true";
export const PUBLIC_SALES_EMAIL = "ventas@hoteles-pms.com";
export const resolveSalesContactUrl = (subject = "Consulta sobre Hotel Chipre PMS") =>
  `mailto:${PUBLIC_SALES_EMAIL}?subject=${encodeURIComponent(subject)}`;

export const isAppHostname = (hostname?: string) => {
  const resolved = hostname || (typeof window !== "undefined" ? window.location.hostname : "");
  return Boolean(resolved) && (resolved === PUBLIC_APP_HOSTNAME || resolved.endsWith(`.${PUBLIC_APP_HOSTNAME}`));
};

export const resolveSiteUrl = (path = "/") => {
  const normalizedPath = ensureLeadingSlash(path);
  return PUBLIC_SITE_URL ? `${PUBLIC_SITE_URL}${normalizedPath}` : normalizedPath;
};

export const resolveAppUrl = (path = "/") => {
  const normalizedPath = ensureLeadingSlash(path);
  return PUBLIC_APP_URL ? `${PUBLIC_APP_URL}${normalizedPath}` : normalizedPath;
};

export const resolveAssetUrl = (path = "/") => {
  const normalizedPath = ensureLeadingSlash(path);
  if (PUBLIC_SITE_URL) {
    return `${PUBLIC_SITE_URL}${normalizedPath}`;
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin}${normalizedPath}`;
  }
  return normalizedPath;
};

export const resolveCanonicalUrl = (path = "/") => {
  if (typeof window === "undefined") {
    return PUBLIC_SITE_URL ? `${PUBLIC_SITE_URL}${ensureLeadingSlash(path)}` : ensureLeadingSlash(path);
  }
  return PUBLIC_SITE_URL ? `${PUBLIC_SITE_URL}${ensureLeadingSlash(path)}` : `${window.location.origin}${ensureLeadingSlash(path)}`;
};
