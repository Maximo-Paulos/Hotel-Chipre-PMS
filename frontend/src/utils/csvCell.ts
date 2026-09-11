/**
 * One CSV cell for a value an untrusted visitor controls.
 *
 * A leading = + - @ tab or carriage return makes Excel, Numbers and Google
 * Sheets evaluate the cell as a formula (CSV injection), so those get a
 * leading apostrophe. Quotes, commas and line breaks get the value quoted.
 */
export const toCsvCell = (value: unknown): string => {
  let text = value == null ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
