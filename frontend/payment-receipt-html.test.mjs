import assert from "node:assert/strict";
import { buildSync } from "esbuild";
import { fileURLToPath } from "node:url";
import test from "node:test";

const entry = fileURLToPath(new URL("./src/utils/paymentReceiptHtml.ts", import.meta.url));
const { outputFiles } = buildSync({
  entryPoints: [entry],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false
});
const { buildPaymentReceiptHtml, canPrintPaymentReceipt } = await import(
  `data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString("base64")}`
);

const receipt = {
  language: "es",
  title: "Comprobante interno de pago 41",
  heading: "Comprobante interno de pago",
  internalNotice: "No reemplaza una factura fiscal.",
  hotelLabel: "Hotel",
  hotelName: "Hotel Chipre",
  operationLabel: "Operación",
  operationId: 41,
  reservationLabel: "Reserva",
  reservationCode: "HC-2041",
  dateLabel: "Fecha y hora",
  date: "28 sep 2026, 14:32",
  movementLabel: "Movimiento",
  movement: "Pago parcial",
  paymentMethodLabel: "Medio de pago",
  paymentMethod: "Transferencia",
  statusLabel: "Estado",
  status: "Confirmado",
  amountLabel: "Importe registrado",
  amount: "$ 25.000,00",
  referenceLabel: "Referencia de operación",
  manualReference: "TR-9981",
  refundOfLabel: "Devolución del pago",
  refundOfTransactionId: null
};

test("receipt uses the saved transaction identity and prints as a self-contained internal document", () => {
  const html = buildPaymentReceiptHtml(receipt);

  assert.match(html, /<html lang="es">/);
  assert.match(html, /Hotel Chipre/);
  assert.match(html, /#41/);
  assert.match(html, /HC-2041/);
  assert.match(html, /TR-9981/);
  assert.match(html, /No reemplaza una factura fiscal/);
  assert.doesNotMatch(html, /https?:\/\//i);
  assert.doesNotMatch(html, /<script\b|<iframe\b/i);
});

test("receipt escapes dynamic hotel, reservation, and reference values", () => {
  const html = buildPaymentReceiptHtml({
    ...receipt,
    hotelName: '<img src=x onerror="alert(1)">',
    reservationCode: "<script>alert('x')</script>",
    manualReference: 'POS " onmouseover="alert(2)'
  });

  assert.doesNotMatch(html, /<img\b|<script\b/i);
  assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.match(html, /&lt;script&gt;alert\(&#39;x&#39;\)&lt;\/script&gt;/);
  assert.match(html, /POS &quot; onmouseover=&quot;alert\(2\)/);
});

test("refund receipts identify the original payment and omit empty optional references", () => {
  const html = buildPaymentReceiptHtml({
    ...receipt,
    movement: "Devolución",
    manualReference: " ",
    refundOfTransactionId: 35
  });

  assert.match(html, /Devolución/);
  assert.match(html, /#35/);
  assert.doesNotMatch(html, /TR-9981/);
});

test("foreign-currency receipt shows both credited amount and frozen exchange rate", () => {
  const html = buildPaymentReceiptHtml({
    ...receipt,
    appliedAmountLabel: "Importe aplicado a la reserva",
    appliedAmount: "ARS 14.000,00",
    fxRateLabel: "Cotización aplicada al cobro",
    fxRate: "1 ARS = 0,001 USD"
  });

  assert.match(html, /Importe aplicado a la reserva/);
  assert.match(html, /ARS 14\.000,00/);
  assert.match(html, /Cotización aplicada al cobro/);
  assert.match(html, /1 ARS = 0,001 USD/);
});

test("only authorized users can print confirmed payment or refund movements", () => {
  assert.equal(canPrintPaymentReceipt("completed", true), true);
  assert.equal(canPrintPaymentReceipt("refunded", true), true);
  assert.equal(canPrintPaymentReceipt("pending", true), false);
  assert.equal(canPrintPaymentReceipt("failed", true), false);
  assert.equal(canPrintPaymentReceipt("cancelled", true), false);
  assert.equal(canPrintPaymentReceipt("completed", false), false);
});
