const expenseProofLabel = "Referencia del comprobante o adjuntá una imagen";

export function cashExpenseValidationMessage({ category, vendor, receiptReference, hasReceiptImage }) {
  const missing = [];
  if (!String(category ?? "").trim()) missing.push("Categoría");
  if (!String(vendor ?? "").trim()) missing.push("Proveedor");
  if (!String(receiptReference ?? "").trim() && !hasReceiptImage) missing.push(expenseProofLabel);

  return missing.length ? `Completá: ${missing.join(", ")}.` : null;
}
