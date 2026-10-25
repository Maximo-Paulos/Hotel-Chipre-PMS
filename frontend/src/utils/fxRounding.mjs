const roundHalfUp = (value, scale) => {
  const scaled = value * scale;
  const rounded = Math.sign(scaled) * Math.floor(
    Math.abs(scaled) + 0.5 + Number.EPSILON * Math.abs(scaled)
  );
  return rounded / scale;
};

export function roundFxAmount(value, policy = "keep_remainder") {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return Number.NaN;

  switch (policy) {
    case "round_up": {
      const epsilon = Number.EPSILON * Math.max(1, Math.abs(amount));
      return Math.ceil(amount - epsilon);
    }
    case "round_down": {
      const epsilon = Number.EPSILON * Math.max(1, Math.abs(amount));
      return Math.floor(amount + epsilon);
    }
    case "nearest_ten":
      return roundHalfUp(amount / 10, 1) * 10;
    case "exact":
      return roundHalfUp(amount, 100);
    case "keep_remainder":
    default:
      return roundHalfUp(amount, 100);
  }
}

export function resolveFxRoundingPolicy(paymentMethod, hotelPolicy = "keep_remainder") {
  return paymentMethod === "cash" ? hotelPolicy : "exact";
}

export function suggestFxTenderSettlement(balance, reservationUnitsPerTenderUnit, policy = "keep_remainder") {
  const due = roundFxAmount(balance, "keep_remainder");
  const rate = Number(reservationUnitsPerTenderUnit);
  if (!Number.isFinite(due) || due < 0 || !Number.isFinite(rate) || rate <= 0) return null;

  const exactTenderAmount = roundFxAmount(due / rate, "keep_remainder");
  let tenderAmount = exactTenderAmount;
  let appliedAmount = roundFxAmount(tenderAmount * rate, "keep_remainder");
  // Never apply more than the reservation balance when a rounded tender
  // currency amount converts back a fraction above the exact due. Keep the
  // unrepresentable remainder payable in the reservation currency.
  while (appliedAmount > due && tenderAmount > 0) {
    tenderAmount = roundFxAmount(tenderAmount - 0.01, "keep_remainder");
    appliedAmount = roundFxAmount(tenderAmount * rate, "keep_remainder");
  }
  const suggestedTenderAmount = roundFxAmount(tenderAmount, policy);
  if (!Number.isFinite(tenderAmount) || !Number.isFinite(appliedAmount) || !Number.isFinite(suggestedTenderAmount)) return null;

  const dueMinorUnits = Math.round(due * 100);
  const appliedMinorUnits = Math.round(appliedAmount * 100);
  const difference = (dueMinorUnits - appliedMinorUnits) / 100;

  return {
    exactTenderAmount,
    tenderAmount,
    suggestedTenderAmount,
    appliedAmount,
    remainingDue: Math.max(0, difference),
    creditAmount: 0,
    isPartial: difference > 0
  };
}
