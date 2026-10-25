export type CashTenderResult = {
  valid: boolean;
  reason: "invalid_expected" | "invalid_received" | "insufficient" | null;
  receivedAmount: number | null;
  changeAmount: number | null;
  amountEntered?: boolean;
};

export function calculateCashTender(rawAmount: string | number | null | undefined, expectedAmount: number): CashTenderResult;

export type CashTipResult = {
  valid: boolean;
  reason: "invalid_change" | "invalid_tip" | "exceeds_change" | null;
  tipAmount: number | null;
  changeAmount: number | null;
};

export function calculateCashTip(
  rawAmount: string | number | null | undefined,
  availableChange: number
): CashTipResult;

export function formatCashTenderAmount(
  value: number | string | null | undefined,
  currencyCode?: string | null,
  locale?: string
): string;
