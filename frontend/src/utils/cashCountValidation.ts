export const MAX_CASH_COUNT = 9_999_999_999.99;

/** Parse an explicit non-negative cash count without treating blank as zero. */
export const parseCashCount = (raw: string): number | null => {
  const normalized = raw.trim();
  if (!/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(normalized)) return null;

  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount < 0 || amount > MAX_CASH_COUNT) return null;
  return amount;
};
