import { useEffect, useRef, useState, type ChangeEvent, type FocusEvent } from "react";
import { createPortal } from "react-dom";

import {
  dateInputCursorPosition,
  formatDateInputValue,
  formatDateTimeInputValue,
  maskDateInputValue,
  maskDateTimeInputValue,
  parseDateInputValue,
  parseDateTimeInputValue,
  type LocalizedDateMode
} from "../utils/localizedDateInput.mjs";

type LocalizedDateFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  mode?: LocalizedDateMode;
  placeholder: string;
  chooseDateLabel: string;
  invalidMessage: string;
  className?: string;
  labelClassName?: string;
  inputClassName?: string;
  testId?: string;
  required?: boolean;
  disabled?: boolean;
  title?: string;
  min?: string;
  max?: string;
  onFocus?: (event: FocusEvent<HTMLInputElement>) => void;
  onBlur?: (event: FocusEvent<HTMLInputElement>) => void;
};

const defaultInputClassName =
  "mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 pr-10 text-sm text-slate-800 shadow-sm focus:border-brand-400 focus:outline-none disabled:bg-slate-50";

const formatValue = (value: string, mode: LocalizedDateMode) =>
  mode === "date" ? formatDateInputValue(value) : formatDateTimeInputValue(value);

const maskValue = (value: string, mode: LocalizedDateMode) =>
  mode === "date" ? maskDateInputValue(value) : maskDateTimeInputValue(value);

const parseValue = (value: string, mode: LocalizedDateMode) =>
  mode === "date" ? parseDateInputValue(value) : parseDateTimeInputValue(value);

export default function LocalizedDateField({
  id,
  label,
  value,
  onChange,
  mode = "date",
  placeholder,
  chooseDateLabel,
  invalidMessage,
  className = "",
  labelClassName = "text-xs font-semibold text-slate-600",
  inputClassName = defaultInputClassName,
  testId = "localized-date-input",
  required = false,
  disabled = false,
  title,
  min,
  max,
  onFocus,
  onBlur
}: LocalizedDateFieldProps) {
  const inputType = mode === "date" ? "date" : "datetime-local";
  const [displayValue, setDisplayValue] = useState(() => formatValue(value, mode));
  const inputRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLInputElement>(null);
  const pickerId = `${id}-native-picker`;

  useEffect(() => {
    const parsedDisplay = parseValue(displayValue, mode);
    if ((parsedDisplay ?? "") !== value) setDisplayValue(formatValue(value, mode));
  }, [displayValue, mode, value]);

  useEffect(() => {
    inputRef.current?.setCustomValidity(displayValue && parseValue(displayValue, mode) === null ? invalidMessage : "");
  }, [displayValue, invalidMessage, mode]);

  const updateFromNativePicker = (event: ChangeEvent<HTMLInputElement>) => {
    const nextValue = event.currentTarget.value;
    setDisplayValue(formatValue(nextValue, mode));
    onChange(nextValue);
  };

  const handleTextChange = (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const rawValue = input.value;
    const rawCaret = input.selectionStart ?? rawValue.length;
    const digitCount = rawValue.slice(0, rawCaret).replace(/\D/g, "").length;
    const nextDisplay = maskValue(rawValue, mode);
    setDisplayValue(nextDisplay);
    onChange(parseValue(nextDisplay, mode) ?? "");

    window.requestAnimationFrame(() => {
      if (document.activeElement === input) {
        const nextCaret = dateInputCursorPosition(nextDisplay, digitCount);
        input.setSelectionRange(nextCaret, nextCaret);
      }
    });
  };

  const openPicker = () => {
    const picker = pickerRef.current;
    if (!picker) return;
    try {
      if (typeof picker.showPicker === "function") picker.showPicker();
      else picker.click();
    } catch {
      picker.click();
    }
  };

  return (
    <div className={className}>
      <label htmlFor={id} className={labelClassName}>{label}</label>
      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          maxLength={mode === "date" ? 10 : 16}
          value={displayValue}
          onChange={handleTextChange}
          onFocus={onFocus}
          onBlur={onBlur}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          title={title}
          aria-label={label}
          data-testid={testId}
          className={inputClassName}
        />
        <button
          type="button"
          aria-label={chooseDateLabel}
          title={chooseDateLabel}
          disabled={disabled}
          onClick={openPicker}
          className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600 disabled:opacity-40"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.6">
            <rect x="3" y="4.5" width="14" height="12" rx="2" />
            <path d="M6.5 2.8v3.4M13.5 2.8v3.4M3 8h14" />
          </svg>
        </button>
      </div>
      {createPortal(
        <input
          ref={pickerRef}
          id={pickerId}
          type={inputType}
          value={value}
          min={min}
          max={max}
          onChange={updateFromNativePicker}
          aria-hidden="true"
          tabIndex={-1}
          data-testid={`${testId}-native-picker`}
          className="pointer-events-none fixed left-0 top-0 h-px w-px opacity-0"
        />,
        document.body
      )}
    </div>
  );
}
