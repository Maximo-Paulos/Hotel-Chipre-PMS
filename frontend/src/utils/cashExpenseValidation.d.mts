export function cashExpenseValidationMessage(input: {
  category?: string | null;
  vendor?: string | null;
  receiptReference?: string | null;
  hasReceiptImage: boolean;
}): string | null;
