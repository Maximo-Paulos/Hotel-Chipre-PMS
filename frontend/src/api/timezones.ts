import { apiFetch } from "./client";

export const listTimezones = () => apiFetch<string[]>("/api/reference/timezones");
