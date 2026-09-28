import { escapeHtml } from "./escapeHtml";

const PRINTABLE_PAYMENT_STATUSES = new Set(["completed", "refunded"]);

export function canPrintPaymentReceipt(status: string, hasCashOperationPermission: boolean): boolean {
  return hasCashOperationPermission && PRINTABLE_PAYMENT_STATUSES.has(status);
}

export type PaymentReceiptContent = {
  language: "en" | "es";
  title: string;
  heading: string;
  internalNotice: string;
  hotelLabel: string;
  hotelName: string;
  operationLabel: string;
  operationId: number | string;
  reservationLabel: string;
  reservationCode: string;
  dateLabel: string;
  date: string;
  movementLabel: string;
  movement: string;
  paymentMethodLabel: string;
  paymentMethod: string;
  statusLabel: string;
  status: string;
  appliedAmountLabel?: string;
  appliedAmount?: string | null;
  surchargeLabel?: string;
  surcharge?: string | null;
  amountLabel: string;
  amount: string;
  referenceLabel: string;
  manualReference?: string | null;
  refundOfLabel: string;
  refundOfTransactionId?: number | null;
};

/** Build a self-contained, printable internal receipt without persisting a file. */
export function buildPaymentReceiptHtml(receipt: PaymentReceiptContent): string {
  const row = (label: string, value: string | number) =>
    '<div class="row"><dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + "</dd></div>";
  const reference = receipt.manualReference?.trim();
  const referenceRow = reference ? row(receipt.referenceLabel, reference) : "";
  const appliedAmountRow = receipt.appliedAmount
    ? row(receipt.appliedAmountLabel || "", receipt.appliedAmount)
    : "";
  const surchargeRow = receipt.surcharge
    ? row(receipt.surchargeLabel || "", receipt.surcharge)
    : "";
  const refundRow = receipt.refundOfTransactionId != null
    ? row(receipt.refundOfLabel, "#" + receipt.refundOfTransactionId)
    : "";

  return [
    "<!doctype html>",
    '<html lang="' + escapeHtml(receipt.language) + '">',
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    "<title>" + escapeHtml(receipt.title) + "</title>",
    "<style>",
    "@page { size: A4; margin: 18mm; }",
    "* { box-sizing: border-box; }",
    "body { margin: 0; color: #0f172a; font: 14px/1.5 Arial, sans-serif; }",
    "main { max-width: 720px; margin: 0 auto; }",
    "header { border-bottom: 2px solid #0f766e; padding-bottom: 16px; }",
    "h1 { margin: 0 0 4px; font-size: 24px; line-height: 1.2; }",
    "header p { margin: 0; color: #475569; font-size: 15px; }",
    ".notice { margin: 18px 0; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 12px; color: #334155; font-size: 12px; }",
    ".details { margin: 0; border-top: 1px solid #e2e8f0; }",
    ".row { display: grid; grid-template-columns: minmax(150px, 1fr) 2fr; gap: 16px; border-bottom: 1px solid #e2e8f0; padding: 10px 0; }",
    "dt { color: #64748b; } dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }",
    ".amount { margin-top: 20px; border-radius: 6px; background: #f1f5f9; padding: 16px; }",
    ".amount dt { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }",
    ".amount dd { margin-top: 4px; font-size: 24px; }",
    "@media print { body { print-color-adjust: exact; -webkit-print-color-adjust: exact; } }",
    "@media screen { body { padding: 28px; background: #f8fafc; } main { background: #fff; padding: 28px; box-shadow: 0 2px 12px #0f172a18; } }",
    "</style>",
    "</head>",
    "<body><main>",
    "<header><h1>" + escapeHtml(receipt.heading) + "</h1><p>" + escapeHtml(receipt.hotelLabel) + ": " + escapeHtml(receipt.hotelName) + "</p></header>",
    '<p class="notice">' + escapeHtml(receipt.internalNotice) + "</p>",
    '<dl class="details">',
    row(receipt.operationLabel, "#" + receipt.operationId),
    row(receipt.reservationLabel, receipt.reservationCode),
    row(receipt.dateLabel, receipt.date),
    row(receipt.movementLabel, receipt.movement),
    row(receipt.paymentMethodLabel, receipt.paymentMethod),
    row(receipt.statusLabel, receipt.status),
    appliedAmountRow,
    surchargeRow,
    referenceRow,
    refundRow,
    "</dl>",
    '<dl class="amount"><dt>' + escapeHtml(receipt.amountLabel) + "</dt><dd>" + escapeHtml(receipt.amount) + "</dd></dl>",
    "</main></body></html>"
  ].join("");
}
