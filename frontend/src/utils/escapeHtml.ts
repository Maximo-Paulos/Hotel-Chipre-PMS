const HTML_ENTITIES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;"
};

/** Escape an untrusted value before placing it in an HTML text node. */
export const escapeHtml = (value: unknown): string =>
  String(value ?? "").replace(/[&<>"']/g, (character) => HTML_ENTITIES[character]);

/** Never substitute a lodging-only balance when an operational balance is absent. */
export const resolveVoucherOperationalBalance = (
  ...values: Array<number | null | undefined>
): number | null => {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) return value;
  }
  return null;
};
