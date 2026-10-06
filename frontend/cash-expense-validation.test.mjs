import assert from "node:assert/strict";
import test from "node:test";

import { cashExpenseValidationMessage } from "./src/utils/cashExpenseValidation.mjs";

test("cash expense validation names missing required details before a request can be sent", () => {
  assert.equal(
    cashExpenseValidationMessage({ category: " ", vendor: "", receiptReference: "", hasReceiptImage: false }),
    "Completá: Categoría, Proveedor, Referencia del comprobante o adjuntá una imagen."
  );
});

test("cash expense can use an attached receipt image instead of a reference number", () => {
  assert.equal(
    cashExpenseValidationMessage({ category: "Limpieza", vendor: "Proveedor", receiptReference: "", hasReceiptImage: true }),
    null
  );
});

test("cash expense trims details and requires a receipt reference or image", () => {
  assert.equal(
    cashExpenseValidationMessage({ category: "Limpieza", vendor: "Proveedor", receiptReference: "   ", hasReceiptImage: false }),
    "Completá: Referencia del comprobante o adjuntá una imagen."
  );
});
