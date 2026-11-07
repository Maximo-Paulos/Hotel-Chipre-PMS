const STALE_CHUNK_ERROR_PATTERNS = [
  /failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /importing a module script failed/i,
  /loading chunk\s+\S+\s+failed/i
];

export function createCacheBustedReloadUrl(currentUrl, timestamp = Date.now()) {
  const url = new URL(currentUrl);
  url.searchParams.set("__app_reload", String(timestamp));
  return url.toString();
}

export function isStaleBundleLoadError(error) {
  const message =
    typeof error === "string"
      ? error
      : error && typeof error === "object" && "message" in error && typeof error.message === "string"
        ? error.message
        : "";

  return STALE_CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}
