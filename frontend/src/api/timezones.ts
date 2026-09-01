import { apiFetch } from "./client";

export type ReferenceCountry = { code: string; name: string; timezone: string };

export const listTimezones = () => apiFetch<string[]>("/api/reference/timezones");

export const listCountries = () => apiFetch<ReferenceCountry[]>("/api/reference/countries");
