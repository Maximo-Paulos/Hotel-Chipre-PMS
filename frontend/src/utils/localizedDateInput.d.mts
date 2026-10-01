export type LocalizedDateMode = "date" | "datetime-local";

export function formatDateInputValue(value?: string | null): string;
export function formatDateTimeInputValue(value?: string | null): string;
export function maskDateInputValue(rawValue: string): string;
export function maskDateTimeInputValue(rawValue: string): string;
export function parseDateInputValue(displayValue: string): string | null;
export function parseDateTimeInputValue(displayValue: string): string | null;
export function dateInputCursorPosition(displayValue: string, digitCount: number): number;
export function formatNativeDateValue(value?: string | null): string;
export function formatNativeDateTimeValue(value?: string | null): string;
