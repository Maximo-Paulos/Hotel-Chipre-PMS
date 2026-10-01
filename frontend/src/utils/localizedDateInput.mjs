const validCalendarDate = (year, month, day) => {
  if (year < 1 || month < 1 || month > 12 || day < 1) return false;
  const value = new Date(Date.UTC(year, month - 1, day));
  return value.getUTCFullYear() === year && value.getUTCMonth() === month - 1 && value.getUTCDate() === day;
};

export const formatDateInputValue = (value) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? "");
  if (!match) return "";
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
};

export const formatDateTimeInputValue = (value) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value ?? "");
  if (!match) return "";
  const [, year, month, day, hour, minute] = match;
  return `${day}/${month}/${year} ${hour}:${minute}`;
};

export const maskDateInputValue = (rawValue) => {
  const trimmed = rawValue.trim();
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (isoMatch) return formatDateInputValue(rawValue.trim());
  const separatedMatch = /^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$/.exec(trimmed);
  if (separatedMatch) {
    const [, day, month, year] = separatedMatch;
    return `${day.padStart(2, "0")}/${month.padStart(2, "0")}/${year}`;
  }

  const digits = rawValue.replace(/\D/g, "").slice(0, 8);
  const day = digits.slice(0, 2);
  const month = digits.slice(2, 4);
  const year = digits.slice(4, 8);
  return `${day}${digits.length > 2 ? `/${month}` : ""}${digits.length > 4 ? `/${year}` : ""}`;
};

export const maskDateTimeInputValue = (rawValue) => {
  const trimmed = rawValue.trim();
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(trimmed);
  if (isoMatch) return formatDateTimeInputValue(rawValue.trim());
  const separatedMatch = /^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\s+(\d{1,2}):(\d{2})$/.exec(trimmed);
  if (separatedMatch) {
    const [, day, month, year, hour, minute] = separatedMatch;
    return `${day.padStart(2, "0")}/${month.padStart(2, "0")}/${year} ${hour.padStart(2, "0")}:${minute}`;
  }

  const digits = rawValue.replace(/\D/g, "").slice(0, 12);
  const day = digits.slice(0, 2);
  const month = digits.slice(2, 4);
  const year = digits.slice(4, 8);
  const hour = digits.slice(8, 10);
  const minute = digits.slice(10, 12);
  return `${day}${digits.length > 2 ? `/${month}` : ""}${digits.length > 4 ? `/${year}` : ""}${digits.length > 8 ? ` ${hour}` : ""}${digits.length > 10 ? `:${minute}` : ""}`;
};

export const parseDateInputValue = (displayValue) => {
  if (!displayValue) return "";
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(displayValue);
  if (!match) return null;
  const [, dayText, monthText, yearText] = match;
  const day = Number(dayText);
  const month = Number(monthText);
  const year = Number(yearText);
  if (!validCalendarDate(year, month, day)) return null;
  return `${yearText}-${monthText}-${dayText}`;
};

export const parseDateTimeInputValue = (displayValue) => {
  if (!displayValue) return "";
  const match = /^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})$/.exec(displayValue);
  if (!match) return null;
  const [, dayText, monthText, yearText, hourText, minuteText] = match;
  const day = Number(dayText);
  const month = Number(monthText);
  const year = Number(yearText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  if (!validCalendarDate(year, month, day) || hour > 23 || minute > 59) return null;
  return `${yearText}-${monthText}-${dayText}T${hourText}:${minuteText}`;
};

export const dateInputCursorPosition = (displayValue, digitCount) => {
  if (digitCount <= 0) return 0;
  let digitsSeen = 0;
  for (let index = 0; index < displayValue.length; index += 1) {
    if (/\d/.test(displayValue[index])) digitsSeen += 1;
    if (digitsSeen >= digitCount) return index + 1;
  }
  return displayValue.length;
};

export const formatNativeDateValue = (value) => formatDateInputValue(value);
export const formatNativeDateTimeValue = (value) => formatDateTimeInputValue(value);
