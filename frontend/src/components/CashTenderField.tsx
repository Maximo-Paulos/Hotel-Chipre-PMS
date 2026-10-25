import { useTranslation } from "react-i18next";

import { calculateCashTender, calculateCashTip, formatCashTenderAmount } from "../utils/cashTender.mjs";

type Props = {
  amount: string;
  tipAmount: string;
  expectedAmount: number;
  currency: string;
  label: string;
  hint: string;
  changeLabel: string;
  tipToggleLabel: string;
  tipAmountLabel: string;
  tipHint: string;
  invalidAmountMessage: string;
  insufficientMessage: string;
  tipInvalidMessage: string;
  onChange: (value: string) => void;
  onTipAmountChange: (value: string) => void;
  testId: string;
  disabled?: boolean;
};

export function CashTenderField({
  amount,
  tipAmount,
  expectedAmount,
  currency,
  label,
  hint,
  changeLabel,
  tipToggleLabel,
  tipAmountLabel,
  tipHint,
  invalidAmountMessage,
  insufficientMessage,
  tipInvalidMessage,
  onChange,
  onTipAmountChange,
  testId,
  disabled = false
}: Props) {
  const { i18n } = useTranslation("reservations");
  const locale = i18n.resolvedLanguage?.toLowerCase().startsWith("en") ? "en-US" : "es-AR";
  const tender = calculateCashTender(amount, expectedAmount);
  const changeBeforeTip = tender.valid ? tender.changeAmount ?? 0 : 0;
  const tip = calculateCashTip(tipAmount, changeBeforeTip);
  const tipSelected = Number(tipAmount) > 0;
  const errorMessage = tender.reason === "insufficient"
    ? insufficientMessage
    : tender.reason === "invalid_received"
      ? invalidAmountMessage
      : null;
  const inputId = `${testId}-input`;
  const hintId = `${testId}-hint`;
  const errorId = `${testId}-error`;
  const tipErrorId = `${testId}-tip-error`;

  return (
    <div className="space-y-1 text-xs">
      <label htmlFor={inputId} className="block font-semibold text-slate-700">{label}</label>
      <input
        id={inputId}
        type="number"
        min={expectedAmount > 0 ? expectedAmount : 0.01}
        step="0.01"
        value={amount}
        onChange={(event) => onChange(event.target.value)}
        placeholder={expectedAmount > 0 ? expectedAmount.toFixed(2) : "0.00"}
        disabled={disabled}
        aria-invalid={errorMessage ? true : undefined}
        aria-describedby={errorMessage ? `${hintId} ${errorId}` : hintId}
        data-testid={testId}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal text-slate-800 shadow-sm disabled:bg-slate-100"
      />
      <p id={hintId} className="text-slate-500">{hint}</p>
      {errorMessage ? <p id={errorId} className="text-rose-700" role="alert">{errorMessage}</p> : null}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <label className="flex items-start gap-2 text-slate-700">
          <input
            type="checkbox"
            checked={tipSelected}
            onChange={(event) => onTipAmountChange(event.target.checked ? changeBeforeTip.toFixed(2) : "")}
            disabled={disabled || !tender.valid || (changeBeforeTip <= 0 && !tipSelected)}
            className="mt-0.5 rounded border-slate-300"
            data-testid={`${testId}-tip-toggle`}
          />
          <span className="font-semibold">{tipToggleLabel}</span>
        </label>
        {tipSelected ? (
          <label className="mt-2 block font-semibold text-slate-700">
            {tipAmountLabel}
            <input
              type="number"
              min="0.01"
              max={changeBeforeTip}
              step="0.01"
              value={tipAmount}
              onChange={(event) => onTipAmountChange(event.target.value)}
              disabled={disabled || !tender.valid}
              aria-invalid={!tip.valid || undefined}
              aria-describedby={!tip.valid ? `${testId}-tip-hint ${tipErrorId}` : `${testId}-tip-hint`}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal text-slate-800 shadow-sm disabled:bg-slate-100"
              data-testid={`${testId}-tip-amount`}
            />
          </label>
        ) : null}
        <p id={`${testId}-tip-hint`} className="mt-1 text-slate-500">{tipHint}</p>
        {!tip.valid ? <p id={tipErrorId} className="text-rose-700" role="alert">{tipInvalidMessage}</p> : null}
      </div>
      <p className="font-semibold text-emerald-800" aria-live="polite" data-testid={`${testId}-change`}>
        {changeLabel}: {tender.valid && tip.valid && tip.changeAmount !== null
          ? formatCashTenderAmount(tip.changeAmount, currency, locale)
          : "—"}
      </p>
    </div>
  );
}
