import { Capacitor } from "@capacitor/core";

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");
const ensureLeadingSlash = (value: string) => (value.startsWith("/") ? value : `/${value}`);
const parseHostname = (value?: string | null) => {
  if (!value) return "";
  try {
    return new URL(value).hostname;
  } catch {
    return "";
  }
};

const normalizeUrl = (value?: string | null) => {
  const trimmed = value?.trim();
  return trimmed ? trimTrailingSlash(trimmed) : "";
};

export const PUBLIC_SITE_URL = normalizeUrl(import.meta.env.VITE_PUBLIC_SITE_URL as string | undefined);
export const PUBLIC_APP_URL = normalizeUrl(import.meta.env.VITE_PUBLIC_APP_URL as string | undefined);
const ENV_APP_HOSTNAME = (import.meta.env.VITE_PUBLIC_APP_HOSTNAME as string | undefined)?.trim() || "";
const APP_URL_HOSTNAME = parseHostname(PUBLIC_APP_URL);
const SITE_URL_HOSTNAME = parseHostname(PUBLIC_SITE_URL);
const ALLOW_PREVIEW_APP_HOST = String(import.meta.env.VITE_ALLOW_PREVIEW_APP_HOST ?? "").toLowerCase() === "true";
const PREVIEW_APP_HOST_SUFFIXES = (import.meta.env.VITE_PREVIEW_APP_HOST_SUFFIXES as string | undefined ?? ".vercel.app")
  .split(",")
  .map((suffix) => suffix.trim().toLowerCase())
  .filter(Boolean)
  .map((suffix) => (suffix.startsWith(".") ? suffix : `.${suffix}`));

export const PUBLIC_APP_HOSTNAME = ENV_APP_HOSTNAME || APP_URL_HOSTNAME || "app.hotels-pms.com";
export const PUBLIC_SITE_HOSTNAME =
  SITE_URL_HOSTNAME || (PUBLIC_APP_HOSTNAME.startsWith("app.") ? PUBLIC_APP_HOSTNAME.slice(4) : "");
export const ALLOW_INDEXING = String(import.meta.env.VITE_ALLOW_INDEXING ?? "").toLowerCase() === "true";
export const PUBLIC_SALES_EMAIL = "ventas@hotels-pms.com";
export const resolveSalesContactUrl = (subject = "Consulta sobre Hotel Chipre PMS") =>
  `mailto:${PUBLIC_SALES_EMAIL}?subject=${encodeURIComponent(subject)}`;

export const isAppHostname = (hostname?: string) => {
  // Packaged Capacitor apps load from capacitor://localhost (iOS) or
  // https://localhost (Android WebView), never from app.hotels-pms.com, so
  // the hostname check below can never match. Treat any native shell as the
  // app host directly so it never redirects itself to the marketing site.
  if (!hostname && Capacitor.isNativePlatform()) return true;
  const resolved = (hostname || (typeof window !== "undefined" ? window.location.hostname : "")).toLowerCase();
  if (!resolved) return false;
  const candidates = Array.from(
    new Set([PUBLIC_APP_HOSTNAME, APP_URL_HOSTNAME].map((value) => value.trim().toLowerCase()).filter(Boolean))
  );
  if (candidates.some((candidate) => resolved === candidate || resolved.endsWith(`.${candidate}`))) {
    return true;
  }
  return ALLOW_PREVIEW_APP_HOST && PREVIEW_APP_HOST_SUFFIXES.some((suffix) => resolved.endsWith(suffix));
};

const buildAbsoluteUrl = (baseUrl: string, path = "/", search = "", hash = "") => {
  const pathname = ensureLeadingSlash(path);
  return baseUrl ? `${baseUrl}${pathname}${search}${hash}` : `${pathname}${search}${hash}`;
};

export const resolveSiteUrl = (path = "/") => {
  const siteBaseUrl = PUBLIC_SITE_URL || (PUBLIC_SITE_HOSTNAME ? `https://${PUBLIC_SITE_HOSTNAME}` : "");
  return buildAbsoluteUrl(siteBaseUrl, path);
};

export const resolveAppUrl = (path = "/") => {
  const appBaseUrl = PUBLIC_APP_URL || (PUBLIC_APP_HOSTNAME ? `https://${PUBLIC_APP_HOSTNAME}` : "");
  return buildAbsoluteUrl(appBaseUrl, path);
};

export const resolveSiteLocation = (path = "/", search = "", hash = "") => {
  const siteBaseUrl = PUBLIC_SITE_URL || (PUBLIC_SITE_HOSTNAME ? `https://${PUBLIC_SITE_HOSTNAME}` : "");
  return buildAbsoluteUrl(siteBaseUrl, path, search, hash);
};

export const resolveAppLocation = (path = "/", search = "", hash = "") => {
  const appBaseUrl = PUBLIC_APP_URL || (PUBLIC_APP_HOSTNAME ? `https://${PUBLIC_APP_HOSTNAME}` : "");
  return buildAbsoluteUrl(appBaseUrl, path, search, hash);
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
