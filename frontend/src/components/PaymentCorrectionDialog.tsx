import { useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  correctPaymentTransaction,
  newPaymentCorrectionIdempotencyKey,
  type PaymentCorrectionRequest,
  type PaymentCorrectionResponse,
  type PaymentCorrectionType,
  type PaymentSummary
} from "../api/payments";
import type { SessionLike } from "../api/client";
import { useDialogA11y } from "../hooks/useDialogA11y";
import { formatMoney } from "../utils/currency";

type PaymentCorrectionSource = Pick<PaymentSummary["transactions"][number], "id" | "amount" | "currency" | "method">;

type PaymentCorrectionDialogProps = {
  open: boolean;
  transaction: PaymentCorrectionSource | null;
  sourceConfirmationCode: string;
  session: SessionLike;
  onClose: () => void;
  onSuccess: (
    result: PaymentCorrectionResponse,
    destinationConfirmationCode: string
  ) => void;
};

type CorrectionFormState = {
  transactionId: number;
  correctionType: PaymentCorrectionType;
  destinationConfirmationCode: string;
  reason: string;
};

export default function PaymentCorrectionDialog({
  open,
  transaction,
  sourceConfirmationCode,
  session,
  onClose,
  onSuccess
}: PaymentCorrectionDialogProps) {
  const { t } = useTranslation("reservations");
  const isOpen = open && transaction !== null;
  const [formState, setFormState] = useState<CorrectionFormState | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intentRef = useRef<{ fingerprint: string; key: string } | null>(null);
  const containerRef = useDialogA11y(isOpen, () => {
    if (!pending) onClose();
  });

  if (!isOpen || !transaction) return null;

  const form = formState?.transactionId === transaction.id
    ? formState
    : {
        transactionId: transaction.id,
        correctionType: "reassign" as const,
        destinationConfirmationCode: "",
        reason: ""
      };
  const isCashPayment = transaction.method === "cash";

  const updateForm = (changes: Partial<Omit<CorrectionFormState, "transactionId">>) => {
    setFormState({ ...form, ...changes });
    setError(null);
  };

  const handleClose = () => {
    if (pending) return;
    setError(null);
    setFormState((current) => current?.transactionId === transaction.id ? null : current);
    onClose();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const destinationCode = form.destinationConfirmationCode.trim().toUpperCase();
    const reason = form.reason.trim();
    if (!reason) {
      setError(t("page.details.paymentCorrection.reasonRequired"));
      return;
    }
    if (form.correctionType === "reassign" && !destinationCode) {
      setError(t("page.details.paymentCorrection.destinationRequired"));
      return;
    }

    const payload: PaymentCorrectionRequest = form.correctionType === "reassign"
      ? {
          correction_type: "reassign",
          destination_confirmation_code: destinationCode,
          reason
        }
      : { correction_type: "duplicate_reversal", reason };
    const fingerprint = JSON.stringify({ transactionId: transaction.id, payload });
    const intent = intentRef.current?.fingerprint === fingerprint
      ? intentRef.current
      : {
          fingerprint,
          key: newPaymentCorrectionIdempotencyKey(transaction.id)
        };
    intentRef.current = intent;

    setPending(true);
    setError(null);
    try {
      const result = await correctPaymentTransaction(
        transaction.id,
        payload,
        session,
        intent.key
      );
      onSuccess(result, destinationCode);
      setError(null);
      setFormState((current) => current?.transactionId === transaction.id ? null : current);
      onClose();
    } catch {
      // API errors are currently returned in Spanish; keep the operator-facing
      // message in the selected interface language instead of rendering a raw
      // server message here.
      setError(t("page.details.paymentCorrection.failed"));
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-slate-900/50 px-3 py-5 sm:px-4"
      onClick={() => {
        if (!pending) handleClose();
      }}
    >
      <section
        ref={containerRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="payment-correction-title"
        aria-describedby="payment-correction-description"
        className="max-h-[90vh] w-full max-w-xl animate-scale-in overflow-y-auto rounded-xl border border-slate-200 bg-white p-5 shadow-xl outline-none sm:p-6"
        data-testid="payment-correction-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="payment-correction-title" className="text-lg font-semibold text-slate-900">
              {t("page.details.paymentCorrection.title", { id: transaction.id })}
            </h2>
            <p id="payment-correction-description" className="mt-1 text-sm text-slate-600">
              {t("page.details.paymentCorrection.description")}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={pending}
            className="min-h-11 shrink-0 rounded-lg px-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-50"
          >
            {t("page.common.close")}
          </button>
        </div>

        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="font-semibold text-slate-900">
            {formatMoney(transaction.amount, transaction.currency)} · {t(`page.paymentMethods.${transaction.method}`)}
          </p>
          <p className="mt-1 text-xs text-slate-600">
            {t("page.details.paymentCorrection.sourceReservation", { code: sourceConfirmationCode })}
          </p>
        </div>

        <form className="mt-4 space-y-4" onSubmit={(event) => void handleSubmit(event)}>
          <fieldset disabled={pending}>
            <legend className="text-sm font-semibold text-slate-700">
              {t("page.details.paymentCorrection.operation")}
            </legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm hover:bg-slate-50">
                <input
                  type="radio"
                  name="payment-correction-type"
                  value="reassign"
                  checked={form.correctionType === "reassign"}
                  onChange={() => updateForm({ correctionType: "reassign" })}
                  className="mt-0.5"
                />
                <span>
                  <span className="block font-semibold text-slate-800">{t("page.details.paymentCorrection.reassign")}</span>
                  <span className="mt-1 block text-xs font-normal text-slate-600">
                    {t(isCashPayment
                      ? "page.details.paymentCorrection.cashReassignHint"
                      : "page.details.paymentCorrection.reassignHint")}
                  </span>
                </span>
              </label>
              <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm hover:bg-slate-50">
                <input
                  type="radio"
                  name="payment-correction-type"
                  value="duplicate_reversal"
                  checked={form.correctionType === "duplicate_reversal"}
                  onChange={() => updateForm({ correctionType: "duplicate_reversal" })}
                  className="mt-0.5"
                />
                <span>
                  <span className="block font-semibold text-slate-800">{t("page.details.paymentCorrection.duplicateReversal")}</span>
                  <span className="mt-1 block text-xs font-normal text-slate-600">
                    {t(isCashPayment
                      ? "page.details.paymentCorrection.cashDuplicateReversalHint"
                      : "page.details.paymentCorrection.duplicateReversalHint")}
                  </span>
                </span>
              </label>
            </div>
          </fieldset>

          {form.correctionType === "reassign" ? (
            <label className="block text-sm font-semibold text-slate-700">
              {t("page.details.paymentCorrection.destinationCode")}
              <input
                type="text"
                value={form.destinationConfirmationCode}
                disabled={pending}
                onChange={(event) => updateForm({ destinationConfirmationCode: event.target.value })}
                maxLength={40}
                required
                autoComplete="off"
                autoCapitalize="characters"
                className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal uppercase text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                placeholder={t("page.details.paymentCorrection.destinationCodePlaceholder")}
                data-testid="payment-correction-destination-code"
              />
            </label>
          ) : null}

          <label className="block text-sm font-semibold text-slate-700">
            {t("page.details.paymentCorrection.reason")}
            <textarea
              value={form.reason}
              disabled={pending}
              onChange={(event) => updateForm({ reason: event.target.value })}
              minLength={3}
              maxLength={240}
              rows={3}
              required
              className="mt-1 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 font-normal text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              placeholder={t("page.details.paymentCorrection.reasonPlaceholder")}
              data-testid="payment-correction-reason"
            />
          </label>

          <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            {t("page.details.paymentCorrection.notRefund")}
          </p>

          {error ? <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p> : null}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={handleClose}
              disabled={pending}
              className="min-h-11 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {t("page.form.cancel")}
            </button>
            <button
              type="submit"
              disabled={pending || form.reason.trim().length < 3 || (form.correctionType === "reassign" && !form.destinationConfirmationCode.trim())}
              aria-busy={pending}
              className="min-h-11 rounded-lg border border-rose-700 bg-rose-700 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="payment-correction-submit"
            >
              {pending
                ? t("page.details.paymentCorrection.submitting")
                : t("page.details.paymentCorrection.submit")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
