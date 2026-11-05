/**
 * Detect the backend's explicit over-balance quote rejection without treating
 * other validation or availability failures as an amount problem.
 */
export function isPaymentQuoteOverBalanceError(status, message) {
  return status === 422
    && typeof message === "string"
    && message.startsWith("El pago convertiría a ")
    && message.includes(", por encima del saldo pendiente de ");
}
