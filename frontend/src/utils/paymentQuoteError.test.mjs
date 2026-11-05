import test from "node:test";
import assert from "node:assert/strict";

import { isPaymentQuoteOverBalanceError } from "./paymentQuoteError.mjs";

test("recognizes the over-balance payment quote rejection", () => {
  assert.equal(
    isPaymentQuoteOverBalanceError(
      422,
      "El pago convertiría a 57001.00 ARS, por encima del saldo pendiente de 57000.00 ARS."
    ),
    true
  );
});

test("does not classify other quote errors or statuses as over-balance", () => {
  assert.equal(isPaymentQuoteOverBalanceError(422, "No se pudo asegurar la cotización del cobro."), false);
  assert.equal(
    isPaymentQuoteOverBalanceError(503, "El pago convertiría a 57001.00 ARS, por encima del saldo pendiente de 57000.00 ARS."),
    false
  );
  assert.equal(isPaymentQuoteOverBalanceError(422, undefined), false);
});
