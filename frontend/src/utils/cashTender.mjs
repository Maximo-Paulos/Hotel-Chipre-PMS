const toCents = (value) => {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return null;
  const cents = Math.round((amount + Number.EPSILON) * 100);
  return Math.abs(amount * 100 - cents) < 0.0001 ? cents : null;
};

/**
 * A blank tender field means the guest handed over the exact amount due.
 * Otherwise validate the delivered cash and calculate the change in cents.
 */
export function calculateCashTender(rawAmount, expectedAmount) {
  const expectedCents = toCents(expectedAmount);
  if (expectedCents === null || expectedCents <= 0) {
    return { valid: false, reason: "invalid_expected", receivedAmount: null, changeAmount: null };
  }

  const raw = String(rawAmount ?? "").trim();
  if (!raw) {
    return {
      valid: true,
      reason: null,
      receivedAmount: expectedCents / 100,
      changeAmount: 0,
      amountEntered: false
    };
  }

  const receivedCents = toCents(raw);
  if (receivedCents === null || receivedCents <= 0) {
    return { valid: false, reason: "invalid_received", receivedAmount: null, changeAmount: null, amountEntered: true };
  }
  if (receivedCents < expectedCents) {
    return { valid: false, reason: "insufficient", receivedAmount: receivedCents / 100, changeAmount: null, amountEntered: true };
  }

  return {
    valid: true,
    reason: null,
    receivedAmount: receivedCents / 100,
    changeAmount: (receivedCents - expectedCents) / 100,
    amountEntered: true
  };
}

/**
 * Validate an explicitly selected cash tip against the calculated change.
 * The tip remains separate from the amount applied to the reservation.
 */
export function calculateCashTip(rawAmount, availableChange) {
  const availableCents = toCents(availableChange);
  if (availableCents === null || availableCents < 0) {
    return { valid: false, reason: "invalid_change", tipAmount: null, changeAmount: null };
  }

  const raw = String(rawAmount ?? "").trim();
  if (!raw) {
    return {
      valid: true,
      reason: null,
      tipAmount: 0,
      changeAmount: availableCents / 100
    };
  }

  const tipCents = toCents(raw);
  if (tipCents === null || tipCents < 0) {
    return { valid: false, reason: "invalid_tip", tipAmount: null, changeAmount: null };
  }
  if (tipCents > availableCents) {
    return { valid: false, reason: "exceeds_change", tipAmount: null, changeAmount: null };
  }

  return {
    valid: true,
    reason: null,
    tipAmount: tipCents / 100,
    changeAmount: (availableCents - tipCents) / 100
  };
}

/** Format a physical cash amount with its cents visible, regardless of currency defaults. */
export function formatCashTenderAmount(value, currencyCode, locale = "es-AR") {
  const numericAmount = Number(value);
  const safeAmount = Number.isFinite(numericAmount) ? numericAmount : 0;
  const normalizedCurrency = String(currencyCode || "ARS").trim().toUpperCase() || "ARS";
  const options = {
    style: "currency",
    currency: normalizedCurrency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  };

  try {
    return new Intl.NumberFormat(locale, options).format(safeAmount);
  } catch {
    return new Intl.NumberFormat("es-AR", {
      ...options,
      currency: "ARS"
    }).format(safeAmount);
  }
}
