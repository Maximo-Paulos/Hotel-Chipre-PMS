export function isLargeTotalAdjustment(currentAmount, proposedAmount) {
  const current = Number(currentAmount);
  const proposed = Number(proposedAmount);
  if (!Number.isFinite(current) || !Number.isFinite(proposed) || current < 0 || proposed < 0) {
    return false;
  }
  if (current === 0) return proposed > 0;
  return Math.abs(proposed - current) >= current * 0.5;
}
